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
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

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
