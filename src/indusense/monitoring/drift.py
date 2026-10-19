# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — src/indusense/monitoring/drift.py
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
# src/indusense/monitoring/drift.py — Détection de dérive des données (m31-32)
# -----------------------------------------------------------------------------
# ROLE : mesurer si les données COURANTES ressemblent encore aux données de
# RÉFÉRENCE (celles de l'entraînement). Deux outils complémentaires :
#   - PSI (Population Stability Index) : l'AMPLEUR du déplacement de masse ;
#   - test KS (Kolmogorov-Smirnov)     : la SIGNIFICATIVITÉ statistique.
# Règle du cours : on DÉCIDE sur l'ampleur (PSI + seuils), KS confirme.
# Lecture usuelle du PSI : < 0,10 RAS · 0,10-0,25 à surveiller · > 0,25 fort.
# =============================================================================
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

#: Seuils de lecture usuels du PSI (conventions credit scoring, cf. m31 §2.2).
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
SEUIL_PSI_SURVEILLER = 0.10
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
SEUIL_PSI_FORT = 0.25

#: Features capteurs surveillées par défaut (drift spec InduSense).
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
FEATURES_SURVEILLEES = ("temperature", "pressure_bar")


# [PÉDAGOGIE] BLOC `psi` — mesure de dérive : comparer la fenêtre courante à une référence sans
# [PÉDAGOGIE] changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : ref, cur, bins ; preuve : conserver bins, seuils, segmentation,
# [PÉDAGOGIE] fenêtre et valeurs calculées dans le rapport.
def psi(ref, cur, bins: int = 10) -> float:
    """Population Stability Index entre référence et fenêtre courante.

    Conventions (m31, à FIGER dans la drift spec) :
      - bins calculés sur la RÉFÉRENCE (grille stable dans le temps) ;
      - bords extrêmes ouverts (±inf) : une valeur courante HORS de la plage de
        la référence est comptée dans un bin de bord — sinon np.histogram la
        jette en silence et une dérive d'échelle devient invisible ;
      - lissage +1e-6 : évite ln(0) sur les bins vides ;
      - les NaN (vraies données capteurs !) sont écartés feature par feature.
    """
    # `pd.Series(...)` accepte aussi bien une liste, une série pandas qu'un
    # tableau NumPy. Le passage par `dropna()` retire les mesures manquantes :
    # le PSI doit comparer des valeurs observées, pas transformer NaN en nombre.
    # `np.asarray(..., dtype=float)` donne ensuite un format numérique homogène
    # compris par les fonctions d'histogramme, quel que soit le type d'entrée.
    ref = np.asarray(pd.Series(ref).dropna(), dtype=float)
    cur = np.asarray(pd.Series(cur).dropna(), dtype=float)

    # Les tranches sont calculées UNE FOIS sur la référence. On fige ainsi la
    # règle de mesure : deux fenêtres de production sont comparées avec la même
    # « règle graduée ». Recalculer les bins sur `cur` masquerait une dérive.
    edges = np.histogram_bin_edges(ref, bins=bins)

    # NumPy ignore normalement les valeurs situées hors des bords. En ouvrant
    # les deux extrémités, toute valeur courante très basse ou très haute tombe
    # dans un bin de bord au lieu de disparaître silencieusement du calcul.
    edges[0], edges[-1] = -np.inf, np.inf

    # `np.histogram(...)[0]` renvoie les EFFECTIFS par tranche. On divise par la
    # taille de l'échantillon pour obtenir des PROPORTIONS comparables lorsque
    # référence et production n'ont pas le même nombre de lignes.
    # Le petit epsilon empêche une division par zéro et `log(0)` si un bin est
    # vide. Cette convention doit rester figée dans la drift spec du projet.
    p_ref = np.histogram(ref, edges)[0] / len(ref) + 1e-6
    p_cur = np.histogram(cur, edges)[0] / len(cur) + 1e-6

    # Formule, bin par bin : déplacement de masse × logarithme du rapport.
    # `np.sum` agrège toutes les contributions ; `float` renvoie un nombre
    # Python simple, facile à sérialiser ensuite dans un CSV ou un rapport JSON.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return float(np.sum((p_cur - p_ref) * np.log(p_cur / p_ref)))


# [PÉDAGOGIE] BLOC `ks_pvalue` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : ref, cur ; preuve : conserver bins, seuils, segmentation,
# [PÉDAGOGIE] fenêtre et valeurs calculées dans le rapport.
def ks_pvalue(ref, cur) -> float:
    """p-value du test KS à 2 échantillons (p ≈ 0 → distributions différentes).

    Attention à grands n : significatif ≠ important — voir psi() pour l'ampleur.
    """
    # `ks_2samp` compare les fonctions de répartition empiriques des deux
    # échantillons. Seule la p-value est exposée ici : le reste du projet attend
    # un scalaire sérialisable, pas l'objet résultat complet de SciPy.
    # Comme pour le PSI, on écarte les NaN feature par feature.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return float(stats.ks_2samp(pd.Series(ref).dropna(), pd.Series(cur).dropna()).pvalue)


