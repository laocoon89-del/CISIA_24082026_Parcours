# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — FORMATION/EXERCICES/tp_drift_indusense/scripts/drift_lab.py
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

"""InduSense — Laboratoire de dérive : PSI + KS sur les capteurs réels.

Surveillance des 2 features capteurs (m31) : temperature, pressure_bar.
Spécificité InduSense vs PayGuard : la RÉFÉRENCE se choisit PAR RÉGIME
(normale = sept+nov+déc · haute = campagne d'octobre · train = tout 2025 mélangé),
et la table peut être segmentée PAR MACHINE (m31 §2.5).

Usage :
  python scripts/drift_lab.py --fenetre 1 --reference normale
  python scripts/drift_lab.py --fenetre janvier --reference normale   # fausse alerte de régime !
  python scripts/drift_lab.py --fenetre janvier --reference haute     # silence : même régime
  python scripts/drift_lab.py --fenetre 2 --reference normale --machine MACH-03
"""
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
DATA = RACINE / "data"
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RAPPORTS = RACINE / "reports"
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
FEATURES_SURVEILLEES = ["temperature", "pressure_bar"]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
SEUIL_PSI_SURVEILLER, SEUIL_PSI_FORT = 0.10, 0.25


# [PÉDAGOGIE] BLOC `psi` — mesure de dérive : comparer la fenêtre courante à une référence sans
# [PÉDAGOGIE] changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : ref, cur, bins ; preuve : conserver bins, seuils, segmentation,
# [PÉDAGOGIE] fenêtre et valeurs calculées dans le rapport.
def psi(ref, cur, bins: int = 10) -> float:
    """PSI, conventions m31 : bins figés sur la référence, +1e-6, bords ouverts ±inf.
    Les NaN (vraies données capteurs !) sont écartés feature par feature."""
    ref = np.asarray(pd.Series(ref).dropna(), dtype=float)
    cur = np.asarray(pd.Series(cur).dropna(), dtype=float)
    edges = np.histogram_bin_edges(ref, bins=bins)
    edges[0], edges[-1] = -np.inf, np.inf
    p_ref = np.histogram(ref, edges)[0] / len(ref) + 1e-6
    p_cur = np.histogram(cur, edges)[0] / len(cur) + 1e-6
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return float(np.sum((p_cur - p_ref) * np.log(p_cur / p_ref)))


# [PÉDAGOGIE] BLOC `ks_pvalue` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : ref, cur ; preuve : conserver bins, seuils, segmentation,
# [PÉDAGOGIE] fenêtre et valeurs calculées dans le rapport.
def ks_pvalue(ref, cur) -> float:
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return float(stats.ks_2samp(pd.Series(ref).dropna(), pd.Series(cur).dropna()).pvalue)


# [PÉDAGOGIE] BLOC `verdict_psi` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : v ; preuve : conserver bins, seuils, segmentation, fenêtre et
# [PÉDAGOGIE] valeurs calculées dans le rapport.
def verdict_psi(v: float) -> str:
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if v < SEUIL_PSI_SURVEILLER: return "OK RAS"
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if v < SEUIL_PSI_FORT: return "! à surveiller"
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return "!! dérive forte"


# [PÉDAGOGIE] BLOC `drift_table` — mesure de dérive : comparer la fenêtre courante à une référence
# [PÉDAGOGIE] sans changer la règle en cours de route.
# [PÉDAGOGIE] CONTRAT — entrées : df_ref, df_cur, features, bins ; preuve : conserver bins,
# [PÉDAGOGIE] seuils, segmentation, fenêtre et valeurs calculées dans le rapport.
def drift_table(df_ref, df_cur, features=FEATURES_SURVEILLEES, bins=10) -> pd.DataFrame:
    lignes = [{"feature": f,
               "psi": psi(df_ref[f], df_cur[f], bins=bins),
               "ks_pvalue": ks_pvalue(df_ref[f], df_cur[f]),
               "verdict": verdict_psi(psi(df_ref[f], df_cur[f], bins=bins))}
              for f in features]
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return pd.DataFrame(lignes).sort_values("psi", ascending=False).reset_index(drop=True)


# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fenetre", required=True, choices=["1", "2", "3", "janvier"])
    ap.add_argument("--reference", default="normale", choices=["normale", "haute", "train"])
    ap.add_argument("--machine", default=None, help="segmentation par machine, ex. MACH-03")
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()

    fic_ref = {"normale": "reference_normale.csv", "haute": "reference_haute.csv", "train": "reference.csv"}
    df_ref = pd.read_csv(DATA / fic_ref[args.reference])
    nom_f = f"fenetre_{args.fenetre}.csv"
    df_cur = pd.read_csv(DATA / nom_f)
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if args.machine:
        df_ref = df_ref[df_ref["machine"] == args.machine]
        df_cur = df_cur[df_cur["machine"] == args.machine]

    table = drift_table(df_ref, df_cur, bins=args.bins)
    RAPPORTS.mkdir(exist_ok=True)
    suffixe = f"_{args.machine}" if args.machine else ""
    table.to_csv(RAPPORTS / f"drift_f{args.fenetre}_ref-{args.reference}{suffixe}.csv", index=False)

    aff = table.copy()
    aff["psi"] = aff["psi"].map(lambda v: f"{v:.3f}")
    aff["ks_pvalue"] = aff["ks_pvalue"].map(lambda v: f"{v:.2e}")
    print(f"\n=== Fenêtre {args.fenetre} vs référence {args.reference}"
          f"{' · ' + args.machine if args.machine else ''} "
          f"({len(df_ref)} vs {len(df_cur)} relevés, {args.bins} bins) ===")
    print(aff.to_string(index=False))


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
