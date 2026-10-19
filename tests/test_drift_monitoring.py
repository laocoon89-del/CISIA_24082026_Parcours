# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — tests/test_drift_monitoring.py
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

# =============================================================================
# tests/test_drift_monitoring.py — Tests du module de dérive (m31-32)
# Aucune donnée réelle requise : distributions synthétiques contrôlées.
# =============================================================================
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import numpy as np
import pandas as pd

from indusense.monitoring.drift import drift_report, drift_table, ks_pvalue, psi, verdict_psi


# [PÉDAGOGIE] BLOC `test_psi_quasi_nul_sur_distributions_identiques` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_quasi_nul_sur_distributions_identiques():
    rng = np.random.default_rng(0)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert psi(rng.normal(0, 1, 20_000), rng.normal(0, 1, 5_000)) < 0.05


# [PÉDAGOGIE] BLOC `test_psi_detecte_un_decalage_d_un_ecart_type` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_detecte_un_decalage_d_un_ecart_type():
    rng = np.random.default_rng(2)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert psi(rng.normal(0, 1, 20_000), rng.normal(1, 1, 5_000)) > 0.25


# [PÉDAGOGIE] BLOC `test_psi_compte_les_valeurs_hors_plage_de_reference` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_compte_les_valeurs_hors_plage_de_reference():
    # La moitié de la masse courante sort de la plage de la référence : une
    # implémentation à bins fermés sous-estime (~0,35) voire annule (~0) le PSI.
    ref = np.linspace(0.0, 1.0, 5_000)
    cur = np.concatenate([np.linspace(0.0, 1.0, 1_000), np.full(1_000, 5.0)])
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert psi(ref, cur) > 0.8


# [PÉDAGOGIE] BLOC `test_psi_ignore_les_nan_capteurs` — ce test transforme un comportement attendu
# [PÉDAGOGIE] en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_ignore_les_nan_capteurs():
    rng = np.random.default_rng(3)
    ref = rng.normal(50, 4, 10_000)
    ref[::50] = np.nan  # trous de capteur réalistes
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert psi(ref, rng.normal(50, 4, 3_000)) < 0.05


# [PÉDAGOGIE] BLOC `test_ks_pvalue_coherente` — ce test transforme un comportement attendu en
# [PÉDAGOGIE] contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_ks_pvalue_coherente():
    rng = np.random.default_rng(4)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert ks_pvalue(rng.normal(0, 1, 4_000), rng.normal(0, 1, 4_000)) > 0.001
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert ks_pvalue(rng.normal(0, 1, 4_000), rng.normal(1, 1, 4_000)) < 1e-6


# [PÉDAGOGIE] BLOC `test_verdicts_suivent_les_seuils_du_cours` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_verdicts_suivent_les_seuils_du_cours():
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert "RAS" in verdict_psi(0.05)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert "surveiller" in verdict_psi(0.18)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert "forte" in verdict_psi(0.60)


# [PÉDAGOGIE] BLOC `test_drift_table_structure_et_tri` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_drift_table_structure_et_tri():
    rng = np.random.default_rng(5)
    df_ref = pd.DataFrame({"a": rng.normal(0, 1, 5_000), "b": rng.normal(0, 1, 5_000)})
    df_cur = pd.DataFrame({"a": rng.normal(0, 1, 2_000), "b": rng.normal(2, 1, 2_000)})
    table = drift_table(df_ref, df_cur, features=("a", "b"))
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert list(table.columns) == ["feature", "psi", "ks_pvalue", "verdict"]
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert table.loc[0, "feature"] == "b"  # tri PSI décroissant


# [PÉDAGOGIE] BLOC `test_drift_report_contrat_module32` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_drift_report_contrat_module32():
    rng = np.random.default_rng(6)
    df_ref = pd.DataFrame({"a": rng.normal(0, 1, 5_000), "b": rng.normal(0, 1, 5_000)})
    df_cur = pd.DataFrame({"a": rng.normal(0, 1, 2_000), "b": rng.normal(2, 1, 2_000)})
    rapport = drift_report(df_ref, df_cur, features=("a", "b"))
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert rapport["b"]["drift"] is True and rapport["a"]["drift"] is False
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert rapport["_global"]["drift"] is True
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert set(rapport["a"]) == {"psi", "ks_p", "drift"}
