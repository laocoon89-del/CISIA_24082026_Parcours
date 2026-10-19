# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — FORMATION/EXERCICES/tp_drift_indusense/scripts/build_dataset.py
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

"""InduSense — Construction du jeu drift : jointure §95 + rolling anti-fuite + cible contrôlée.

Données CAPTEURS 100 % réelles (capteurs_temperature.csv, capteurs_pression.tsv, machine.sql),
jointes selon les conventions du snippet 95 (normalize_machine_id, merge_asof ±90 min).

⚠️ CIBLE CONTRÔLÉE (v1/v2), PAS les incidents du CSV : mesure faite (split TEMPOREL m8) —
les incidents de releves_incidents.csv ne sont pas corrélés aux capteurs (ROC ≈ 0,56, PR-AUC ≈
prévalence). C'est d'ailleurs pourquoi le parcours modélise sur le Gold. Ici, on garde les X réels
(régimes, campagnes oct/janv, NaN, fuseaux) et on tire la panne selon une règle physique connue :
  v1 (historique)  : emballement RELATIF — delta6h température ↑ et delta6h pression ↓ (fuite)
  v2 (post-rétrofit, concept drift) : signes inversés — pannes en sous-régime
Seeds figés (42 / 4242) → reproductible à l'identique.

Fenêtres produites (data/) :
  reference.csv        aoû→déc 2025, labels v1        → entraînement + référence drift « train »
  reference_normale.csv  sept+nov+déc 2025 (régime normal 39 °C ± 4)
  reference_haute.csv    octobre 2025 (campagne haute charge 82 °C ± 30)
  fenetre_1.csv        février 2026, labels v1        → témoin
  fenetre_2.csv        février 2026 + 8 °C capteur, labels v1  → covariate drift
  fenetre_3.csv        février 2026 (X identique à F1), labels v2 → concept drift
  fenetre_janvier.csv  janvier 2026 (campagne haute charge), labels v1 → leçon « référence par régime »

Usage : python scripts/build_dataset.py [--datas /chemin/vers/indusense/datas]
"""
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations
import argparse, re
from pathlib import Path
import numpy as np
import pandas as pd

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
_D = re.compile(r"(\d+)")

# [PÉDAGOGIE] BLOC `normalize_machine_id` — unité de responsabilité : isoler un comportement
# [PÉDAGOGIE] nommable, testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : raw ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def normalize_machine_id(raw: str) -> str:
    m = _D.search(str(raw))
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if not m: raise ValueError(f"machine_id sans numéro : {raw!r}")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return f"MACH-{int(m.group(1)):02d}"

# [PÉDAGOGIE] BLOC `charger_et_joindre` — unité de responsabilité : isoler un comportement
# [PÉDAGOGIE] nommable, testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : datas ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def charger_et_joindre(datas: Path) -> pd.DataFrame:
    t = pd.read_csv(datas / "capteurs_temperature.csv", sep=";")
    t["timestamp"] = pd.to_datetime(t["timestamp"])
    t["machine"] = t["machine_id"].map(normalize_machine_id)
    p = pd.read_csv(datas / "capteurs_pression.tsv", sep="\t")
    p["timestamp"] = pd.to_datetime(p["timestamp"], utc=True, format="mixed").dt.tz_localize(None)
    p["machine"] = p["machine_id"].map(normalize_machine_id)
    s = pd.merge_asof(
        t.sort_values("timestamp")[["timestamp", "machine", "temperature"]],
        p.sort_values("timestamp")[["timestamp", "machine", "pressure_bar"]],
        on="timestamp", by="machine", direction="nearest",
        tolerance=pd.Timedelta(minutes=90),
    ).dropna(subset=["pressure_bar"])
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return s.sort_values(["machine", "timestamp"]).reset_index(drop=True)

# [PÉDAGOGIE] BLOC `enrichir_rolling` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : s ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def enrichir_rolling(s: pd.DataFrame) -> pd.DataFrame:
    """Features rolling anti-fuite (m9) : shift(1) AVANT rolling, par machine."""
    g = s.groupby("machine", group_keys=False)
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for col in ["temperature", "pressure_bar"]:
        base = g[col].shift(1)
        s[f"{col}_moy6h"] = base.groupby(s["machine"]).rolling(6, min_periods=3).mean().reset_index(drop=True)
        s[f"{col}_moy24h"] = base.groupby(s["machine"]).rolling(24, min_periods=12).mean().reset_index(drop=True)
        s[f"{col}_std24h"] = base.groupby(s["machine"]).rolling(24, min_periods=12).std().reset_index(drop=True)
        s[f"{col}_delta6h"] = s[col] - s[f"{col}_moy6h"]
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return s

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
FEATURES_MODELE = ["temperature", "pressure_bar"] + [
    f"{c}_{k}" for c in ["temperature", "pressure_bar"] for k in ["moy6h", "moy24h", "std24h", "delta6h"]
]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
B0 = -3.75  # calé pour ~5 % de panne (proche des 4,78 % du flux réel)

