# Runbook M34 — InduSense API

Un runbook suit toujours le même ordre : **symptôme → diagnostic → action → escalade**. Il se joue comme un exercice incendie : un runbook jamais joué est probablement faux.

Commandes à lancer depuis la racine du dépôt Parcours. Sous Linux, si le terminal ne voit pas encore le groupe `docker`, préfixer par `sg docker -c "…"`.

---

## Runbook A — API morte

### Alerte

- Nom : `EXERCICE — API morte (up < 1)` (dossier Grafana « InduSense alertes », groupe `indusense-m34`).
- Signal/condition : `up{job="indusense-api"} < 1` pendant **1 min** (`for: 1m`), évalué toutes les 10 s.
- Gravité et impact métier : **critique**. Plus aucune prédiction n'est servie, donc la maintenance ne reçoit plus d'alerte de panne : risque d'arrêt de ligne non anticipé. Les SLO 1 (disponibilité) et 2 (readiness) consomment leur budget.

### Diagnostic borné

1. Le conteneur tourne-t-il ? `docker compose ps api` → état `running` et `healthy` attendus. `exited` ou absent = conteneur arrêté.
2. L'API répond-elle depuis le PC ? `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/health` → `200` attendu. `000` = rien n'écoute sur le port.
3. Pourquoi s'est-elle arrêtée ? `docker compose logs --tail 50 api` : chercher une erreur de démarrage (modèle introuvable, port déjà pris, `.env` absent). Ne pas copier ces journaux dans un ticket s'ils contiennent un payload.

### Action réversible

- Action : `docker compose up -d --wait api` (redémarre seulement le service `api`, sans reconstruire ni toucher à la base).
- Retour arrière : `docker compose stop api` remet l'état précédent. L'action ne modifie ni l'image, ni les données, ni la configuration.
- Preuve de résolution :
  1. `curl http://localhost:8000/health` → `200`, puis `/ready` → `200` ;
  2. dans Prometheus, `up{job="indusense-api"}` = 1 et la readiness `up × indusense_model_loaded` = 1 ;
  3. dans Grafana, la règle repasse **Normal**.

### Escalade

- L'API redémarre puis retombe (boucle de redémarrage), ou `/ready` reste à `503` (modèle non chargé) → prévenir le formateur, ou en production l'astreinte MLOps, avec l'heure de début, la sortie de `docker compose ps` et les **dernières lignes d'erreur** seulement.

---

## Runbook B — Pic de 401

### Alerte

- Nom : `EXERCICE — Pic de 401`.
- Signal/condition : `sum(rate(http_requests_total{status="401"}[1m])) > 0.2` (plus d'une requête refusée toutes les 5 s) pendant **1 min**.
- Gravité et impact métier : **avertissement**. Soit un client légitime a perdu sa clé (rotation mal propagée, `.env` erroné) et ne reçoit plus de prédictions ; soit quelqu'un essaie des requêtes sans autorisation.

### Diagnostic borné

1. Quel endpoint ? Dans Grafana, panel « Requêtes/s par code HTTP » : les 401 visent-ils `/predict-tabular` ?
2. Depuis quand, et y a-t-il encore des 200 ? Si les 200 tombent à 0 en même temps, c'est probablement le client légitime qui a une mauvaise clé.
3. La clé attendue est-elle bien configurée ? Vérifier que `INDUSENSE_API_KEY` est présente dans `.env` **sans l'afficher** (`grep -c '^INDUSENSE_API_KEY=' .env` → `1`).

### Action réversible

- Action : identifier le client et lui redonner la bonne clé ; s'il s'agit d'un appel non autorisé, le bloquer en amont (pare-feu, proxy).
- Retour arrière : retirer le blocage ajouté.
- Preuve de résolution : le taux de 401 repasse sous 0,2/s, la règle repasse **Normal**, et les 200 sont revenus sur le panel.

### Escalade

- Si les 401 continuent alors que les clients légitimes ont la bonne clé, il s'agit d'une tentative d'accès non autorisée : prévenir la sécurité. **Ne jamais coller de clé ni de payload** dans le ticket.

---

## Exercices joués (19/10/2026, poste Linux, Grafana 11.1.0)

Les règles sont évaluées toutes les 10 s. Après le **premier** constat de la condition, une règle passe en **Pending**. Elle ne passe en **Firing** que si la condition reste vraie pendant toute la durée du `for:`.

### Incident A — API morte (runbook A)

| Heure | Événement |
|---|---|
| 12:08:45 | règle Normal ; `docker compose stop api` |
| 12:08:56 | **Pending** : première évaluation avec `up = 0` |
| 12:09:57 | **Firing** : condition vraie depuis 1 min (`for: 1m`) |
| 12:09:57 | diagnostic 1 : `api exited` ; diagnostic 2 : `/health` → `000` |
| 12:09:57 | action : `docker compose up -d --wait api` |
| 12:10:28 | preuve : `/health` 200, `/ready` 200 ; règle **Normal** |

Délai de détection : environ 1 min 12 s entre la panne et l'alerte Firing. Délai de résolution une fois l'alerte reçue : 31 s.

### Incident B — Pic de 401 (runbook B)

| Heure | Événement |
|---|---|
| 12:10:36 | règle Normal ; boucle de `POST /predict-tabular` **sans** `X-API-Key` (environ 2 req/s), contrôle → `401` |
| 12:11:11 | **Pending** : le taux de 401 sur 1 min dépasse 0,2/s |
| 12:12:12 | **Firing** : condition vraie depuis 1 min |
| 12:12:12 | action : arrêt de la source des 401 (fin de la boucle) |
| 12:13:13 | règle **Normal** : la fenêtre `rate(...[1m])` ne contient plus de 401 |

Le retour à Normal prend environ 1 min après l'arrêt : c'est la durée de la fenêtre `[1m]` de la requête, le temps que les derniers 401 en sortent.

Ne jamais copier de secret, de payload sensible ou de journal complet dans le runbook.
