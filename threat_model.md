# Modèle de menaces — InduSense (M26)

Branche `ludovic-bourreau`, jalon 04. Établi le 29/09/2026. Périmètre : `POST /predict-tabular` (et `POST /predict-image`) + pipeline de données et d'entraînement.
Méthode : **STRIDE** appliqué à chaque frontière de confiance ; contrôles et risques résiduels reportés dans `security_controls.md`.

## Actifs à protéger

- **Disponibilité** du service de prédiction (les équipes de maintenance en dépendent).
- **Intégrité des décisions** renvoyées (`proba_panne`, `decision`) : une fausse décision entraîne une intervention inutile ou une panne manquée.
- **Modèle entraîné** `artifacts/models/rf.joblib` (suivi par DVC, md5 `2779890061870d6a08d6efdf733da094`).
- **Données** : Gold (`data/gold/gold_dataset.csv`, DVC) et sources brutes (`data/raw/`), dont `releves_incidents.csv`, qui contient des **données personnelles pseudonymisées** (`operator_name`, `operator_badge`, `shift`).
- **Secrets** : clé API (`INDUSENSE_API_KEY`, fichier `.env` non versionné).
- **Traçabilité** : lien code ↔ données ↔ modèle (Git, DVC, MLflow).

## Frontières de confiance

1. **Client → API** (réseau) : tout ce qui arrive (en-têtes, corps JSON, fichier) est non fiable.
2. **API → modèle** : l'API charge `rf.joblib` depuis le disque au démarrage (`lifespan`).
3. **Sources brutes → pipeline** (`load_*`, `build_dataset`) : fichiers CSV/TSV/SQL hétérogènes.
4. **Dépôt et CI** : code, `uv.lock`, pointeurs DVC, hooks et workflows.

## Menaces STRIDE

| Menace | Scénario concret | Impact | Contrôle existant | Risque résiduel | Action |
|---|---|---|---|---|---|
| **S** — Usurpation | un appelant non autorisé interroge `/predict-tabular` | usage abusif, extraction du modèle | clé `X-API-Key` → 401 (Implémenté) | clé unique partagée ; `dev-key` par défaut ; pas d'identité par client | clé obligatoire en production, une clé par client, `compare_digest`, rotation |
| **T** — Altération des entrées | relevés fabriqués mais dans les bornes, choisis pour faire passer la décision à « ok » (entrée adversariale) | panne non anticipée | validation Pydantic (bornes, ≥ 7 relevés) → 422 (Implémenté) | aucune vérification de plausibilité ; le modèle n'a de toute façon pas de pouvoir prédictif démontré | contrôles de cohérence temporelle ; supervision humaine (D2) |
| **T** — Altération / empoisonnement des données | modification d'un fichier brut ou du Gold avant entraînement | modèle biaisé, décisions fausses | empreintes DVC (md5) + `gold_md5` tagué dans MLflow | pas de contrôle d'intégrité automatique avant entraînement ni de revue des sources | vérifier `dvc status` et le md5 en CI avant tout entraînement |
| **T** — Altération du modèle | remplacement de `rf.joblib` par un fichier piégé (un fichier joblib/pickle peut **exécuter du code** au chargement) | exécution de code sur le serveur | pointeur DVC (md5 de référence) | l'API **ne vérifie pas** le md5 avant `load_model` | comparer le md5 de l'artefact au pointeur DVC avant chargement ; artefact en lecture seule dans l'image |
| **R** — Répudiation | un client conteste avoir reçu une alerte, ou on ne peut pas retrouver quelle prédiction a motivé une intervention | litige, perte de confiance, audit impossible | `X-Request-ID` (corrélation seulement) | **aucun journal d'audit** (Planifié v0) | événement d'audit structuré sans clé, payload ni PII + test |
| **I** — Fuite d'information | messages d'erreur ou logs exposant la clé, les données ou la pile d'appel ; clé commitée dans Git | compromission de la clé, fuite de données | gitleaks en pre-commit ; `.env` ignoré ; erreurs 4xx à message court ; test de non-divulgation `tests/test_log_non_disclosure.py` (aucune clé ni valeur du payload dans les logs) | `/docs` et `/openapi.json` publics (le contrat est visible) ; le test ne couvre que les logs émis aujourd'hui | garder ce test quand l'audit logging sera ajouté ; décider si `/docs` doit être exposé en production |
| **I** — Fuite de données personnelles | réutilisation des données opérateur de la source brute | atteinte à la vie privée, détournement de finalité | minimisation : `load_incidents` ne garde que `machine` et `incident_ts` ; décision D3 | données personnelles toujours présentes dans `data/raw/` | restreindre l'accès aux sources brutes ; pseudonymisation contrôlée |
| **D** — Déni de service (volume) | rafale de requêtes | indisponibilité | rate limit 60/min/IP → 429 (Implémenté) | compteur en mémoire mono-processus ; contournable avec plusieurs IP | limitation partagée ou au reverse proxy |
| **D** — Déni de service (taille) | corps JSON ou fichier très volumineux | saturation mémoire ou CPU | `Content-Length` > 64 Kio → 413, illisible → 400 (Implémenté) ; `/predict-image` ne lit que 8 octets | requête sans `Content-Length` non contrôlée par le middleware | limite au reverse proxy ; test sans `Content-Length` |
| **E** — Élévation de privilège | paramètre de sécurité surchargeable par le client (ex. `?limit=100000` qui désactiverait le rate limit) | contournement d'un contrôle | `rate_limit_dependency` n'expose aucun paramètre ; test OpenAPI (Implémenté) | le processus tourne avec les droits de l'utilisateur local | exécution non-root dans le conteneur (M27) ; moindre privilège |

## Menaces propres au ML

| Menace | Application à InduSense | Traitement actuel |
|---|---|---|
| Entrées adversariales | relevés construits pour faire mentir le modèle | bornes seulement (voir T) |
| Empoisonnement | Gold ou incidents modifiés avant entraînement | empreintes DVC, sans contrôle automatique |
| Extraction du modèle | requêtes massives pour reconstituer le comportement du modèle | clé + rate limit |
| Sur-confiance | décision suivie aveuglément alors que ROC-AUC = 0,2475 au split temporel | model card : « ne pas utiliser en l'état » ; supervision humaine (D2) |
| Dérive | capteurs recalibrés, nouvelles machines | non traité (M31-32) |

## Attack tree (objectif : faire manquer une panne)

```text
Faire répondre « ok » alors qu'une panne arrive
├── Accéder à l'API sans être autorisé ........ bloqué par la clé (401)
│   └── utiliser la clé par défaut `dev-key` .. possible si INDUSENSE_API_KEY absent → risque résiduel
├── Envoyer des relevés falsifiés mais bornés .. NON bloqué (validation de forme seulement)
├── Remplacer le modèle sur le disque ........ NON bloqué (pas de vérification md5 au chargement)
└── Empoisonner les données d'entraînement ... détectable (md5 DVC), NON bloqué automatiquement
```

## Hors périmètre et hypothèses

- Hors périmètre : sécurité du réseau et du poste hôte, TLS/HTTPS (à assurer par le reverse proxy au déploiement), gestion des comptes du dépôt Git.
- Hypothèses : l'API est exposée sur un réseau interne d'usine ; la clé est fournie par l'environnement et non par le code ; le modèle n'est pas un composant de sécurité des personnes (décision D2 ; classification AI Act à confirmer avec le référent conformité).
- Les risques résiduels signalés sont issus de la **lecture du code** ; seuls les contrôles marqués « Implémenté » sont prouvés par des tests.