# [PÉDAGOGIE] BLOC `verdict_psi` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : valeur ; preuve : conserver bins, seuils, segmentation, fenêtre
# [PÉDAGOGIE] et valeurs calculées dans le rapport.
def verdict_psi(valeur: float) -> str:
    """Verdict lisible selon les seuils du cours."""
    # L'ordre des tests est important : on traite d'abord le cas le plus faible,
    # puis la zone intermédiaire. Tout ce qui reste est donc une dérive forte.
    # Les bornes exactes (0,10 et 0,25) passent dans la catégorie supérieure.
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if valeur < SEUIL_PSI_SURVEILLER:
        # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et
        # [PÉDAGOGIE] son sens doivent rester stables.
        return "OK RAS"
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if valeur < SEUIL_PSI_FORT:
        # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et
        # [PÉDAGOGIE] son sens doivent rester stables.
        return "! à surveiller"
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return "!! dérive forte"


# [PÉDAGOGIE] BLOC `drift_table` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : df_ref, df_cur, features, bins ; preuve : conserver bins,
# [PÉDAGOGIE] seuils, segmentation, fenêtre et valeurs calculées dans le rapport.
def drift_table(
    df_ref: pd.DataFrame,
    df_cur: pd.DataFrame,
    features=FEATURES_SURVEILLEES,
    bins: int = 10,
) -> pd.DataFrame:
    """Table de dérive : une ligne par feature (psi, ks_pvalue, verdict), tri PSI desc."""
    # Une ligne de sortie regroupe les deux mesures complémentaires et le
    # verdict lisible. On conserve le nom de feature pour alimenter ensuite les
    # tableaux, les fichiers CSV et les labels Prometheus.
    lignes = [
        {
            "feature": f,
            # Le PSI mesure l'ampleur du déplacement.
            "psi": psi(df_ref[f], df_cur[f], bins=bins),
            # KS répond à la question statistique « différence détectable ? ».
            "ks_pvalue": ks_pvalue(df_ref[f], df_cur[f]),
            # Le verdict transforme la valeur continue en consigne exploitable.
            "verdict": verdict_psi(psi(df_ref[f], df_cur[f], bins=bins)),
        }
        for f in features
    ]
    # Le tri décroissant fait remonter les features les plus préoccupantes.
    # `reset_index(drop=True)` fournit un index propre 0..n-1 après le tri.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return pd.DataFrame(lignes).sort_values("psi", ascending=False).reset_index(drop=True)


# [PÉDAGOGIE] BLOC `drift_report` — mesure de dérive : comparer la fenêtre courante à une
# [PÉDAGOGIE] référence sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : df_ref, df_cur, features, psi_threshold, bins ; preuve :
# [PÉDAGOGIE] conserver bins, seuils, segmentation, fenêtre et valeurs calculées dans le rapport.
def drift_report(
    df_ref: pd.DataFrame,
    df_cur: pd.DataFrame,
    features=FEATURES_SURVEILLEES,
    psi_threshold: float = SEUIL_PSI_FORT,
    bins: int = 10,
) -> dict:
    """Rapport machine (module 32) : {feature: {psi, ks_p, drift}} + verdict global.

    C'est le « rapport JSON maison » branché dans le flow après predict ;
    Evidently est l'alternative outillée (même contrat de sortie côté décision).
    """
    # On part de la table humaine validée plus haut afin de ne pas maintenir une
    # seconde implémentation des calculs PSI/KS dans la couche « rapport ».
    table = drift_table(df_ref, df_cur, features=features, bins=bins)

    # `to_dict("records")` transforme chaque ligne en dictionnaire. La
    # compréhension suivante construit un objet indexé par feature, plus facile
    # à consommer par une API ou une task Prefect qu'un DataFrame pandas.
    contenu = {
        r["feature"]: {
            # Arrondir le PSI stabilise l'affichage et allège le JSON ; la
            # décision booléenne est prise AVANT sur la valeur non arrondie.
            "psi": round(float(r["psi"]), 4),
            "ks_p": float(r["ks_pvalue"]),
            "drift": bool(r["psi"] > psi_threshold),
        }
        for r in table.to_dict("records")
    }
    # Le verdict global suit une logique « au moins une feature en dérive ».
    # `any(...)` s'arrête dès qu'un `True` est rencontré et renvoie un booléen.
    contenu["_global"] = {"drift": any(v["drift"] for v in contenu.values())}
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return contenu
