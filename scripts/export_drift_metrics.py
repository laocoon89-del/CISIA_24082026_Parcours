# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — scripts/export_drift_metrics.py
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
# scripts/export_drift_metrics.py — Exporteur Prometheus du TP drift (m33)
# Expose sur :9109/metrics : indusense_drift_psi{feature,fenetre},
# indusense_drift_ks_pvalue{...}, indusense_drift_rappel{fenetre}, etc.
# Relit reports/drift/*.csv toutes les 15 s (relancez evaluate_drift → MAJ).
# Prometheus (stack compose du repo) le scrappe via host.docker.internal:9109
# (job « indusense-drift » ajouté dans monitoring/prometheus.yml).
# Usage : uv run python scripts/export_drift_metrics.py
# =============================================================================
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

# `prometheus_client` est une dépendance pédagogique optionnelle. Le message
# d'erreur indique immédiatement la commande de correction au lieu de laisser
# Python afficher une longue trace d'import difficile à interpréter en atelier.
# [PÉDAGOGIE] ERREUR — cette frontière distingue le chemin nominal de la stratégie explicite de
# [PÉDAGOGIE] récupération.
try:
    from prometheus_client import Gauge, start_http_server
except ImportError:
    # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
    # [PÉDAGOGIE] suivantes.
    raise SystemExit(
        "prometheus-client manquant → uv add prometheus-client "
        "(ou pip install prometheus-client)"
    ) from None

# `RACINE` part de ce fichier pour retrouver le dépôt, indépendamment du dossier
# courant du terminal. `RP` est le répertoire observé par l'exporteur.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RACINE = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
RP = RACINE / "reports" / "drift"

# Une Gauge Prometheus représente une valeur qui peut monter OU descendre. C'est
# le bon type pour un PSI, une p-value ou un rappel recalculé à chaque fenêtre.
# Les labels évitent de créer un nom de métrique différent par feature/fenêtre :
# une seule série logique est découpée par dimensions interrogeables en PromQL.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
PSI = Gauge(
    "indusense_drift_psi", "PSI par feature vs référence", ["feature", "fenetre", "reference"]
)
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
KSP = Gauge("indusense_drift_ks_pvalue", "p-value KS", ["feature", "fenetre", "reference"])

# `MET` fabrique six gauges de même structure. La clé Python (`rappel`, etc.)
# correspond exactement au nom de colonne produit par evaluate_drift.py.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
MET = {
    c: Gauge(f"indusense_drift_{c}", f"{c} au seuil gelé", ["fenetre"])
    for c in ("rappel", "precision", "taux_alerte", "taux_panne", "pr_auc", "roc_auc")
}


