# Model Card — InduSense (modèle apprenant)

Les statuts autorisés sont `[mesuré]`, `[à produire]`, `[non mesuré]`,
`[à confirmer]` et `[benchmark externe]`. Toute ligne `[mesuré]` doit comporter
`preuve=chemin/relatif` vers un fichier local réel.

## 1. Niveau métier

*Lecteur : responsable maintenance / production. Question : « puis-je m'appuyer sur ce signal pour planifier une intervention ? »*

- Finalité et utilisateurs : [mesuré] Signaler, pour chaque machine, un risque de panne dans les 24 h afin d'anticiper une intervention de maintenance ; utilisateurs : équipe maintenance et responsable de ligne (décision D1, validée le 29/09/2026) ; preuve=docs/decisions_metier.md
- Horizon de prédiction : [mesuré] cible `panne` = 1 pour tout relevé situé dans les 24 h précédant un incident de la même machine (`window_hours=24`, `incident_window_hours=24`) ; preuve=src/indusense/data/loaders.py
- Seuil de décision servi par l'API : [mesuré] `decision_threshold = 0.5` → `decision = "alerte"` si `proba_panne ≥ 0.5`, sinon `"ok"` ; preuve=src/indusense/config.py
- Performance réellement mesurée : [mesuré] split temporel par machine (1516 train / 380 test, prévalence test 0,1316), au seuil 0,975 : précision 0, rappel 0 (aucune alerte émise) ; PR-AUC 0,1036 (inférieure à la prévalence) ; ROC-AUC 0,2475 (< 0,5, donc pire qu'un classement aléatoire) ; preuve=metrics.json
- Performance au seuil servi 0,5 : [non mesuré] le seuil de l'API (0,5) diffère du seuil évalué (0,975) ; rappel, précision et nombre d'alertes à 0,5 n'ont pas été mesurés.
- Coût des erreurs : [non mesuré] faux négatif = panne non anticipée (arrêt non planifié, réparation en urgence) ; faux positif = intervention ou inspection inutile. Coûts unitaires et ratio FN/FP à produire avec le métier avant tout choix de seuil.
- Décision assistée, hors périmètre et supervision humaine : [mesuré] le modèle **assiste** la décision, il ne la prend pas : toute intervention reste décidée par un humain. Hors périmètre : arrêt automatique d'une machine, décision de sécurité des personnes, machines ou capteurs absents des données d'entraînement (décision D2, validée le 29/09/2026) ; preuve=docs/decisions_metier.md
- Limites et recommandation d'usage : [mesuré] en l'état, le modèle **n'a pas de pouvoir prédictif démontré** sur le futur (ROC-AUC 0,2475 au split temporel) ; il ne doit pas être utilisé pour déclencher des interventions. Le score élevé du split stratifié (fuite temporelle) n'est pas représentatif ; preuve=versioning_strategy.md

## 2. Niveau technique / maintenance

*Lecteur : data scientist / MLOps. Question : « quel modèle exact, entraîné comment, et comment le rejouer ? »*

- Artefact et version : [mesuré] `RandomForestClassifier` (`n_estimators=200`, `random_state=42`), fichier `artifacts/models/rf.joblib` suivi par DVC, md5 `2779890061870d6a08d6efdf733da094`, taille 4 965 817 o ; registre MLflow `indusense-rf` **v2** ; l'API expose `model_version = "0.1.0"` (= `package_version` de `model_metadata.json`, et non la version du registre) ; preuve=artifacts/models/rf.joblib.dvc
- Données, split temporel et empreinte : [mesuré] Gold `data/gold/gold_dataset.csv`, md5 `637be8d3825023160de0980761c9a9e8` (287 704 o), 1896 lignes exploitables, taux de panne 0,1055 ; split **temporel par machine** : 1516 train / 380 test ; 12 features (température et pression + lags 1/3/6 + moyennes glissantes 3/6, `shift(1)` avant `rolling`) ; preuve=data/gold/gold_dataset.csv.dvc
- Métriques et seuil : [mesuré] test temporel : PR-AUC 0,1036, ROC-AUC 0,2475, précision 0, rappel 0, F1 0 au seuil d'évaluation 0,975 ; prévalence test 0,1316 ; seuil servi par l'API 0,5 (performance à ce seuil non mesurée) ; preuve=metrics.json
- MLflow run_id : [mesuré] `b022d07a181246dda313e29493fb2052` (run temporel, version v2, expérience `indusense-maintenance`, commit `769b4df`, tag `gold_md5=637be8d38250`) ; run de comparaison stratifié (fuite) `3d425d2081014f17856b3cc0d3eacea2` (v1) ; preuve=versioning_strategy.md
- Signature I/O : [mesuré] entrée `TabularPredictionRequest` = `machine_id` (texte normalisé en `MACH-0N`) + `readings` (≥ 7 relevés `timestamp`, `temperature` ∈ [-20 ; 200], `pressure_bar` ∈ ]0 ; 400]) ; sortie `PredictionResponse` = `machine_id`, `proba_panne` ∈ [0 ; 1], `decision`, `model_version`, `threshold` ; codes 401 / 422 / 503 testés ; preuve=src/indusense/api/schemas.py
- Coût comparé CPU, RAM, GPU, durée, latence et taille : [non mesuré] seule la taille de l'artefact est connue (4 965 817 o, ligne « Artefact et version ») ; CPU, RAM, durée d'entraînement, latence d'inférence et énergie ne sont pas mesurés ; pas de GPU utilisé.
- Limites, drift, réévaluation et responsable : [à produire] limites connues : pas de pouvoir prédictif au split temporel ; seuil servi ≠ seuil évalué ; `model_version` ne distingue pas deux entraînements du même package. Suivi du drift (M31-32), critère et fréquence de réévaluation, responsable nommé : à produire.

