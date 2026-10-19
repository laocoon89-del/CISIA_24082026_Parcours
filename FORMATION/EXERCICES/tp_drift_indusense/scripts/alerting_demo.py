# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — FORMATION/EXERCICES/tp_drift_indusense/scripts/alerting_demo.py
# [PÉDAGOGIE] MODULE  — M31–M32 — dérive, performance retardée et décision d'alerte
# [PÉDAGOGIE] RÔLE    — Comparer une référence gelée à une fenêtre courante puis transformer les
# [PÉDAGOGIE]           mesures en décision traçable.
# [PÉDAGOGIE] THÉORIE — le PSI mesure un déplacement de distribution ; KS teste un écart
# [PÉDAGOGIE]           statistique
# [PÉDAGOGIE]           • une dérive d'entrée ne prouve pas à elle seule une dégradation de
# [PÉDAGOGIE]             performance métier
# [PÉDAGOGIE]           • seuil, fenêtre, segmentation et cooldown font partie du contrat de
# [PÉDAGOGIE]             détection
# [PÉDAGOGIE] À VOIR  — Le rapport doit conserver valeurs, seuils, décision, fenêtre, référence et
# [PÉDAGOGIE]           horodatage UTC.
# [PÉDAGOGIE] PIÈGE   — Changer les bins ou la référence entre deux fenêtres rend la comparaison
# [PÉDAGOGIE]           difficile à interpréter.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

"""Preuve M32 autonome : rapport PSI/KS, drift_events et cooldown 0 -> 1 -> 0.

Ce script reste dans le kit Sprint 3 et s'exécute sans Docker ni PostgreSQL. Il utilise
les CSV InduSense déjà versionnés, la convention PSI du module 31 et une base SQLite
en mémoire par défaut. Il ne remplace pas l'intégration Prefect/PostgreSQL : il prouve
la règle de décision et la traçabilité avant ce branchement.
"""
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "scripts"))
from drift_lab import SEUIL_PSI_FORT, drift_table  # noqa: E402

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
DDL = """
CREATE TABLE IF NOT EXISTS drift_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TEXT NOT NULL,
    feature TEXT NOT NULL,
    psi REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
)
"""


