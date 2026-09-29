# Stratégie de versioning - InduSense

Branche `ludovic-bourreau`, M24. Preuves DVC relevées le 28/09/2026 ; runs MLflow rejoués le 29/09/2026 sur le serveur **du repo** (commit `769b4df`, après fusion du jalon 03).

| Objet | Source de vérité | Identifiant/version | Stockage | Preuve de restauration |
|---|---|---|---|---|
| Code | Git, branche `ludovic-bourreau` | commit `769b4df` (code des 2 runs, tag MLflow `mlflow.source.git.commit`) | Git | `git switch --detach 769b4df` puis `uv sync --frozen --extra dev --extra mlops` |
| Données | pointeur `data/gold/gold_dataset.csv.dvc` | md5 `637be8d3825023160de0980761c9a9e8` (287 704 o) | DVC, remote `localstore` = `../dvc-store` | suppression locale → `dvc pull` → md5 recalculée identique → `dvc status` : *up to date* |
| Modèle | pointeur `artifacts/models/rf.joblib.dvc` + `model_metadata.json` + MLflow `indusense-rf` | md5 `2779890061870d6a08d6efdf733da094` (4 965 817 o) ; MLflow v1 et v2 (tableau ci-dessous) | DVC + MLflow | `dvc pull` (pointeur) ; `models:/indusense-rf/2` (MLflow) |
| Secrets | `.env` local (non versionné), secrets GitHub Actions en CI | Jamais dans Git | `.env` ignoré (`.gitignore`) ; `.env.example` sans valeur | hook `gitleaks` actif : sentinelle AWS de démonstration bloquée (`leaks found: 1`) |

## Code

Toute modification passe par une PR. La PR doit avoir une CI verte : ruff, black, pytest, build.

- `.github/workflows/ci.yml` : job `quality` (Python 3.13, ruff, `black --check .`, pytest), puis job `build` (`needs: quality`, `uv build`, artefact `indusense-wheel`). Commit `0db09d9`.
- Hooks locaux `pre-commit` et `pre-push` installés : ruff `--fix`, black, gitleaks.
- Environnement figé : `uv.lock` inchangé, toujours `uv sync --frozen` / `uv run --frozen`. Jamais `uv add` ni `uv lock`.

## Données

Les datasets volumineux sont suivis avec DVC. Git conserve les pointeurs, pas les fichiers lourds.

- Gold : `data/gold/gold_dataset.csv.dvc`, md5 `637be8d3…` (tag MLflow `gold_md5=637be8d38250` sur les deux runs).
- Remote par défaut `localstore` → `../dvc-store` (hors du repo). `dvc push` : 2 fichiers. `dvc status` : *Data and pipelines are up to date.*
- Commit des pointeurs : `2c973e0`.

## Modèle

Les artefacts modèle sont accompagnés de `model_metadata.json`. Promotion : Candidate -> Staging -> Production -> Archived.

Deux runs MLflow comparables (serveur du repo `http://127.0.0.1:5001`, backend `sqlite:///mlflow.db` du repo, expérience `indusense-maintenance` id 1 ; même code, même Gold, mêmes hyperparamètres ; **seul le split change**) :

| | Run 1 | Run 2 (artefact final) |
|---|---|---|
| `run_id` | `3d425d2081014f17856b3cc0d3eacea2` | `b022d07a181246dda313e29493fb2052` |
| Version registre `indusense-rf` | **v1** (sans stage) | **v2** (sans stage) |
| Split | `stratifie (fuite)` | `temporel/machine` |
| Début (UTC) | 29/09/2026 07:55:38 | 29/09/2026 07:55:55 |
| Paramètres | `n_estimators=200`, `random_state=42`, `threshold=0.975`, `test_size=0.2`, `n_features=12` | identiques |
| n_train / n_test | 1516 / 380 | 1516 / 380 |
| Taux de panne test | 0,1053 | 0,1316 |
| PR-AUC | 0,4336 | 0,1036 |
| ROC-AUC | 0,8531 | 0,2475 |
| Précision / rappel / F1 (seuil 0,975) | 0 / 0 / 0 | 0 / 0 / 0 |
| Commit Git (tag MLflow) | `769b4df` | `769b4df` |

