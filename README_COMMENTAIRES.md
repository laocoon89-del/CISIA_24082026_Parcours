# Repo CISIA_24082026 — référence commentée

Ce document accompagne le repo `thomasfesq/CISIA_24082026`.
Objectif pédagogique : qu'un apprenant puisse lire **chaque fichier** et comprendre
*ce que fait le code* **et** *pourquoi*, sans connaissance préalable du projet.

> Cette référence est à ouvrir lorsque le formateur le demande, après la phase de conception ou
> d'enquête. Elle sert de filet de sécurité et de support de relecture, pas de raccourci à recopier.

> ✅ **Les ajouts pédagogiques de la session ne modifient pas le comportement.**
> Ils utilisent uniquement des commentaires `#` : aucune instruction Python,
> constante, signature ou dépendance n'est changée. La preuve actuelle est
> `git diff --check`, zéro ligne exécutable ajoutée/retirée et **32 tests verts**.

## Comment t'en servir

- **Pour lire/apprendre** : ouvre les fichiers dans cet ordre conseillé.
- **Pour les utiliser** : tu peux recopier ces fichiers par-dessus ceux de ton repo
  (les commentaires ne changent rien à l'exécution). À toi de voir si tu veux garder
  un repo de prod épuré ou cette version pédagogique.

## Légende des commentaires pédagogiques

Les nouveaux fichiers suivent autant que possible la même grille de lecture :

- **RÔLE / POURQUOI** : la responsabilité du fichier et la raison du choix ;
- **ENTRÉE / SORTIE** : ce qui arrive dans un bloc et ce qui doit en ressortir ;
- **À OBSERVER** : la preuve visible dans le terminal, un CSV, l'API ou Grafana ;
- **PIÈGE** : l'erreur fréquente et son effet, sans simplement donner la réponse ;
- **À COMPLÉTER** : le contrat d'un exercice laissé volontairement ouvert.

On ne commente pas une syntaxe évidente pour la répéter mot à mot. On explique
prioritairement la causalité, les invariants, les choix MLOps et les preuves.
Sur une branche d'exercice, un commentaire ne doit jamais dévoiler une solution
qui n'a pas encore été construite. Sur `J6-gameday`, les commentaires restent
neutres afin de ne pas révéler les pannes à diagnostiquer.

## Ordre de lecture conseillé

1. `pyproject.toml` — la carte d'identité du projet (dépendances, outils, commandes).
2. `src/indusense/config.py` — les réglages centraux (chemins, graine, cible).
3. `src/indusense/data/loaders.py` — charger et nettoyer les données brutes, fabriquer la cible `panne` (le `merge_asof`).
4. `src/indusense/features/temporal.py` — fabriquer les features `lag`/`rolling` **sans fuite temporelle**.
5. `src/indusense/models/tabular.py` — le modèle (RandomForest), entraînement, prédiction, sauvegarde.
6. `src/indusense/cli.py` — les 4 commandes `indusense` (check-data / build-gold / train / predict).
7. `tests/` — ce que chaque test garantit (anti-fuite, normalisation, isolation par machine).
8. `scripts/demo_versioning.py` — la démo DVC + MLflow (versionner données + modèle).
9. `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `Makefile`, `.gitignore`, `.env.example` — l'outillage qualité/CI.

## Fichiers fortement commentés

| Catégorie | Fichiers |
|---|---|
| Package | `config.py`, `cli.py`, `data/loaders.py`, `features/temporal.py`, `models/tabular.py` + les `__init__.py` |
| Tests | `test_loaders.py`, `test_package.py`, `test_temporal.py`, `test_api.py`, `test_security.py`, `test_drift_monitoring.py` |
| Scripts | `demo_versioning.py`, `train_drift_model.py`, `evaluate_drift.py`, `export_drift_metrics.py`, `check_env_macos.sh`, `check_env_windows.ps1` |
| Drift | `monitoring/drift.py` : PSI, KS, seuils, contrat machine et limites d'interprétation |
| Config/CI | `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `Makefile`, `.gitignore`, `.env.example` |

## Non inclus (volontairement, car non « commentables »)

Les **données** (`data/**` : CSV/TSV/SQL), le **modèle binaire** (`artifacts/models/rf.joblib`),
le **verrou de dépendances** (`uv.lock`) et les **README**/markdown déjà rédigés restent ceux du
repo d'origine, inchangés. Ils sont déjà présents dans ton clone de `CISIA_24082026`.

---

*Sprint 3 CISIA « Industrialisation & déploiement » · InduSense 4.0 · AELION*

---

## ⭐ Mise à jour — RÉFÉRENCE COMPLÈTE & commentée (modules 23 → 34)

Le dépôt contient aussi une **référence complète commentée** que les étudiants peuvent étudier de bout en bout après le signal du formateur :

- **`src/indusense/api/`** — l'API FastAPI : `schemas.py` (contrat I/O Pydantic), `security.py` (clé API 401, rate limit 429, taille 413), `model_store.py` (chargement du modèle), `main.py` (`/health`, `/ready`, `/predict-tabular`, `/predict-image`, métriques Prometheus). *(modules 25-26)*
- **`Dockerfile`** + **`.dockerignore`** — image multi-stage, non-root, Variante A. *(module 27)*
- **`docker-compose.yml`** — stack api + PostgreSQL + Prometheus + Grafana. *(module 28)*
- **`monitoring/prometheus.yml`** — scrape de `/metrics`. *(modules 33-34)*
- **`tests/test_api.py`**, **`tests/test_security.py`** — vérifient 200/401/422/413/429 + normalisation `M-7`→`MACH-07`.
- **`payload.json`** — exemple de requête pour `/predict-tabular`.
- `pyproject.toml` complété (fastapi, uvicorn, prometheus-instrumentator, prefect, sqlalchemy, psycopg, scipy, evidently, mlflow…), `config.py` (+ `api_key`, `decision_threshold`), `Makefile` (cible `serve`).

**Hygiène git** : `mlruns/` et `mlflow.db` (artefacts de démo MLflow) sortis du suivi git et ajoutés au `.gitignore`.

✅ **Vérifié** : la suite courante donne **`pytest` = 32 tests verts**
(package, données, temporalité, API, sécurité et drift). Ruff, Black et
`from indusense.api.main import app` réussissent également.

> Note : `flows/pipeline.py` sert de référence Prefect pour les modules 29-30.
> Les scripts drift et l'exporteur Prometheus deviennent des références de
> lecture aux modules 31-34, seulement après le signal du formateur.

---

## 🧹 Instantané propre pour la session du 24/08/2026

Le dépôt public est un instantané sans historique de la cohorte précédente, sans environnement local
ni cache. Les données pédagogiques et le modèle de démonstration nécessaires sont livrés ; aucun
`dvc pull` n'est requis. Régénère l'environnement avec
`uv sync --frozen --extra dev --extra mlops`.

> Le dépôt est déjà versionné. Après le clone, crée seulement ta branche de travail :
> ```
> cd CISIA_24082026_Parcours
> git switch -c prenom-nom
> ```

---

## 🧭 Parcours de lecture par journée (J2 → J6)

Pour t'y retrouver, voici **quels fichiers ouvrir chaque jour** (dans l'ordre) :

