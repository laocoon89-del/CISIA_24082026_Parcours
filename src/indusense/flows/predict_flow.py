"""M30 — flow réel ingest → feature → predict → store (contrats : docs/flow_design.md).

Le flow ORCHESTRE la lib déjà testée (build_dataset, add_temporal_features, predict_proba) :
aucune logique métier n'est réécrite ici. Chaque run score la dernière observation de chaque
machine et l'historise dans `predictions` par UPSERT sur (machine, prediction_ts) : rejouer
le flow met à jour les lignes au lieu d'en ajouter (idempotence).

    # Hôte (SQLite) : base de preuve neuve, jeu complet via INDUSENSE_DATA_DIR
    uv run python -m indusense.flows.predict_flow
    # Compose (PostgreSQL) : via le service api, INDUSENSE_DB_URL fourni par docker-compose.yml
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd
from prefect import flow, get_run_logger, task
from sqlalchemy import create_engine, text

from indusense.config import settings
from indusense.data.loaders import build_dataset, load_incidents, load_pressure, load_temperature
from indusense.features.temporal import add_temporal_features
from indusense.models.tabular import load_model, predict_proba, select_features

# Clé naturelle (machine, prediction_ts) = PRIMARY KEY : support de l'upsert.
DDL = {
    "sqlite": """CREATE TABLE IF NOT EXISTS predictions (
        machine TEXT NOT NULL,
        prediction_ts TEXT NOT NULL,
        proba_panne REAL NOT NULL,
        decision TEXT NOT NULL,
        model_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (machine, prediction_ts))""",
    "postgresql": """CREATE TABLE IF NOT EXISTS predictions (
        machine TEXT NOT NULL,
        prediction_ts TIMESTAMP NOT NULL,
        proba_panne DOUBLE PRECISION NOT NULL,
        decision TEXT NOT NULL,
        model_version TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (machine, prediction_ts))""",
}
# Même syntaxe ON CONFLICT pour SQLite (>= 3.24) et PostgreSQL.
UPSERT = text("""INSERT INTO predictions
        (machine, prediction_ts, proba_panne, decision, model_version, created_at)
    VALUES (:machine, :prediction_ts, :proba_panne, :decision, :model_version, :created_at)
    ON CONFLICT (machine, prediction_ts) DO UPDATE SET
        proba_panne = excluded.proba_panne,
        decision = excluded.decision,
        model_version = excluded.model_version,
        created_at = excluded.created_at""")


def _summary(prefix: str, df: pd.DataFrame) -> str:
    """Résumé nommé de la population (jamais les lignes sources)."""
    count = int(df[settings.target_col].sum())
    return (
        f"{prefix}_rows={len(df)} {prefix}_panne_count={count} "
        f"{prefix}_panne_rate={count / len(df):.8f}"
    )


@task
def ingest(data_dir: str) -> pd.DataFrame:
    """3 sources -> jointure capteurs (merge_asof by="machine") + cible `panne` (date + time)."""
    root = Path(data_dir)
    joined = build_dataset(
        load_temperature(root / "capteurs_temperature.csv"),
        load_pressure(root / "capteurs_pression.tsv"),
        load_incidents(root / "releves_incidents.csv"),
        window_hours=settings.incident_window_hours,
    )
    get_run_logger().info(_summary("joined", joined))
    return joined


@task
def feature(joined: pd.DataFrame) -> pd.DataFrame:
    """Transformation PURE (lags et moyennes passées par machine) : pas de retries."""
    gold = add_temporal_features(joined).dropna().reset_index(drop=True)
    get_run_logger().info(_summary("gold", gold))
    return gold


@task
def predict(gold: pd.DataFrame, model_dir: str) -> pd.DataFrame:
    """Score la dernière observation de chaque machine avec le modèle livré."""
    model = load_model(Path(model_dir) / "rf.joblib")
    meta = json.loads((Path(model_dir) / "model_metadata.json").read_text(encoding="utf-8"))
    latest = gold.sort_values("timestamp").groupby("machine").tail(1).reset_index(drop=True)
    proba = predict_proba(model, select_features(latest, settings.target_col))
    preds = pd.DataFrame(
        {
            "machine": latest["machine"],
            "prediction_ts": latest["timestamp"],
            "proba_panne": proba,
            "decision": ["alerte" if p >= settings.decision_threshold else "ok" for p in proba],
            "model_version": str(meta.get("package_version", "0")),
        }
    )
    get_run_logger().info("predict : %d machines scorées", len(preds))
    return preds


# DB = ressource externe : seule task avec retries + backoff (erreurs transitoires).
@task(retries=3, retry_delay_seconds=[5, 15, 45])
def store(preds: pd.DataFrame) -> int:
    """UPSERT dans `predictions`. L'URL est lue dans l'environnement, jamais journalisée."""
    db_url = os.environ.get("INDUSENSE_DB_URL")
    if not db_url:
        raise RuntimeError("INDUSENSE_DB_URL absente : base de preuve non définie")
    engine = create_engine(db_url)
    dialect = engine.dialect.name
    now = dt.datetime.now(dt.UTC)
    rows = [
        {
            "machine": r.machine,
            # SQLite refuse un pandas.Timestamp brut : ISO 8601 ; PostgreSQL : datetime Python.
            "prediction_ts": (
                pd.Timestamp(r.prediction_ts).isoformat()
                if dialect == "sqlite"
                else pd.Timestamp(r.prediction_ts).to_pydatetime()
            ),
            "proba_panne": float(r.proba_panne),
            "decision": r.decision,
            "model_version": r.model_version,
            "created_at": now.isoformat() if dialect == "sqlite" else now,
        }
        for r in preds.itertuples()
    ]
    with engine.begin() as cx:
        cx.execute(text(DDL[dialect]))
        cx.execute(UPSERT, rows)
        total = cx.execute(text("SELECT count(*) FROM predictions")).scalar_one()
    engine.dispose()
    get_run_logger().info("store : %d lignes upsertées, %d lignes en base", len(rows), total)
    return len(rows)


@flow(name="indusense-predict-flow")
def predict_flow(data_dir: str | None = None, model_dir: str | None = None) -> int:
    """ingest -> feature -> predict -> store ; paramètres retrouvables dans chaque run."""
    joined = ingest(str(data_dir or settings.data_dir))
    gold = feature(joined)
    preds = predict(gold, str(model_dir or settings.model_dir))
    return store(preds)


if __name__ == "__main__":
    predict_flow()