# [PÉDAGOGIE] BLOC `make_report` — construction déterministe : produire la même sortie pour les
# [PÉDAGOGIE] mêmes entrées et paramètres.
# [PÉDAGOGIE] CONTRAT — entrées : reference, current ; preuve : vérifier forme, taille, empreinte
# [PÉDAGOGIE] ou invariants de la sortie.
def make_report(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    """Retourne le contrat JSON du module 32 à partir du calcul testé du module 31."""
    table = drift_table(reference, current)
    report: dict[str, Any] = {}
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for row in table.itertuples(index=False):
        report[str(row.feature)] = {
            "psi": float(row.psi),
            "ks_p": float(row.ks_pvalue),
            "drift": bool(row.psi > SEUIL_PSI_FORT),
        }
    report["_global"] = {"drift": any(v["drift"] for v in report.values())}
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return report


# [PÉDAGOGIE] BLOC `should_alert` — décision d'alerte : transformer un signal en événement
# [PÉDAGOGIE] actionnable et traçable.
# [PÉDAGOGIE] CONTRAT — entrées : connection, feature, now, cooldown_hours ; preuve : prouver le
# [PÉDAGOGIE] seuil, le cooldown et l'absence de doublon lors d'une reprise.
def should_alert(
    connection: sqlite3.Connection,
    feature: str,
    now: datetime,
    cooldown_hours: int = 6,
) -> bool:
    """Autorise une alerte si aucune alerte récente n'existe pour la feature."""
    last = connection.execute(
        "SELECT max(detected_at) FROM drift_events WHERE feature = ?", (feature,)
    ).fetchone()[0]
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if last is None:
        # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et
        # [PÉDAGOGIE] son sens doivent rester stables.
        return True
    last_at = datetime.fromisoformat(str(last))
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return now - last_at >= timedelta(hours=cooldown_hours)


# [PÉDAGOGIE] BLOC `maybe_alert` — décision d'alerte : transformer un signal en événement
# [PÉDAGOGIE] actionnable et traçable.
# [PÉDAGOGIE] CONTRAT — entrées : connection, report, now, cooldown_hours ; preuve : prouver le
# [PÉDAGOGIE] seuil, le cooldown et l'absence de doublon lors d'une reprise.
def maybe_alert(
    connection: sqlite3.Connection,
    report: dict[str, Any],
    now: datetime,
    cooldown_hours: int = 6,
) -> int:
    """Insère au plus une alerte pour la feature la plus dérivée ; retourne 0 ou 1."""
    candidates = [
        (feature, values)
        for feature, values in report.items()
        if feature != "_global" and values["drift"]
    ]
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if not candidates:
        # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et
        # [PÉDAGOGIE] son sens doivent rester stables.
        return 0
    feature, values = max(candidates, key=lambda item: item[1]["psi"])
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if not should_alert(connection, feature, now, cooldown_hours):
        # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et
        # [PÉDAGOGIE] son sens doivent rester stables.
        return 0
    connection.execute(
        "INSERT INTO drift_events(detected_at, feature, psi) VALUES (?, ?, ?)",
        (now.isoformat(), feature, float(values["psi"])),
    )
    connection.commit()
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return 1


# [PÉDAGOGIE] BLOC `run_demo` — orchestration : rendre l'ordre, les dépendances et les points
# [PÉDAGOGIE] d'échec visibles.
# [PÉDAGOGIE] CONTRAT — entrées : connection ; preuve : chaque étape doit annoncer sa preuve avant
# [PÉDAGOGIE] que la suivante ne commence.
def run_demo(connection: sqlite3.Connection) -> tuple[list[int], dict[str, Any]]:
    """Joue fenêtre saine, dérive +8 °C puis relance à +1 h sous cooldown."""
    connection.execute(DDL)
    data = RACINE / "data"
    reference = pd.read_csv(data / "reference_normale.csv")
    healthy = make_report(reference, pd.read_csv(data / "fenetre_1.csv"))
    drifted = make_report(reference, pd.read_csv(data / "fenetre_2.csv"))
    t0 = datetime(2026, 2, 25, 9, 0, tzinfo=timezone.utc)
    sequence = [
        maybe_alert(connection, healthy, t0),
        maybe_alert(connection, drifted, t0),
        maybe_alert(connection, drifted, t0 + timedelta(hours=1)),
    ]
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return sequence, drifted


# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default=":memory:",
        help="SQLite : :memory: par défaut, ou chemin explicite pour conserver la preuve.",
    )
    parser.add_argument("--json", action="store_true", help="Affiche aussi le rapport JSON.")
    parser.add_argument(
        "--report-out",
        type=Path,
        help="Écrit le rapport JSON dans ce chemin (créé sous le dossier demandé).",
    )
    args = parser.parse_args()

    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with sqlite3.connect(args.db) as connection:
        sequence, report = run_demo(connection)
        rows = connection.execute(
            "SELECT detected_at, feature, psi, status FROM drift_events ORDER BY id"
        ).fetchall()
        print("sequence=" + " -> ".join(map(str, sequence)))
        print(f"drift_events={len(rows)}")
        # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément
        # [PÉDAGOGIE] le cas vrai et le cas faux.
        if rows:
            print(f"event_feature={rows[0][1]}")
            print(f"event_psi={rows[0][2]:.3f}")
        # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément
        # [PÉDAGOGIE] le cas vrai et le cas faux.
        if args.report_out:
            args.report_out.parent.mkdir(parents=True, exist_ok=True)
            args.report_out.write_text(
                json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(f"report_out={args.report_out}")
        # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément
        # [PÉDAGOGIE] le cas vrai et le cas faux.
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément
        # [PÉDAGOGIE] le cas vrai et le cas faux.
        if sequence != [0, 1, 0] or len(rows) != 1:
            # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les
            # [PÉDAGOGIE] étapes suivantes.
            raise SystemExit("Preuve M32 invalide : attendu 0 -> 1 -> 0 et une ligne.")


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
