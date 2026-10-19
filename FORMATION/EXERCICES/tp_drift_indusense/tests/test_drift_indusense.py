# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — FORMATION/EXERCICES/tp_drift_indusense/tests/test_drift_indusense.py
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

"""Tests du kit drift InduSense — definition of done du scénario complet."""
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pytest

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "scripts"))
import drift_lab  # noqa: E402

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
DATA = RACINE / "data"
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
MODELES = RACINE / "models"

# [PÉDAGOGIE] BLOC `test_psi_quasi_nul_sur_distributions_identiques` — ce test transforme un
# [PÉDAGOGIE] comportement attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_quasi_nul_sur_distributions_identiques():
    rng = np.random.default_rng(0)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert drift_lab.psi(rng.normal(0, 1, 20000), rng.normal(0, 1, 5000)) < 0.05

# [PÉDAGOGIE] BLOC `test_psi_detecte_un_decalage` — ce test transforme un comportement attendu en
# [PÉDAGOGIE] contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_detecte_un_decalage():
    rng = np.random.default_rng(2)
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert drift_lab.psi(rng.normal(0, 1, 20000), rng.normal(1, 1, 5000)) > 0.25

# [PÉDAGOGIE] BLOC `test_psi_ignore_les_nan` — ce test transforme un comportement attendu en
# [PÉDAGOGIE] contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_psi_ignore_les_nan():
    rng = np.random.default_rng(3)
    ref = rng.normal(0, 1, 10000); ref[::50] = np.nan
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert drift_lab.psi(ref, rng.normal(0, 1, 3000)) < 0.05

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
_donnees = (DATA / "reference_normale.csv").exists() and (DATA / "fenetre_3.csv").exists()
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
_modele = (MODELES / "model.joblib").exists()
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
donnees = pytest.mark.skipif(not _donnees, reason="lancez d'abord scripts/build_dataset.py")
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
modele = pytest.mark.skipif(not (_donnees and _modele), reason="lancez d'abord scripts/train_model.py")

# [PÉDAGOGIE] BLOC `_t` — unité de responsabilité : isoler un comportement nommable, testable et
# [PÉDAGOGIE] réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : fen, ref ; preuve : l'appelant doit pouvoir vérifier la sortie
# [PÉDAGOGIE] ou l'effet de bord annoncé.
def _t(fen, ref):
    import pandas as pd
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return drift_lab.drift_table(pd.read_csv(DATA / f"reference_{ref}.csv"), pd.read_csv(DATA / f"fenetre_{fen}.csv"))

# [PÉDAGOGIE] BLOC `test_fenetre1_temoin_silencieuse` — ce test transforme un comportement attendu
# [PÉDAGOGIE] en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
@donnees
def test_fenetre1_temoin_silencieuse():
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert (_t("1", "normale")["psi"] < 0.10).all()

# [PÉDAGOGIE] BLOC `test_fenetre2_capteur_detecte` — ce test transforme un comportement attendu en
# [PÉDAGOGIE] contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
@donnees
def test_fenetre2_capteur_detecte():
    tab = _t("2", "normale").set_index("feature")
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert tab.loc["temperature", "psi"] > 0.25
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert tab.loc["temperature", "ks_pvalue"] < 1e-6

# [PÉDAGOGIE] BLOC `test_fenetre3_concept_muet_au_psi` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
@donnees
def test_fenetre3_concept_muet_au_psi():
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert (_t("3", "normale")["psi"] < 0.10).all()

# [PÉDAGOGIE] BLOC `test_janvier_reference_par_regime` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
@donnees
def test_janvier_reference_par_regime():
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert _t("janvier", "normale").set_index("feature").loc["temperature", "psi"] > 0.25  # fausse alerte
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert (_t("janvier", "haute")["psi"] < 0.10).all()                                    # même régime : silence

# [PÉDAGOGIE] BLOC `test_concept_drift_effondre_le_rappel` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
@modele
def test_concept_drift_effondre_le_rappel():
    import evaluate_fenetre
    m1 = evaluate_fenetre.evaluer_fenetre("1")
    m3 = evaluate_fenetre.evaluer_fenetre("3")
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert m1["rappel"] > 0.60
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert m3["rappel"] < 0.5 * m1["rappel"]
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert m3["roc_auc"] < 0.5
    # [PÉDAGOGIE] ORACLE — l'assertion compare le résultat observé au contrat attendu par ce test.
    assert abs(m3["taux_alerte"] - m1["taux_alerte"]) < 0.05  # panne silencieuse côté ops
