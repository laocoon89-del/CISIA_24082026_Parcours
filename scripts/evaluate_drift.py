# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — scripts/evaluate_drift.py
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
# scripts/evaluate_drift.py — Ronde de surveillance d'une fenêtre (m31)
# Table PSI/KS (module indusense.monitoring.drift) + métriques au seuil GELÉ.
# Usage : uv run python scripts/evaluate_drift.py --fenetre 1 [--reference normale]
# =============================================================================
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

from indusense.monitoring.drift import drift_table

# Chemins centralisés : le script fonctionne depuis VS Code, PowerShell, zsh ou
# bash même si le terminal n'est pas positionné exactement à la racine du dépôt.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
DRIFT = RACINE / "data" / "drift"


# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    # ---------------------------------------------------------------------
    # 1. Lire les choix de la personne qui lance la ronde de surveillance.
    # ---------------------------------------------------------------------
    ap = argparse.ArgumentParser()

    # `choices` transforme une faute de frappe en message d'aide immédiat au
    # lieu de produire plus tard un obscur « fichier introuvable ».
    ap.add_argument("--fenetre", required=True, choices=["1", "2", "3", "janvier"])

    # Trois références permettent de montrer qu'un verdict de drift dépend du
    # contexte choisi : régime normal, haute charge ou train historique complet.
    ap.add_argument("--reference", default="normale", choices=["normale", "haute", "train"])

    # Le filtre machine est facultatif : sans lui, on évalue toute la flotte.
    ap.add_argument("--machine", default=None)
    args = ap.parse_args()

    # ---------------------------------------------------------------------
    # 2. Charger référence et fenêtre courante avec une correspondance explicite.
    # ---------------------------------------------------------------------
    # Ce dictionnaire évite d'éparpiller des `if/elif` et rend visible le contrat
    # entre le nom pédagogique de la référence et le fichier réellement lu.
    fic = {
        "normale": "reference_normale.csv",
        "haute": "reference_haute.csv",
        "train": "reference.csv",
    }
    df_ref = pd.read_csv(DRIFT / fic[args.reference])
    df_cur = pd.read_csv(DRIFT / f"fenetre_{args.fenetre}.csv")

    # Si une machine est fournie, le MÊME filtre s'applique aux deux côtés de la
    # comparaison. Comparer une machine à toute la flotte répondrait à une autre
    # question et pourrait créer un faux signal de dérive.
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if args.machine:
        df_ref, df_cur = (
            df_ref[df_ref["machine"] == args.machine],
            df_cur[df_cur["machine"] == args.machine],
        )

    # ---------------------------------------------------------------------
    # 3. Mesurer le covariate drift, puis préparer uniquement l'AFFICHAGE.
    # ---------------------------------------------------------------------
    table = drift_table(df_ref, df_cur)

    # `aff` est une copie : on y convertit les nombres en chaînes joliment
    # formatées sans dégrader les vraies valeurs numériques qui seront écrites
    # dans le CSV et utilisées par Prometheus.
    aff = table.copy()
    aff["psi"] = aff["psi"].map(lambda v: f"{v:.3f}")
    aff["ks_pvalue"] = aff["ks_pvalue"].map(lambda v: f"{v:.2e}")
    print(
        f"\n=== PSI/KS fenêtre {args.fenetre} vs référence {args.reference}"
        f"{' · ' + args.machine if args.machine else ''} ==="
    )
    print(aff.to_string(index=False))

    # ---------------------------------------------------------------------
    # 4. Évaluer le modèle gelé avec le contrat sauvegardé à l'entraînement.
    # ---------------------------------------------------------------------
    # Le modèle et sa carte doivent voyager ensemble. La carte fournit l'ordre
    # exact des features et, surtout, le seuil métier choisi sur la validation.
    modele = joblib.load(RACINE / "artifacts" / "drift_model.joblib")
    carte = json.loads((RACINE / "artifacts" / "drift_threshold.json").read_text(encoding="utf-8"))

    # On produit des probabilités continues, puis on applique le seuil GELÉ.
    # Il serait méthodologiquement faux de réoptimiser ce seuil sur chaque
    # fenêtre courante : cela masquerait la dégradation en production.
    proba = modele.predict_proba(df_cur[carte["features"]])[:, 1]
    y = df_cur["panne_v1"].to_numpy()
    yp = (proba >= carte["seuil"]).astype(int)

    # Ordre scikit-learn : TN, FP, FN, TP. Les FN sont ici particulièrement
    # coûteux car ils représentent des pannes non signalées à la maintenance.
    tn, fp, fn, tp = confusion_matrix(y, yp).ravel()

    # Le dictionnaire `m` est volontairement composé de types Python simples :
    # il pourra être converti sans surprise en une ligne CSV ou en JSON.
    m = {
        "fenetre": args.fenetre,
        "reference": args.reference,
        "n": int(len(y)),
        "taux_panne": float(y.mean()),
        "taux_alerte": float(yp.mean()),
        "rappel": tp / (tp + fn) if tp + fn else 0.0,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "pr_auc": float(average_precision_score(y, proba)),
        "roc_auc": float(roc_auc_score(y, proba)),
        "fn": int(fn),
        "tp": int(tp),
    }
    print(f"\n=== Modèle au seuil gelé {carte['seuil']} ===")
    print(
        f"  panne réelle {m['taux_panne']:.2%} · alerte {m['taux_alerte']:.2%} · "
        f"rappel {m['rappel']:.3f} · précision {m['precision']:.3f} · "
        f"ROC {m['roc_auc']:.3f} · FN={fn}"
    )

    # ---------------------------------------------------------------------
    # 5. Écrire les preuves de façon idempotente.
    # ---------------------------------------------------------------------
    # Le répertoire est créé si nécessaire. Le tableau PSI/KS garde une preuve
    # détaillée par feature et par couple fenêtre/référence.
    rp = RACINE / "reports" / "drift"
    rp.mkdir(parents=True, exist_ok=True)
    table.to_csv(rp / f"psi_f{args.fenetre}_ref-{args.reference}.csv", index=False)

    # `suivi_fenetres.csv` est un journal compact destiné aux dashboards. Avant
    # d'ajouter la nouvelle ligne, on retire l'ancienne ligne portant la même
    # clé (fenêtre + référence). Une relance met donc à jour au lieu de dupliquer.
    suivi = rp / "suivi_fenetres.csv"
    ligne = pd.DataFrame([m])
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if suivi.exists():
        # `dtype={"fenetre": str}` préserve « janvier » et empêche pandas de
        # traiter différemment les fenêtres numériques et textuelles.
        old = pd.read_csv(suivi, dtype={"fenetre": str})
        old = old[~((old["fenetre"] == m["fenetre"]) & (old["reference"] == m["reference"]))]
        ligne = pd.concat([old, ligne], ignore_index=True)

    # `index=False` évite d'ajouter une colonne technique sans sens métier.
    ligne.to_csv(suivi, index=False)


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