Fichiers produits par le run final : `metrics.json` (split `temporel/machine`), `params.yaml`, `artifacts/models/model_metadata.json` (avec `gold_md5` et `metrics_holdout`).
Pointeur modèle après le run final : `dvc add artifacts/models/rf.joblib` + `dvc push` (*Everything is up to date*) + `dvc status` à jour ; md5 inchangée (`2779890…`). Le réentraînement avec `random_state=42` sur le même Gold redonne un fichier identique.
Artefacts MLflow stockés dans `mlartifacts/` (≈ 16,5 Mo) et base `mlflow.db` : tous deux **ignorés par Git** (état local, reconstructible).

Lecture des résultats :

- Le split **stratifié mélange passé et futur** : ROC-AUC 0,85 est un score **gonflé par la fuite temporelle**.
- Le split **temporel par machine** est le seul réaliste : ROC-AUC 0,25 (< 0,5, donc pire qu'un classement aléatoire) et PR-AUC 0,10, sous le taux de panne de 0,13. Le modèle du starter **n'a pas de pouvoir prédictif** sur le futur.
- Avec un seuil de 0,975, aucune alerte n'est émise (rappel = 0) sur les deux splits : **seuil inadapté**, à recalibrer sur validation.
- Conclusion : la chaîne de versioning est démontrée ; le modèle **n'est pas promouvable** (aucune promotion Staging, non exigée ici).

Historique : une première paire de runs (28/09, `43652745…` / `4b20b865…`) avait été reçue par erreur par un ancien serveur `mlflow ui` du projet `Formation`, resté actif sur le port 5000. Ces runs ont été **rejoués** sur le serveur du repo (port 5001), après vérification que ce serveur ne connaissait que l'expérience `Default`. Métriques identiques, ce qui confirme la **reproductibilité** (seed 42, même Gold).

## Secrets

Aucun secret dans Git. Secrets locaux dans `.env`, secrets CI dans GitHub Actions secrets.

- `.env` listé dans `.gitignore` ; seul `.env.example` (sans valeur réelle) est versionné.
- gitleaks en hook `pre-commit` : la démonstration avec les clés d'exemple publiques AWS a bien été **bloquée**, puis la sentinelle a été supprimée sans commit.
- Un secret commité par erreur est compromis même après suppression : **le révoquer**.

## Contrat d'expérience vision - rappel cohorte de juin

| Champ | Valeur / preuve |
|---|---|
| run_id MLflow | à produire |
| méthode / score | à produire : MSE, SSIM validée ou PatchCore réel |
| split ou hash ; résolution ; seed | à produire |
| seuil et calibration | seuil propre à chaque score ; à produire |
| carte d'erreur / artefact | chemin à produire |
| durée ; pic mémoire ; énergie/CO2e | à mesurer, jamais extrapoler |
| statut | STRUCTURE=PASS ; MESURES=NOT_READY tant que les preuves manquent |

## Questions tranchées

1. **Quel commit produit quel modèle ?** Le tag MLflow `mlflow.source.git.commit` de chaque run : `769b4df` pour v1 et v2. Le pointeur `rf.joblib.dvc` du commit désigne le fichier exact.
2. **Quelle empreinte identifie le Gold utilisé ?** md5 `637be8d3825023160de0980761c9a9e8` (pointeur DVC), reprise dans le tag `gold_md5` de chaque run et dans `model_metadata.json`.
3. **Comment rejouer un run sans modifier `uv.lock` ?** `uv sync --frozen --extra dev --extra mlops` puis `uv run --frozen python scripts/demo_versioning.py --no-dvc --tracking-uri http://127.0.0.1:5001 --split temporal` ; contrôle : `git status --short -- uv.lock` vide.
4. **Comment restaurer code, données et modèle ensemble ?** (serveur MLflow : `uv run --frozen mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5001`) `git switch --detach <commit>` → `uv sync --frozen ...` → `uv run --frozen dvc pull` → `uv run --frozen dvc status` à jour ; le modèle servi peut aussi être rechargé depuis `models:/indusense-rf/<version>`.