- **J2 — API & sécurité (modules 25-26).** `src/indusense/api/schemas.py` (le **contrat** d'entrée/sortie, Pydantic) → `src/indusense/api/security.py` (clé d'API **401**, rate limit **429**, taille **413**) → `src/indusense/api/model_store.py` (chargement du modèle) → `src/indusense/api/main.py` (les routes `/health`, `/ready`, `/predict-tabular`) → `tests/test_api.py` + `tests/test_security.py` (ce qui est garanti). **Démarrer :** `uv run uvicorn indusense.api.main:app --reload`, puis ouvrir **http://localhost:8000/docs**.
- **J3 — Conteneurisation (27-28).** `Dockerfile` (multi-stage, non-root) → `.dockerignore` → `docker-compose.yml` (api + PostgreSQL + Prometheus + Grafana). **Tester :** `docker build -t indusense .` puis `docker compose up`.
- **J4 — Orchestration (29-30).** `flows/pipeline.py` montre la séparation entre tâches Prefect et code métier ; `scripts/demo_prefect_idempotence.py` rend visible l'**idempotence** (upsert, pas de doublon). Ne l'ouvre qu'au jalon correspondant.
- **J5 — Data drift (31-32).** `src/indusense/monitoring/drift.py` porte PSI/KS ; `scripts/train_drift_model.py` gèle le seuil ; `scripts/evaluate_drift.py` compare les fenêtres. Clé : distinguer dérive des **entrées** et dégradation **métier**.
- **J6 — Observabilité (33-34) + Game Day.** `monitoring/prometheus.yml` (scrape de `/metrics`) → l'instrumentation dans `api/main.py` → dashboards **Grafana** (TP). Termine par le **Game Day** (fiche dédiée) : dérive → alerte → runbook → correction.

> Rappel : le dépôt est abondamment commenté, mais les commentaires sont
> volontairement progressifs. En cas de doute sur un mot, garde la fiche
> **Prérequis & glossaire** à côté de toi et suis l'ordre de lecture du jalon.
