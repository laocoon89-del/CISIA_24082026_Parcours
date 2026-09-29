# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — src/indusense/api/main.py
# [PÉDAGOGIE] MODULE  — M25 — contrat d'API, validation et preuve de readiness
# [PÉDAGOGIE] RÔLE    — Exposer le modèle derrière un contrat HTTP explicite, testable et
# [PÉDAGOGIE]           observable.
# [PÉDAGOGIE] THÉORIE — Pydantic valide la forme et les invariants avant l'appel au modèle
# [PÉDAGOGIE]           • liveness et readiness répondent à deux questions opérationnelles
# [PÉDAGOGIE]             différentes
# [PÉDAGOGIE]           • l'injection de dépendances permet d'isoler le chargement du modèle dans
# [PÉDAGOGIE]             les tests
# [PÉDAGOGIE] À VOIR  — Swagger/TestClient doivent rendre visibles les entrées, sorties et codes
# [PÉDAGOGIE]           2xx/4xx/5xx attendus.
# [PÉDAGOGIE] PIÈGE   — Une réponse 200 ne suffit pas si le schéma, la version du modèle ou la
# [PÉDAGOGIE]           normalisation sont faux.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

"""API M25 : contrat, readiness, authentification et prediction tabulaire.

Les protections de taille de corps et de debit arrivent au jalon M26.
"""

# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, status

import indusense.api.model_store as store
from indusense.api.model_store import ModelBundle, get_model_bundle
from indusense.api.schemas import PredictionResponse, TabularPredictionRequest
from indusense.config import settings
from indusense.data.loaders import normalize_machine_id
from indusense.features.temporal import add_temporal_features
from indusense.models.tabular import predict_proba, select_features


# [PÉDAGOGIE] BLOC `lifespan` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : app ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [PÉDAGOGIE] ERREUR — cette frontière distingue le chemin nominal de la stratégie explicite
    # [PÉDAGOGIE] de récupération.
    try:
        store._BUNDLE = store.load_bundle(settings.model_dir, settings.decision_threshold)
    except FileNotFoundError:
        store._BUNDLE = None
    yield


# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
app = FastAPI(title="InduSense API", version="0.1.0", lifespan=lifespan)


# [PÉDAGOGIE] BLOC `add_request_id` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : request, call_next ; preuve : l'appelant doit pouvoir vérifier
# [PÉDAGOGIE] la sortie ou l'effet de bord annoncé.
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return response


# [PÉDAGOGIE] BLOC `require_api_key` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : x_api_key ; preuve : l'appelant doit pouvoir vérifier la sortie
# [PÉDAGOGIE] ou l'effet de bord annoncé.
def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if x_api_key is None or x_api_key != settings.api_key:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cle API absente ou invalide",
        )


# [PÉDAGOGIE] BLOC `health` — unité de responsabilité : isoler un comportement nommable, testable
# [PÉDAGOGIE] et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : l'appelant doit pouvoir
# [PÉDAGOGIE] vérifier la sortie ou l'effet de bord annoncé.
@app.get("/health")
def health() -> dict:
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return {"status": "ok"}


# [PÉDAGOGIE] BLOC `ready` — frontière d'entrée : convertir une représentation externe en
# [PÉDAGOGIE] structure interne validée.
# [PÉDAGOGIE] CONTRAT — entrées : bundle ; preuve : vérifier schéma, types, ordre et erreurs
# [PÉDAGOGIE] explicites avant tout calcul aval.
@app.get("/ready")
def ready(bundle: ModelBundle | None = Depends(get_model_bundle)) -> dict:
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if bundle is None:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=503, detail="Modele non charge")
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return {"status": "ready", "model_version": bundle.version}


