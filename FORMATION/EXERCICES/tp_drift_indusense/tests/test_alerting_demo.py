# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — FORMATION/EXERCICES/tp_drift_indusense/tests/test_alerting_demo.py
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

"""Tests de la preuve autonome M32, sans réseau, Docker ni base externe."""
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "scripts"))
from alerting_demo import DDL, maybe_alert, run_demo  # noqa: E402


# [PÉDAGOGIE] BLOC `test_sequence_canonique_trace_une_seule_alerte` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_sequence_canonique_trace_une_seule_alerte() -> None:
    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with sqlite3.connect(":memory:") as connection:
        sequence, _ = run_demo(connection)
        rows = connection.execute(
            "SELECT feature, psi FROM drift_events ORDER BY id"
        ).fetchall()
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert sequence == [0, 1, 0]
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert len(rows) == 1
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert rows[0][0] == "temperature"
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert rows[0][1] > 0.25


# [PÉDAGOGIE] BLOC `test_cooldown_expire_apres_six_heures` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_cooldown_expire_apres_six_heures() -> None:
    report = {
        "temperature": {"psi": 0.30, "ks_p": 0.0, "drift": True},
        "_global": {"drift": True},
    }
    t0 = datetime(2026, 2, 25, 9, 0, tzinfo=timezone.utc)
    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with sqlite3.connect(":memory:") as connection:
        connection.execute(DDL)
        # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce
        # [PÉDAGOGIE] test.
        assert maybe_alert(connection, report, t0) == 1
        # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce
        # [PÉDAGOGIE] test.
        assert maybe_alert(connection, report, t0 + timedelta(hours=1)) == 0
        # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce
        # [PÉDAGOGIE] test.
        assert maybe_alert(connection, report, t0 + timedelta(hours=6)) == 1
        count = connection.execute("SELECT count(*) FROM drift_events").fetchone()[0]
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert count == 2


# [PÉDAGOGIE] BLOC `test_fenetre_saine_ne_cree_aucun_evenement` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_fenetre_saine_ne_cree_aucun_evenement() -> None:
    report = {
        "temperature": {"psi": 0.02, "ks_p": 0.3, "drift": False},
        "_global": {"drift": False},
    }
    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with sqlite3.connect(":memory:") as connection:
        connection.execute(DDL)
        # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce
        # [PÉDAGOGIE] test.
        assert maybe_alert(connection, report, datetime.now(timezone.utc)) == 0
        count = connection.execute("SELECT count(*) FROM drift_events").fetchone()[0]
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert count == 0
