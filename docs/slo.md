# SLO InduSense — M33

**SLI** (*Service Level Indicator*) : ce que l'on **mesure**, ici avec une requête PromQL.
**SLO** (*Service Level Objective*) : l'**objectif chiffré** que ce SLI doit tenir sur une fenêtre de temps.
**Budget d'erreur** : la part d'échec tolérée par l'objectif (`100 % - objectif`). Tant qu'il reste du budget, on peut livrer ; une fois épuisé, on gèle les évolutions et on stabilise.

## Les 5 SLO

| # | Indicateur | Population | Fenêtre | Objectif | Source PromQL | Budget d'erreur |
|---|---|---|---|---|---|---|
| 1 | Disponibilité | cible Prometheus `indusense-api` (scrape toutes les 15 s) | 30 jours glissants | ≥ 99,5 % du temps `up = 1` | `avg_over_time(up{job="indusense-api"}[30d])` | 0,5 % ≈ 3 h 36 d'indisponibilité par 30 j |
| 2 | Readiness modèle | cible `indusense-api` : processus collecté **et** modèle chargé | 30 jours glissants | ≥ 99 % du temps à 1 | `(up{job="indusense-api"} * on(job, instance) indusense_model_loaded{job="indusense-api"}) or on(job, instance) (0 * up{job="indusense-api"})` (instantané) | 1 % ≈ 7 h 12 par 30 j |
| 3 | Latence | requêtes `POST /predict-tabular` | 5 min (alerte), 30 j (rapport) | p95 < 300 ms | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{handler="/predict-tabular"}[5m])) by (le))` | 5 % des requêtes peuvent dépasser 300 ms |
| 4 | Erreurs serveur | toutes les requêtes HTTP de l'API | 5 min (alerte), 30 j (rapport) | taux de 5xx < 1 % | `(sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0)) / sum(rate(http_requests_total[5m]))` | 1 % des requêtes |
| 5 | Dérive des entrées | features `temperature` et `pressure_bar`, fenêtre courante contre la référence **du même régime** | à chaque fenêtre évaluée | PSI < 0,25 pour chaque feature | `max by (feature) (indusense_drift_psi{reference="normale"})` | aucune fenêtre au-dessus de 0,25 sans analyse ; 0,10 à 0,25 = à surveiller |

## Pourquoi ces objectifs sont utiles au métier

1. **Disponibilité** : si l'API est injoignable, la maintenance ne reçoit plus aucune alerte de panne. Une panne non anticipée coûte un arrêt de ligne.
2. **Readiness modèle** : une API vivante sans modèle répond 503 à toutes les prédictions. `/health` resterait vert alors que le service métier est rendu nul : c'est le piège que ce SLI couvre.
3. **Latence** : la prédiction doit arriver avant la décision d'intervention ; 300 ms laisse de la marge à l'outil appelant. Mesure locale du 19/10/2026 (Locust, 20 utilisateurs, 30 s) : p95 = 110 ms côté client.
4. **Erreurs serveur** : un 5xx est une erreur **de notre côté** (bug, base indisponible). Les 4xx (401, 422, 429) sont des refus voulus et ne consomment pas ce budget.
5. **Dérive** : un modèle qui reçoit des données différentes de celles de son apprentissage se trompe **sans erreur visible**. Le PSI F2 à 6,834 (capteur +8 °C) doit déclencher une analyse avant que les décisions ne se dégradent.

## SLI absent contre SLI mauvais

Un SLI **mauvais** a une valeur, mais hors objectif (p95 = 0,45 s). Un SLI **absent** n'a **aucune valeur** : la requête PromQL renvoie un résultat vide. Une alerte du type `p95 > 0,3` ne se déclenche jamais sur un résultat vide, donc l'absence de donnée **cache** un incident.

| SLI | Comment l'absence est rendue visible |
|---|---|
| Disponibilité | `up` existe toujours tant que Prometheus tourne : il vaut 0 quand la cible ne répond plus. Vérifié le 19/10 : API arrêtée → `up = 0`. |
| Readiness | API arrêtée : la gauge `indusense_model_loaded` devient **vide** (pas 0). La branche `or on(job, instance) (0 * up)` ramène 0. Vérifié le 19/10 : readiness = 0 pendant l'arrêt, puis 1 au redémarrage. |
| Latence | Sans trafic, `rate()` est vide. Lire ce SLI **avec** le débit (`sum(rate(http_requests_total[5m]))`) : débit nul = SLI absent, pas « latence parfaite ». |
| Erreurs | Sans aucun 5xx, la série n'existe pas et la division renvoie vide. Le `or vector(0)` au numérateur transforme « aucun 5xx » en 0 %. |
| Dérive | Exporteur arrêté → la cible `indusense-drift` passe `DOWN` (`up{job="indusense-drift"} = 0`) et les gauges PSI disparaissent : à surveiller par `up`, pas par le PSI. |

## Limites connues

- **Précision du p95** : l'histogramme n'a que 3 tranches (0,1 / 0,5 / 1 s). Le 19/10, PromQL donnait 316 ms alors que Locust mesurait 110 ms : le p95 tombe entre 0,1 et 0,5 s, et PromQL l'estime par interpolation linéaire. Pour piloter un SLO à 300 ms, il faudrait des tranches autour de cette valeur (par exemple 0,2 / 0,3 / 0,4 s).
- **Compteurs remis à zéro** au redémarrage du conteneur : utiliser `rate()` ou `increase()`, jamais la valeur brute d'un counter.
- **Pas de `machine_id` en label** : cardinalité et fuite de donnée métier (M26). La métrique `indusense_predictions_total` n'a que le label `decision` (2 valeurs).
- **Objectifs 30 jours** : ce sont des cibles de conception. La stack locale ne conserve pas 30 jours d'historique ; elles sont à confirmer avec le métier.
- Indicateur complémentaire, sans objectif fixé : taux de 401 (`sum(rate(http_requests_total{status="401"}[5m]))`), rendu possible par `should_group_status_codes=False`. Il sert l'alerte d'exercice du M34.
