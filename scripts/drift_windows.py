# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — scripts/drift_windows.py
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
# scripts/drift_windows.py — Fenêtres de dérive pour le TP m31 (fil rouge)
# -----------------------------------------------------------------------------
# Construit, À PARTIR DES LOADERS OFFICIELS du repo (§95 : normalize, fuseaux,
# merge_asof ±90 min) : une RÉFÉRENCE (aoû→déc 2025) + 4 fenêtres de production
# (témoin, capteur +8 °C, concept drift, campagne haute charge de janvier),
# écrites dans data/drift/.
#
# ⚠ CIBLE CONTRÔLÉE (panne_v1 / panne_v2), mesure à l'appui : les incidents du
# CSV réel ne sont pas corrélés aux capteurs (ROC ≈ 0,56 en validation
# TEMPORELLE, ≈ prévalence en PR-AUC — la modélisation sérieuse se fait sur le
# Gold). On garde donc les X 100 % réels (régimes, NaN, campagnes) et on tire
# la panne selon une règle physique FIGÉE (seeds 42/4242) :
#   v1 : emballement RELATIF (delta 6 h de température ↑, delta pression ↓,
#        normalisés par l'écart-type 24 h de la machine) ;
#   v2 : signes inversés (« post-rétrofit » : pannes en sous-régime) → concept.
# La colonne `panne` (incidents réels) est conservée pour comparaison.
#
# Usage : uv run python scripts/drift_windows.py   (source : data/drift_source, flux complet)
# =============================================================================
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from indusense.data.loaders import build_dataset, load_incidents, load_pressure, load_temperature
from indusense.features.temporal import add_temporal_features

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
B0 = -3.75  # calé pour ~5 % de panne (proche des 4,78 % du flux réel)


# [PÉDAGOGIE] BLOC `_sig` — unité de responsabilité : isoler un comportement nommable, testable et
# [PÉDAGOGIE] réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : x ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def _sig(x):
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return 1.0 / (1.0 + np.exp(-x))


# [PÉDAGOGIE] BLOC `enrichir` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : df ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def enrichir(df: pd.DataFrame) -> pd.DataFrame:
    """Features temporelles officielles + extensions anti-fuite (delta6, std24)."""
    df = add_temporal_features(df)  # lags 1/3/6 + roll 3/6 mean (m9, sans fuite)
    df = df.sort_values(["machine", "timestamp"]).reset_index(drop=True)
    g = df.groupby("machine", group_keys=False)
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for col in ("temperature", "pressure_bar"):
        # même principe anti-fuite que temporal.py : shift(1) AVANT rolling
        base = g[col].shift(1)
        df[f"{col}_std24"] = (
            base.groupby(df["machine"]).rolling(24, min_periods=12).std().reset_index(drop=True)
        )
        df[f"{col}_delta6"] = df[col] - df[f"{col}_roll6_mean"]
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return df


# [PÉDAGOGIE] BLOC `tirer_cibles` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : df ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def tirer_cibles(df: pd.DataFrame) -> pd.DataFrame:
    zt = (df["temperature_delta6"] / df["temperature_std24"].clip(lower=0.5)).clip(-4, 4)
    zp = (df["pressure_bar_delta6"] / df["pressure_bar_std24"].clip(lower=0.5)).clip(-4, 4)
    r1, r2 = np.random.default_rng(42), np.random.default_rng(4242)
    df["panne_v1"] = (r1.random(len(df)) < _sig(B0 + 1.3 * zt - 1.0 * zp)).astype(int)
    df["panne_v2"] = (r2.random(len(df)) < _sig(B0 - 1.3 * zt + 1.0 * zp)).astype(int)
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return df


# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--datas",
        type=Path,
        default=RACINE / "data" / "drift_source",
        help="flux capteurs COMPLET du fil rouge (data/raw = jeu de démarrage réduit)",
    )
    args = ap.parse_args()

    temp = load_temperature(args.datas / "capteurs_temperature.csv")
    pres = load_pressure(args.datas / "capteurs_pression.tsv")
    inc = load_incidents(args.datas / "releves_incidents.csv")
    s = build_dataset(temp, pres, inc)  # jointure §95 + cible réelle `panne`
    s = enrichir(s)
    colonnes_f = [c for c in s.columns if c not in ("machine", "timestamp", "panne")]
    s = s.dropna(subset=colonnes_f).reset_index(drop=True)
    s = tirer_cibles(s)
    print(
        f"Jointure + features : {len(s)} lignes · panne_v1 {s['panne_v1'].mean():.2%} "
        f"· panne_v2 {s['panne_v2'].mean():.2%} · panne réelle {s['panne'].mean():.2%}"
    )

    mois = s["timestamp"].dt.to_period("M").astype(str)
    dd = RACINE / "data" / "drift"
    dd.mkdir(parents=True, exist_ok=True)

    ref = s[s["timestamp"] < "2026-01-01"]
    fev = s[mois == "2026-02"]
    janv = s[mois == "2026-01"]

    ref.to_csv(dd / "reference.csv", index=False)
    s[mois.isin(["2025-09", "2025-11", "2025-12"])].to_csv(
        dd / "reference_normale.csv", index=False
    )
    s[mois == "2025-10"].to_csv(dd / "reference_haute.csv", index=False)
    fev.to_csv(dd / "fenetre_1.csv", index=False)
    f2 = fev.copy()
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for c in (
        "temperature",
        "temperature_lag1",
        "temperature_lag3",
        "temperature_lag6",
        "temperature_roll3_mean",
        "temperature_roll6_mean",
    ):
        f2[c] = f2[c] + 8.0  # le capteur ment de +8 °C ; la réalité (labels) ne change pas
    f2.to_csv(dd / "fenetre_2.csv", index=False)
    f3 = fev.copy()
    f3["panne_v1"] = f3["panne_v2"]  # le monde a changé (concept) ; X strictement identique
    f3.to_csv(dd / "fenetre_3.csv", index=False)
    janv.to_csv(dd / "fenetre_janvier.csv", index=False)

    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for nom in (
        "reference",
        "reference_normale",
        "reference_haute",
        "fenetre_1",
        "fenetre_2",
        "fenetre_3",
        "fenetre_janvier",
    ):
        n = sum(1 for _ in open(dd / f"{nom}.csv", encoding="utf-8")) - 1
        print(f"  data/drift/{nom}.csv : {n} lignes")


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
