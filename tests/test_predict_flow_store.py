"""M30 — idempotence de la task `store` : deux exécutions -> 0 doublon (SQLite, zéro infra)."""

from __future__ import annotations

import pandas as pd
from prefect.logging import disable_run_logger
from sqlalchemy import create_engine, text

from indusense.flows.predict_flow import store

PREDS = pd.DataFrame(
    {
        "machine": ["MACH-01", "MACH-02"],
        "prediction_ts": pd.to_datetime(["2026-01-01 06:00", "2026-01-01 06:00"]),
        "proba_panne": [0.12, 0.81],
        "decision": ["ok", "alerte"],
        "model_version": ["0.1.0", "0.1.0"],
    }
)


def test_store_deux_runs_zero_doublon(tmp_path, monkeypatch):
    db = tmp_path / "predictions.db"
    monkeypatch.setenv("INDUSENSE_DB_URL", f"sqlite:///{db.as_posix()}")

    # .fn = la fonction Python sous le décorateur @task (pas de serveur Prefect).
    with disable_run_logger():
        store.fn(PREDS)
        store.fn(PREDS.assign(proba_panne=[0.20, 0.90]))  # rejeu avec nouveau score

    with create_engine(f"sqlite:///{db.as_posix()}").connect() as cx:
        total = cx.execute(text("SELECT count(*) FROM predictions")).scalar_one()
        dups = cx.execute(
            text(
                "SELECT count(*) FROM (SELECT 1 FROM predictions "
                "GROUP BY machine, prediction_ts HAVING count(*) > 1)"
            )
        ).scalar_one()
        proba = cx.execute(
            text("SELECT proba_panne FROM predictions WHERE machine = 'MACH-01'")
        ).scalar_one()

    assert total == len(PREDS)  # l'upsert a mis à jour, pas empilé
    assert dups == 0  # aucun doublon sur la clé naturelle
    assert proba == 0.20  # la ligne existante porte le dernier score
