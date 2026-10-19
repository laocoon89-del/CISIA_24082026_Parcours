# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — perf/locustfile.py
# [PÉDAGOGIE] MODULE  — M33–M34 — charge, capacité et objectifs de service
# [PÉDAGOGIE] RÔLE    — Générer une charge contrôlée pour observer débit, latence, erreurs et
# [PÉDAGOGIE]           protections de l'API.
# [PÉDAGOGIE] THÉORIE — un scénario de charge doit représenter un comportement utilisateur
# [PÉDAGOGIE]           explicite
# [PÉDAGOGIE]           • percentiles et taux d'erreur décrivent mieux l'expérience qu'une moyenne
# [PÉDAGOGIE]             seule
# [PÉDAGOGIE]           • le test de charge observe aussi rate limit, saturation et récupération
# [PÉDAGOGIE] À VOIR  — Comparer la charge injectée aux métriques API et système sur la même
# [PÉDAGOGIE]           fenêtre temporelle.
# [PÉDAGOGIE] PIÈGE   — Un test lancé sans borne peut dégrader le poste ; garder utilisateurs,
# [PÉDAGOGIE]           cadence et durée contrôlés.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

"""Charge légère M33, sans dépendance ajoutée au verrou de l'application."""

# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import json
import os
from pathlib import Path

from locust import HttpUser, between, task

# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
SPRINT_ROOT = Path(__file__).resolve().parents[1]
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
PAYLOAD_PATH = SPRINT_ROOT / "payload.json"


# [PÉDAGOGIE] BLOC `_load_payload` — frontière d'entrée : convertir une représentation externe en
# [PÉDAGOGIE] structure interne validée.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : vérifier schéma, types,
# [PÉDAGOGIE] ordre et erreurs explicites avant tout calcul aval.
def _load_payload() -> dict[str, object]:
    """Charge le corps une seule fois au démarrage du processus Locust."""

    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with PAYLOAD_PATH.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if len(payload.get("readings", [])) < 7:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise RuntimeError(f"{PAYLOAD_PATH} doit contenir au moins 7 relevés")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return payload


# [PÉDAGOGIE] BLOC `_load_api_key` — frontière d'entrée : convertir une représentation externe en
# [PÉDAGOGIE] structure interne validée.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : vérifier schéma, types,
# [PÉDAGOGIE] ordre et erreurs explicites avant tout calcul aval.
def _load_api_key() -> str:
    """Lit la clé depuis l'environnement, jamais depuis une constante versionnée."""

    api_key = os.environ.get("INDUSENSE_API_KEY", "").strip()
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if not api_key:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise RuntimeError(
            "INDUSENSE_API_KEY est absent : chargez la valeur du .env dans le terminal "
            "PowerShell avant de lancer Locust."
        )
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return api_key


# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
PAYLOAD = _load_payload()


# [PÉDAGOGIE] TYPE `InduSenseUser` — regroupe un état cohérent et le contrat des opérations
# [PÉDAGOGIE] associées.
# [PÉDAGOGIE] THÉORIE — nommer ce type rend les invariants visibles et facilite les tests à la
# [PÉDAGOGIE] frontière.
class InduSenseUser(HttpUser):
    """Client tabulaire à cadence compatible avec la limite pédagogique de 60/min."""

    wait_time = between(18.0, 22.0)

    # [PÉDAGOGIE] BLOC `on_start` — unité de responsabilité : isoler un comportement nommable,
    # [PÉDAGOGIE] testable et réutilisable.
    # [PÉDAGOGIE] CONTRAT — entrées : self ; preuve : l'appelant doit pouvoir vérifier la sortie
    # [PÉDAGOGIE] ou l'effet de bord annoncé.
    def on_start(self) -> None:
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": _load_api_key(),
        }

    # [PÉDAGOGIE] BLOC `predict_tabular` — phase d'inférence ou d'évaluation : appliquer un
    # [PÉDAGOGIE] contrat gelé à des observations nouvelles.
    # [PÉDAGOGIE] CONTRAT — entrées : self ; preuve : contrôler ordre des features, seuil,
    # [PÉDAGOGIE] métriques et provenance du modèle.
    @task
    def predict_tabular(self) -> None:
        self.client.post(
            "/predict-tabular",
            json=PAYLOAD,
            headers=self.headers,
            name="/predict-tabular",
        )
