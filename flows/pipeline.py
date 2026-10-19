# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — flows/pipeline.py
# [PÉDAGOGIE] MODULE  — M29–M30 — orchestration, reprise et idempotence
# [PÉDAGOGIE] RÔLE    — Séparer le code métier des tâches observables et de leur ordre
# [PÉDAGOGIE]           d'exécution.
# [PÉDAGOGIE] THÉORIE — un flow décrit le graphe ; une task porte une unité observable et
# [PÉDAGOGIE]           relançable
# [PÉDAGOGIE]           • un retry convient à une erreur transitoire mais ne corrige pas une
# [PÉDAGOGIE]             logique fausse
# [PÉDAGOGIE]           • l'idempotence garantit qu'une reprise ne duplique pas les effets déjà
# [PÉDAGOGIE]             validés
# [PÉDAGOGIE] À VOIR  — Deux exécutions avec la même clé métier doivent produire un état final
# [PÉDAGOGIE]           cohérent et traçable.
# [PÉDAGOGIE] PIÈGE   — Relancer aveuglément une tâche à effets de bord peut créer doublons,
# [PÉDAGOGIE]           incohérences ou fausses preuves.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

"""Orchestration Prefect du pipeline InduSense (Sprint 3 — modules B9/B10 industrialisation).

POURQUOI UN ORCHESTRATEUR ?
    Jusqu'ici on lançait le pipeline à la main (`indusense train`). En production,
    un orchestrateur apporte ce que un script + cron ne donnent pas :
      - observabilité : chaque exécution (= "flow run") est tracée dans une UI,
        avec logs, durées, graphe des étapes ;
      - résilience : retries automatiques sur les étapes fragiles (ex : I/O) ;
      - planification : exécutions programmées (toutes les heures, cron...) ;
      - historique : on peut comparer les runs entre eux (dérive, régressions).

PRINCIPE DE CE FICHIER
    Le code métier reste dans src/indusense/ (loaders, features, modèle).
    Ici on ne fait QUE l'orchestration : chaque étape devient une `@task`,
    l'enchaînement devient un `@flow`. C'est la séparation orchestration / métier.

COMMANDES (depuis indusense-skeleton/, après `uv sync --extra dev`)
    Définir d'abord PREFECT_PROFILE=ephemeral comme indiqué dans le guide
    multiplateforme, puis lancer :
    uv run python flows/pipeline.py         # exécuter le pipeline avec le profil local
    uv run python flows/pipeline.py --serve # déploiement local optionnel (Ctrl+C pour arrêter)

Pas-à-pas complet (profil local et preuves à observer) :
FORMATION/GUIDE_MULTIPLATEFORME_APPRENANT.md
"""

# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Racine du projet (indusense-skeleton/), calculée depuis ce fichier :
# le flow marche quel que soit le dossier depuis lequel on le lance.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
ROOT = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if str(ROOT / "src") not in sys.path:  # filet de sécurité si `uv pip install -e .` n'a pas été fait
    sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
from prefect import flow, get_run_logger, task  # noqa: E402
from prefect.artifacts import create_markdown_artifact  # noqa: E402

# On réutilise le code métier existant : le flow n'invente RIEN, il orchestre.
from indusense.config import settings  # noqa: E402
from indusense.data.loaders import (  # noqa: E402
    build_dataset,
    load_incidents,
    load_pressure,
    load_temperature,
)
from indusense.features.temporal import add_temporal_features  # noqa: E402
from indusense.models.tabular import (  # noqa: E402
    load_model,
    predict_proba,
    save_model,
    select_features,
    train_model,
)

# ---------------------------------------------------------------------------
# Les TASKS : une task = une étape observable, rejouable, avec retry possible.
# Dans l'UI Prefect, chaque task apparaît comme un nœud du graphe d'exécution.
# ---------------------------------------------------------------------------