# [PÉDAGOGIE] BLOC `predict_tabular` — phase d'inférence ou d'évaluation : appliquer un contrat
# [PÉDAGOGIE] gelé à des observations nouvelles.
# [PÉDAGOGIE] CONTRAT — entrées : payload, bundle ; preuve : contrôler ordre des features, seuil,
# [PÉDAGOGIE] métriques et provenance du modèle.
@app.post(
    "/predict-tabular",
    response_model=PredictionResponse,
    dependencies=[Depends(require_api_key)],
)
def predict_tabular(
    payload: TabularPredictionRequest,
    bundle: ModelBundle | None = Depends(get_model_bundle),
) -> PredictionResponse:
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if bundle is None:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=503, detail="Modele non charge")

    frame = pd.DataFrame([reading.model_dump() for reading in payload.readings])
    # [PÉDAGOGIE] ERREUR — cette frontière distingue le chemin nominal de la stratégie explicite
    # [PÉDAGOGIE] de récupération.
    try:
        frame["machine"] = normalize_machine_id(payload.machine_id)
    except ValueError as exc:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    features = add_temporal_features(frame).dropna()
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if features.empty:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=422, detail="Historique insuffisant")

    model_input = select_features(features, bundle.target_col).iloc[[-1]]
    probability = float(predict_proba(bundle.model, model_input)[0])
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return PredictionResponse(
        machine_id=payload.machine_id,
        proba_panne=probability,
        decision="alerte" if probability >= bundle.threshold else "ok",
        model_version=bundle.version,
        threshold=bundle.threshold,
    )


# --- M25 TP 3 (option) : POST /predict-image ----------------------------------
# Objectif : refuser (422) tout fichier qui n'est pas réellement une image.
# Aucun modèle vision n'est déployé : la route VALIDE l'entrée, elle ne prédit rien.

# Signatures binaires (« magic bytes ») : les premiers octets qui identifient le
# format RÉEL du fichier, quels que soient son nom ou le Content-Type annoncé.
IMAGE_SIGNATURES: dict[str, bytes] = {
    "image/png": b"\x89PNG\r\n\x1a\n",  # PNG : 8 octets fixés par la norme PNG
    "image/jpeg": b"\xff\xd8\xff",  # JPEG : marqueur SOI (Start Of Image) + début de segment
}
# Nombre d'octets à lire pour comparer : la plus longue signature (8 pour PNG).
SIGNATURE_BYTES = max(len(sig) for sig in IMAGE_SIGNATURES.values())


@app.post(
    "/predict-image",  # chemin de la route ; POST car le client ENVOIE un fichier
    dependencies=[Depends(require_api_key)],  # même contrôle de clé que /predict-tabular → 401
)
async def predict_image(
    file: UploadFile,  # fichier reçu en multipart/form-data (champ de formulaire « file »)
) -> dict:
    # Type MIME DÉCLARÉ par le client (ex. "image/png") ; peut être absent ou mensonger.
    declared_type = file.content_type or ""
    # Signature attendue pour ce type ; None si le type n'est pas un format image accepté.
    expected_signature = IMAGE_SIGNATURES.get(declared_type)
    # 1er contrôle : le type annoncé doit faire partie des formats acceptés.
    if expected_signature is None:
        # 422 : la requête est bien formée, mais son contenu est inacceptable.
        raise HTTPException(
            status_code=422,
            detail=f"Type non accepté : {declared_type!r} (attendu : image/png ou image/jpeg)",
        )
    # Lecture des SEULS premiers octets : suffisant pour vérifier la signature.
    head = await file.read(SIGNATURE_BYTES)
    # 2e contrôle : fichier vide → rien à analyser.
    if not head:
        raise HTTPException(status_code=422, detail="Fichier image vide")
    # 3e contrôle : le contenu réel doit commencer par la signature du type annoncé.
    # C'est ce test qui démasque un fichier texte renommé « .png » ou mal étiqueté.
    if not head.startswith(expected_signature):
        raise HTTPException(
            status_code=422,
            detail=f"Le contenu ne correspond pas à une image {declared_type}",
        )
    # Tous les contrôles passent : on accuse réception, sans inventer de prédiction.
    return {
        "filename": file.filename,  # nom fourni par le client (information, jamais une preuve)
        "content_type": declared_type,  # type annoncé ET vérifié par la signature
        "status": "image_valide",  # résultat de la validation
        "prediction": None,  # aucun modèle vision déployé : pas de score à renvoyer
    }
