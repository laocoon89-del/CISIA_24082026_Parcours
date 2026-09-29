"""M25 TP 3 (option) — POST /predict-image : 422 si le fichier n'est pas une image."""

import pytest
from fastapi.testclient import TestClient

from indusense.api.main import app
from indusense.config import settings

# En-tête d'authentification valide (même clé que pour /predict-tabular).
AUTH = {"X-API-Key": settings.api_key}
# Début d'un vrai fichier PNG : la signature suffit pour la validation.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
# Début d'un vrai fichier JPEG (marqueur SOI + segment APP0).
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
# Contenu texte : ce n'est pas une image.
TEXT_BYTES = b"ceci n'est pas une image"


@pytest.fixture(scope="module")
def client():
    # Un seul TestClient pour tout le fichier : l'application (et donc le modèle,
    # chargé dans `lifespan`) ne démarre qu'une fois au lieu d'une fois par test.
    with TestClient(app) as test_client:
        yield test_client


def post_file(client: TestClient, content: bytes, content_type: str, headers=AUTH):
    # `files=` construit une requête multipart/form-data avec un champ « file ».
    return client.post(
        "/predict-image",
        files={"file": ("upload", content, content_type)},
        headers=headers,
    )


def test_valid_png_returns_200(client):
    response = post_file(client, PNG_BYTES, "image/png")
    assert response.status_code == 200
    assert response.json()["status"] == "image_valide"
    assert response.json()["prediction"] is None


def test_valid_jpeg_returns_200(client):
    response = post_file(client, JPEG_BYTES, "image/jpeg")
    assert response.status_code == 200


def test_text_file_returns_422(client):
    response = post_file(client, TEXT_BYTES, "text/plain")
    assert response.status_code == 422


def test_fake_png_is_rejected_by_signature(client):
    # Le client MENT : il annonce image/png mais envoie du texte.
    # Seule la vérification de la signature binaire peut le détecter.
    response = post_file(client, TEXT_BYTES, "image/png")
    assert response.status_code == 422
    assert "ne correspond pas" in response.json()["detail"]


def test_empty_image_returns_422(client):
    response = post_file(client, b"", "image/png")
    assert response.status_code == 422


def test_missing_api_key_returns_401(client):
    # L'authentification est vérifiée AVANT le contenu du fichier.
    response = post_file(client, PNG_BYTES, "image/png", headers={})
    assert response.status_code == 401


def test_missing_file_field_returns_422(client):
    # Aucun champ « file » dans le formulaire : FastAPI refuse la requête (validation).
    response = client.post("/predict-image", headers=AUTH)
    assert response.status_code == 422