# [PÉDAGOGIE] BLOC `charger_sources` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : data_dir ; preuve : l'appelant doit pouvoir vérifier la sortie
# [PÉDAGOGIE] ou l'effet de bord annoncé.
@task(retries=2, retry_delay_seconds=5)
def charger_sources(data_dir: Path) -> pd.DataFrame:
    """Charge et harmonise les 3 sources réelles (CSV ';', TSV, incidents).

    `retries=2` : si la lecture échoue (fichier verrouillé, réseau...), Prefect
    retente 2 fois à 5 s d'intervalle AVANT de mettre le run en échec.
    C'est le genre d'étape I/O qu'on protège toujours en production.
    """
    logger = get_run_logger()  # logger Prefect : les messages remontent dans l'UI Cloud
    temp = load_temperature(data_dir / "capteurs_temperature.csv")
    pres = load_pressure(data_dir / "capteurs_pression.tsv")
    inc = load_incidents(data_dir / "releves_incidents.csv")
    ds = build_dataset(temp, pres, inc, window_hours=settings.incident_window_hours)
    logger.info(f"Dataset assemblé : {len(ds)} lignes, {ds['machine'].nunique()} machines")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return ds


# [PÉDAGOGIE] BLOC `construire_features` — unité de responsabilité : isoler un comportement
# [PÉDAGOGIE] nommable, testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : ds ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
@task
def construire_features(ds: pd.DataFrame) -> pd.DataFrame:
    """Ajoute lags + moyennes glissantes par machine (sans fuite temporelle)."""
    logger = get_run_logger()
    ds = add_temporal_features(ds).dropna()
    logger.info(f"Features temporelles : {ds.shape[1]} colonnes, {len(ds)} lignes exploitables")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return ds


# [PÉDAGOGIE] BLOC `entrainer_modele` — phase d'apprentissage : relier données, paramètres et
# [PÉDAGOGIE] modèle reproductible.
# [PÉDAGOGIE] CONTRAT — entrées : ds, out, data_dir ; preuve : conserver graine, split, métriques
# [PÉDAGOGIE] et artefact afin de pouvoir refaire l'expérience.
@task
def entrainer_modele(ds: pd.DataFrame, out: Path, data_dir: Path) -> dict:
    """Entraîne le RandomForest et persiste modèle + métadonnées (traçabilité)."""
    logger = get_run_logger()
    X, y = select_features(ds, settings.target_col), ds[settings.target_col]
    model = train_model(X, y, random_state=settings.random_seed)
    save_model(model, out)
    # Mêmes métadonnées que `indusense train` + provenance de l'orchestration :
    # en audit, on doit pouvoir dire QUI a produit CE modèle, QUAND, avec QUELLES données.
    meta = {
        "created_at": datetime.now(UTC).isoformat(),
        "package_version": "0.1.0",
        "random_seed": settings.random_seed,
        "target_col": settings.target_col,
        "features": list(X.columns),
        "n_train_rows": int(len(ds)),
        "panne_rate": round(float(y.mean()), 4),
        "dataset": str(data_dir),
        "orchestrator": "prefect",
    }
    (out.parent / "model_metadata.json").write_text(json.dumps(meta, indent=2))
    logger.info(f"Modèle entraîné ({len(ds)} lignes, panne={y.mean():.2%}) → {out}")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return meta


# [PÉDAGOGIE] BLOC `scorer_machines` — phase d'inférence ou d'évaluation : appliquer un contrat
# [PÉDAGOGIE] gelé à des observations nouvelles.
# [PÉDAGOGIE] CONTRAT — entrées : model_path, ds ; preuve : contrôler ordre des features, seuil,
# [PÉDAGOGIE] métriques et provenance du modèle.
@task
def scorer_machines(model_path: Path, ds: pd.DataFrame) -> dict[str, float]:
    """Score la dernière observation de chaque machine : P(panne) ∈ [0, 1]."""
    model = load_model(model_path)
    last = ds.groupby("machine").tail(1)  # 1 ligne par machine = son état le plus récent
    proba = predict_proba(model, select_features(last, settings.target_col))
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return {m: round(float(p), 3) for m, p in zip(last["machine"], proba, strict=False)}


