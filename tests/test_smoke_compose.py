# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — tests/test_smoke_compose.py
# [PÉDAGOGIE] MODULE  — Sprint 3 — tests comme contrats exécutables
# [PÉDAGOGIE] RÔLE    — Décrire un invariant observable avec Arrange, Act, Assert et prévenir les
# [PÉDAGOGIE]           régressions.
# [PÉDAGOGIE] THÉORIE — un test porte sur un comportement, pas sur l'implémentation accidentelle
# [PÉDAGOGIE]           • les fixtures contrôlent l'entrée et rendent l'échec reproductible
# [PÉDAGOGIE]           • les cas limites protègent les frontières où les incidents apparaissent
# [PÉDAGOGIE] À VOIR  — Le nom du test, son entrée et son assertion doivent expliquer précisément
# [PÉDAGOGIE]           la garantie couverte.
# [PÉDAGOGIE] PIÈGE   — Un test qui dépend du réseau, de l'heure ou d'un ordre implicite peut
# [PÉDAGOGIE]           devenir instable.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

"""Smoke test M28 : interroge la VRAIE API lancée par `docker compose up -d --build`.

Contrairement à tests/test_api.py (TestClient en mémoire, faux modèle), ce test passe
par le réseau : port publié 8000, conteneur non-root, modèle livré dans l'image.
Si la stack n'est pas lancée (CI, poste sans Docker), le test est IGNORÉ, pas échoué.
"""

# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from indusense.config import settings

# URL de l'API publiée par Compose ; surchargeable (ex. autre port) sans toucher au code.
BASE_URL = os.environ.get("INDUSENSE_BASE_URL", "http://127.0.0.1:8000")
# Payload de démonstration versionné à la racine du dépôt (MACH-07, relevés horaires).
PAYLOAD = json.loads((Path(__file__).parent.parent / "payload.json").read_text(encoding="utf-8"))


def _skip_if_stack_down() -> None:
    """Skip explicite si personne n'écoute sur BASE_URL (stack non lancée)."""
    try:
        httpx.get(f"{BASE_URL}/health", timeout=5.0)
    except httpx.TransportError:
        pytest.skip(f"Stack Compose non lancée sur {BASE_URL} (docker compose up -d --build)")


# [PÉDAGOGIE] BLOC `test_api_health_and_auth_contract` — ce test transforme un comportement
# [PÉDAGOGIE] attendu en contrat de non-régression.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : la dernière assertion est
# [PÉDAGOGIE] l'oracle : son échec doit pointer la garantie cassée.
def test_api_health_and_auth_contract() -> None:
    """Prouver /health=200, prediction sans cle=401 et prediction valide=200."""
    _skip_if_stack_down()
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as api:
        # 1. Liveness : le processus uvicorn répond.
        health = api.get("/health")
        assert health.status_code == 200, health.text

        # 2. Sécurité : sans en-tête X-API-Key, la prédiction est refusée.
        no_key = api.post("/predict-tabular", json=PAYLOAD)
        assert no_key.status_code == 401, no_key.text

        # 3. Cas nominal : la clé lue dans .env (comme le conteneur) donne une vraie décision.
        ok = api.post("/predict-tabular", json=PAYLOAD, headers={"X-API-Key": settings.api_key})
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["decision"] in {"alerte", "ok"}
        assert 0.0 <= body["proba_panne"] <= 1.0
