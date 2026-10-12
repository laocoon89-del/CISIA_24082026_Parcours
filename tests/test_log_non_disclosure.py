"""M26 TP 3 — non-divulgation : les logs de l'API ne contiennent ni clé, ni payload.

Ce test NE prouve PAS l'existence d'un audit log (qui reste « Planifié v0 ») :
il prouve seulement que ce qui est journalisé aujourd'hui ne divulgue rien.
"""

import logging

from fastapi.testclient import TestClient
from loguru import logger

from indusense.api.main import app
from indusense.config import settings

# Valeurs « traçantes » : uniques, faciles à retrouver si elles fuitaient dans un log.
WRONG_KEY = "cle-invalide-TRACEUR-7f3a"  # clé fausse envoyée volontairement
MACHINE_TRACER = "MACH-07"
TEMPERATURE_TRACER = 123.4567  # valeur unique et bornée (-20 ≤ t ≤ 200)
PRESSURE_TRACER = 234.5678  # valeur unique et bornée (0 < p ≤ 400)


def build_payload() -> dict:
    # 8 relevés horaires valides ; les deux premiers portent les valeurs traçantes.
    readings = [
        {
            "timestamp": f"2025-02-01T0{hour}:00:00",
            "temperature": TEMPERATURE_TRACER if hour < 2 else 50.0 + hour,
            "pressure_bar": PRESSURE_TRACER if hour < 2 else 195.0 + hour,
        }
        for hour in range(8)
    ]
    return {"machine_id": MACHINE_TRACER, "readings": readings}


def test_logs_do_not_disclose_api_key_or_payload(caplog):
    captured: list[str] = []
    # Capte TOUT ce que loguru émet (niveau DEBUG et plus), avec le contexte (request_id).
    sink_id = logger.add(lambda message: captured.append(str(message)), level="DEBUG")
    caplog.set_level(logging.DEBUG)  # capte aussi le module `logging` standard
    try:
        with TestClient(app) as client:  # le démarrage (lifespan) écrit déjà des logs
            payload = build_payload()
            ok = client.post(
                "/predict-tabular", json=payload, headers={"X-API-Key": settings.api_key}
            )
            refused = client.post(
                "/predict-tabular", json=payload, headers={"X-API-Key": WRONG_KEY}
            )
    finally:
        logger.remove(sink_id)

    # Les requêtes ont bien été traitées (sinon le test ne prouverait rien).
    assert ok.status_code == 200
    assert refused.status_code == 401

    all_logs = "\n".join(captured) + "\n" + caplog.text
    # Garde-fou anti-test vide : la capture fonctionne (le démarrage est journalisé).
    assert "Modèle chargé" in all_logs or "Aucun modèle" in all_logs

    # Non-divulgation : aucune clé (valide ou non) ni aucune valeur du payload.
    for secret in (settings.api_key, WRONG_KEY):
        assert secret not in all_logs
    for value in (str(TEMPERATURE_TRACER), str(PRESSURE_TRACER)):
        assert value not in all_logs