# Relit les preuves CSV et rafraîchit toutes les gauges connues.
#
# La fonction ne lance aucun calcul de drift : elle expose uniquement les
# preuves déjà produites par `evaluate_drift.py`. Cette séparation évite que le
# monitoring change les résultats qu'il est censé observer.
#
# SORTIE : un couple `(nombre_de_tables_psi, nombre_de_lignes_de_suivi)` utilisé
# pour la preuve lisible affichée dans le terminal de l'exporteur.
# [PÉDAGOGIE] BLOC `publier` — unité de responsabilité : isoler un comportement nommable, testable
# [PÉDAGOGIE] et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : l'appelant doit pouvoir
# [PÉDAGOGIE] vérifier la sortie ou l'effet de bord annoncé.
def publier() -> tuple[int, int]:

    # Compteur de fichiers chargés, utile pour détecter immédiatement un dossier
    # vide ou un motif de nommage qui ne correspondrait plus au producteur.
    n_psi = 0

    # Exemple de nom attendu : `psi_f2_ref-normale.csv`. Le glob n'ouvre que les
    # preuves conformes à cette convention et ignore les autres fichiers.
    # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur un
    # [PÉDAGOGIE] invariant stable.
    for f in RP.glob("psi_f*_ref-*.csv"):
        # `stem` retire l'extension. On reconstruit ensuite les deux dimensions
        # encodées dans le nom : fenêtre (`f2` -> `2`) et référence (`normale`).
        fen = f.stem.split("_")[1][1:]
        ref = f.stem.split("ref-")[1]

        # Chaque ligne correspond à une feature. `labels(...).set(...)` crée ou
        # met à jour la série Prometheus identifiée par ces trois labels.
        # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur
        # [PÉDAGOGIE] un invariant stable.
        for _, r in pd.read_csv(f).iterrows():
            PSI.labels(feature=r["feature"], fenetre=fen, reference=ref).set(float(r["psi"]))
            KSP.labels(feature=r["feature"], fenetre=fen, reference=ref).set(float(r["ks_pvalue"]))
        n_psi += 1

    # Le second jeu de métriques vient du journal consolidé : une ligne par
    # fenêtre/référence avec les performances métier au seuil gelé.
    n_eval = 0
    suivi = RP / "suivi_fenetres.csv"
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if suivi.exists():
        # La fenêtre est forcée en texte pour conserver aussi la valeur
        # « janvier » et produire des labels homogènes.
        df = pd.read_csv(suivi, dtype={"fenetre": str})
        # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner sur
        # [PÉDAGOGIE] un invariant stable.
        for _, r in df.iterrows():
            # On parcourt le contrat `MET`. Le test `if c in r` rend l'exporteur
            # tolérant à un ancien CSV qui ne contiendrait pas encore une
            # métrique ajoutée plus tard : les autres gauges restent publiées.
            # [PÉDAGOGIE] ITÉRATION — appliquer la même règle à chaque élément permet de raisonner
            # [PÉDAGOGIE] sur un invariant stable.
            for c, g in MET.items():
                # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire
                # [PÉDAGOGIE] séparément le cas vrai et le cas faux.
                if c in r:
                    g.labels(fenetre=str(r["fenetre"])).set(float(r[c]))
        n_eval = len(df)

    # Ces nombres ne sont pas des métriques métier ; ils servent seulement au
    # retour de fonction et à la ligne de diagnostic du terminal.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return n_psi, n_eval


# Démarre le serveur HTTP Prometheus et sa boucle de rafraîchissement.
# [PÉDAGOGIE] BLOC `main` — orchestration : rendre l'ordre, les dépendances et les points d'échec
# [PÉDAGOGIE] visibles.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : chaque étape doit annoncer
# [PÉDAGOGIE] sa preuve avant que la suivante ne commence.
def main() -> None:
    # argparse produit automatiquement `--help` et vérifie les types. Le port
    # 9109 évite les ports déjà utilisés par l'API (8000) et Prometheus (9090).
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9109)

    # Un intervalle flottant permet aussi des boucles très courtes en test. En
    # animation, 15 s suffit pour voir apparaître un nouveau rapport rapidement.
    ap.add_argument("--intervalle", type=float, default=15.0)

    # `--une-fois` sert aux contrôles automatisés : publication, preuve, arrêt.
    ap.add_argument("--une-fois", action="store_true")
    args = ap.parse_args()

    # `start_http_server` lance en arrière-plan un petit serveur qui expose le
    # registre global des métriques sur `/metrics`. La boucle ci-dessous peut
    # donc continuer à mettre les gauges à jour pendant que Prometheus scrape.
    start_http_server(args.port)
    print(f"Exporteur drift InduSense : http://localhost:{args.port}/metrics")

    # La boucle relit les CSV au lieu de mettre les résultats en cache : relancer
    # l'évaluation d'une fenêtre devient visible sans redémarrer l'exporteur.
    # [PÉDAGOGIE] BOUCLE — la condition de poursuite doit progresser vers l'arrêt et rester
    # [PÉDAGOGIE] observable.
    while True:
        n_psi, n_eval = publier()
        print(f"  publié : {n_psi} tables PSI · {n_eval} évaluations")
        # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément
        # [PÉDAGOGIE] le cas vrai et le cas faux.
        if args.une_fois:
            # Sortie déterministe pour les tests et les démonstrations courtes.
            break

        # La pause limite les lectures disque et le bruit dans le terminal.
        time.sleep(args.intervalle)


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    main()