## 3. Niveau conformité AI Act

*Lecteur : référent conformité / DPO. Question : « quels risques, pour qui, avec quelles données, et sous quel contrôle humain ? »*

- Finalité, personnes affectées et données utilisées : [mesuré] finalité : aide à la maintenance prédictive d'équipements (décision D1) ; le modèle prédit un état **machine**, et non un comportement ou une performance de personne. Personnes affectées indirectement : techniciens et responsables de maintenance (planification des interventions). Données du modèle : relevés capteurs (température, pression) horodatés par machine. La source brute `releves_incidents.csv` contient des données **liées à des personnes** (`operator_name`, `operator_badge`, `shift`, pseudonymisées par des codes `OP-…` / `BADGE…`) : **minimisation appliquée**, `load_incidents` ne conserve que `machine` et `incident_ts` ; aucune donnée opérateur n'entre dans le Gold ni dans les features ; preuve=src/indusense/data/loaders.py
- Usages interdits : [mesuré] arrêt automatique de machine, décision de sécurité des personnes, usage sur des machines ou capteurs absents des données d'entraînement (décision D2) ; preuve=docs/decisions_metier.md
- Interdiction de surveiller les opérateurs : [mesuré] tout usage du modèle ou de ses alertes pour évaluer ou surveiller des personnes est interdit (par exemple, rapprochement des alertes et des équipes, des badges ou des postes) ; les données opérateur de la source brute restent exclues du Gold et des features (décision D3, validée le 29/09/2026) ; preuve=docs/decisions_metier.md
- Supervision humaine : [mesuré] le modèle assiste la décision, l'humain décide de toute intervention (décision D2) ; l'API expose la probabilité, la décision, le seuil et la version pour permettre ce contrôle ; preuve=docs/decisions_metier.md
- Risques, transparence, journalisation et supervision : [non mesuré] risques identifiés : faux négatifs (panne non anticipée), faux positifs (interventions inutiles), sur-confiance dans un modèle **sans pouvoir prédictif démontré** (ROC-AUC 0,2475), dérive des capteurs, seuil servi (0,5) non évalué. Transparence : réponse API explicite (`proba_panne`, `decision`, `threshold`, `model_version`), model card. Journalisation : un `X-Request-ID` corrèle chaque requête, mais l'API **n'écrit aucun journal** des prédictions et il n'existe **pas d'audit log** (prévu au M26) ; la traçabilité d'une décision a posteriori n'est donc pas assurée à ce stade.
- Classification réglementaire : [à confirmer] à confirmer avec le référent conformité. Éléments à lui soumettre : système d'aide à la maintenance d'équipements industriels, sans décision automatisée sur des personnes, sans donnée personnelle dans les features ; la question de savoir s'il constitue un composant de sécurité d'un produit ou d'une machine reste ouverte.

## 4. Benchmark externe distinct

- Référence Marine — ne décrit pas mon modèle : [benchmark externe] XGBoost ; cible panne à 24 h ; seuil proche de 0,41 ; PR-AUC proche de 0,62 ; prévalence 16,6 %.
- Coût Marine — ne décrit pas mon modèle : [benchmark externe] frugal 202,6 s / 0,158 gCO2e ; lourd 612,8 s / 0,352 gCO2e.
