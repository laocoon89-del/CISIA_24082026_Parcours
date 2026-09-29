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

- Artefact et version : [à produire]
- Données, split temporel et empreinte : [à produire]
- Métriques et seuil : [à produire]
- MLflow run_id : [à produire]
- Signature I/O : [à produire]
- Coût comparé CPU, RAM, GPU, durée, latence et taille : [non mesuré]
- Limites, drift, réévaluation et responsable : [à produire]

## 3. Niveau conformité AI Act

- Finalité, personnes affectées et données utilisées : [à produire]
- Risques, transparence, journalisation et supervision : [à produire]
- Classification réglementaire : [à confirmer] à confirmer avec le référent conformité

## 4. Benchmark externe distinct

- Référence Marine — ne décrit pas mon modèle : [benchmark externe] XGBoost ; cible panne à 24 h ; seuil proche de 0,41 ; PR-AUC proche de 0,62 ; prévalence 16,6 %.
- Coût Marine — ne décrit pas mon modèle : [benchmark externe] frugal 202,6 s / 0,158 gCO2e ; lourd 612,8 s / 0,352 gCO2e.