# [PÉDAGOGIE] BLOC `_sig` — unité de responsabilité : isoler un comportement nommable, testable et
# [PÉDAGOGIE] réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : x ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def _sig(x): return 1.0 / (1.0 + np.exp(-x))

# [PÉDAGOGIE] BLOC `_scores_relatifs` — phase d'inférence ou d'évaluation : appliquer un contrat
# [PÉDAGOGIE] gelé à des observations nouvelles.
# [PÉDAGOGIE] CONTRAT — entrées : s ; preuve : contrôler ordre des features, seuil, métriques et
# [PÉDAGOGIE] provenance du modèle.
def _scores_relatifs(s):
    zt = (s["temperature_delta6h"] / s["temperature_std24h"].clip(lower=0.5)).clip(-4, 4)
    zp = (s["pressure_bar_delta6h"] / s["pressure_bar_std24h"].clip(lower=0.5)).clip(-4, 4)
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return zt, zp

# [PÉDAGOGIE] BLOC `tirer_labels` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : s ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
def tirer_labels(s: pd.DataFrame) -> pd.DataFrame:
    zt, zp = _scores_relatifs(s)
    rng1, rng2 = np.random.default_rng(42), np.random.default_rng(4242)
    s["panne_v1"] = (rng1.random(len(s)) < _sig(B0 + 1.3 * zt - 1.0 * zp)).astype(int)
    s["panne_v2"] = (rng2.random(len(s)) < _sig(B0 - 1.3 * zt + 1.0 * zp)).astype(int)
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return s

# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datas", type=Path, default=RACINE.parents[1] / "indusense" / "datas",
                    help="dossier des 4 fichiers sources InduSense")
    args = ap.parse_args()
    print(f"Sources : {args.datas}")
    s = charger_et_joindre(args.datas)
    print(f"Jointure merge_asof ±90 min : {len(s)} lignes (attendu 65 625)")
    s = enrichir_rolling(s)
    s = s.dropna(subset=FEATURES_MODELE).reset_index(drop=True)
    s = tirer_labels(s)
    print(f"Après rolling + dropna : {len(s)} lignes · panne v1 = {s['panne_v1'].mean():.2%} · v2 = {s['panne_v2'].mean():.2%}")

    mois = s["timestamp"].dt.to_period("M").astype(str)
    dd = RACINE / "data"; dd.mkdir(exist_ok=True)
    cols = ["timestamp", "machine"] + FEATURES_MODELE

    ref = s[s["timestamp"] < "2026-01-01"]
    ref[cols + ["panne_v1"]].rename(columns={"panne_v1": "panne_24h"}).to_csv(dd / "reference.csv", index=False)
    s[mois.isin(["2025-09", "2025-11", "2025-12"])][cols].to_csv(dd / "reference_normale.csv", index=False)
    s[mois == "2025-10"][cols].to_csv(dd / "reference_haute.csv", index=False)

    fev = s[mois == "2026-02"]; janv = s[mois == "2026-01"]
    fev[cols + ["panne_v1"]].rename(columns={"panne_v1": "panne_24h"}).to_csv(dd / "fenetre_1.csv", index=False)
    f2 = fev.copy()
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for c in ["temperature", "temperature_moy6h", "temperature_moy24h"]:
        f2[c] = f2[c] + 8.0   # le capteur ment de +8 °C ; la réalité (labels v1) est inchangée
    f2[cols + ["panne_v1"]].rename(columns={"panne_v1": "panne_24h"}).to_csv(dd / "fenetre_2.csv", index=False)
    fev[cols + ["panne_v2"]].rename(columns={"panne_v2": "panne_24h"}).to_csv(dd / "fenetre_3.csv", index=False)
    janv[cols + ["panne_v1"]].rename(columns={"panne_v1": "panne_24h"}).to_csv(dd / "fenetre_janvier.csv", index=False)

    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for f in ["reference", "reference_normale", "reference_haute", "fenetre_1", "fenetre_2", "fenetre_3", "fenetre_janvier"]:
        df = pd.read_csv(dd / f"{f}.csv")
        extra = f" · panne {df['panne_24h'].mean():.2%}" if "panne_24h" in df else ""
        print(f"  data/{f}.csv : {len(df)} lignes{extra}")

# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