# [PÉDAGOGIE] BLOC `publier_rapport` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : meta, scores ; preuve : l'appelant doit pouvoir vérifier la
# [PÉDAGOGIE] sortie ou l'effet de bord annoncé.
@task
def publier_rapport(meta: dict, scores: dict[str, float]) -> None:
    """Publie un rapport markdown : UI Cloud → onglet Artifacts du run.

    Un "artifact" Prefect = un livrable lisible attaché au run (rapport, tableau...).
    Intérêt : le métier consulte le résultat dans l'UI sans ouvrir de terminal.
    """
    seuil = settings.decision_threshold
    lignes = "\n".join(
        f"| {machine} | {p:.3f} | {'A RISQUE' if p >= seuil else 'ok'} |"
        for machine, p in sorted(scores.items())
    )
    create_markdown_artifact(
        key="rapport-indusense",  # clé stable : l'UI garde l'historique des versions
        description="Scoring maintenance prédictive InduSense",
        markdown=(
            f"# InduSense — rapport de run\n\n"
            f"- Entraînement : {meta['n_train_rows']} lignes, "
            f"taux de panne {meta['panne_rate']:.2%}\n"
            f"- Seuil de décision : {seuil}\n\n"
            f"| Machine | P(panne) | Statut |\n|---|---|---|\n{lignes}\n"
        ),
    )


# ---------------------------------------------------------------------------
# Le FLOW : le chef d'orchestre. Il enchaîne les tasks ; Prefect trace tout.
# ---------------------------------------------------------------------------


# [PÉDAGOGIE] BLOC `pipeline_indusense` — orchestration : rendre l'ordre, les dépendances et les
# [PÉDAGOGIE] points d'échec visibles.
# [PÉDAGOGIE] CONTRAT — entrées : data_dir ; preuve : chaque étape doit annoncer sa preuve avant
# [PÉDAGOGIE] que la suivante ne commence.
@flow(name="indusense-pipeline", log_prints=True)  # log_prints : les print() → logs du run
def pipeline_indusense(data_dir: str | None = None) -> dict[str, float]:
    """Pipeline complet : sources → features → entraînement → scoring → rapport.

    `data_dir` est un PARAMÈTRE de flow : dans l'UI Cloud on peut relancer le
    pipeline sur un autre jeu de données sans toucher au code (Deployments → Run).
    """
    dd = Path(data_dir) if data_dir else ROOT / "data" / "sample"
    out = ROOT / "artifacts" / "models" / "rf.joblib"

    ds = construire_features(charger_sources(dd))  # les tasks s'enchaînent comme des fonctions
    meta = entrainer_modele(ds, out, dd)
    scores = scorer_machines(out, ds)
    publier_rapport(meta, scores)

    a_risque = [m for m, p in scores.items() if p >= settings.decision_threshold]
    print(f"{len(scores)} machines scorées, {len(a_risque)} au-dessus du seuil : {a_risque}")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return scores


# [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le cas
# [PÉDAGOGIE] vrai et le cas faux.
if __name__ == "__main__":
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if "--serve" in sys.argv:
        # MODE DÉPLOIEMENT LOCAL : `serve()` enregistre un déploiement avec le profil
        # Prefect courant et transforme CE process en mini-worker qui exécute les runs.
        # Pour la formation, le profil doit rester `ephemeral`. Tant qu'il tourne
        # (Ctrl+C pour arrêter) :
        #   - exécution automatique toutes les heures (interval=3600 s) ;
        #   - logs et états restent observables localement.
        # Aucun compte Prefect Cloud n'est requis pour cette démo. En production réelle :
        # workers + work pools et backend d'orchestration validé par l'équipe.
        pipeline_indusense.serve(
            name="indusense-horaire",
            interval=3600,
            tags=["indusense", "sprint3"],
        )
    else:
        # MODE SIMPLE : une exécution immédiate avec le profil courant. Le parcours de
        # formation impose `ephemeral`; aucun `prefect cloud login` n'est nécessaire.
        pipeline_indusense()
