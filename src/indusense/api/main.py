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

# =============================================================================
#  src/indusense/api/main.py  —  L'APPLICATION FastAPI (le cœur de l'API)
# -----------------------------------------------------------------------------
#  Place dans le projet : Sprint 3, module API (n°25) + sécurité (n°26).
#
#  RÔLE DU FICHIER
#  C'est ici qu'on assemble TOUT : on crée l'application web, on charge le modèle
#  au démarrage, on branche les protections (middlewares, clé API, anti-flood),
#  l'observabilité (logs + métriques Prometheus), et on définit les « routes »
#  (les URL que les clients peuvent appeler) :
#    - GET  /health          : « le serveur est-il VIVANT ? » (liveness)
#    - GET  /ready           : « le serveur est-il PRÊT à servir ? » (readiness)
#    - POST /predict-tabular : prédiction de panne à partir de relevés capteurs
#    - POST /predict-image   : analyse d'une image (validation du fichier ici)
#    - GET  /metrics         : métriques techniques pour Prometheus (auto)
#
#  FASTAPI EN DEUX MOTS
#  Un framework web Python moderne et rapide. On y décrit chaque route avec un
#  décorateur (`@app.get(...)`, `@app.post(...)`) au-dessus d'une fonction.
#  FastAPI s'occupe de lire la requête, valider les données (avec Pydantic),
#  appeler notre fonction, et renvoyer la réponse au format JSON.
#
#  RAPPEL DES CODES HTTP UTILISÉS ICI
#    200 OK                    : tout va bien (succès par défaut).
#    401 Unauthorized          : authentification manquante/invalide (clé API).
#    413 Payload Too Large      : corps de requête trop volumineux (middleware).
#    422 Unprocessable Entity   : données comprises mais invalides (validation).
#    429 Too Many Requests      : trop de requêtes (limiteur de débit).
#    503 Service Unavailable    : service temporairement indisponible (pas de modèle).
# =============================================================================

# Annotations de type modernes (voir explication dans les autres fichiers).
# [PÉDAGOGIE] DÉPENDANCE — __future__ : apporte une dépendance explicitement visible au lecteur.
from __future__ import annotations

# `uuid` : module standard pour générer des identifiants UNIQUES et aléatoires.
# On l'utilise pour donner un identifiant à chaque requête (traçabilité des logs).
import uuid

# `asynccontextmanager` : transforme une fonction en « gestionnaire de contexte »
# asynchrone. FastAPI s'en sert pour le `lifespan` : du code à exécuter AU
# DÉMARRAGE (avant le `yield`) puis à L'ARRÊT (après le `yield`) de l'application.
from contextlib import asynccontextmanager

# `pandas` (alias `pd`) : la bibliothèque reine pour manipuler des tableaux de
# données (« DataFrame »). On construit un DataFrame à partir des relevés reçus,
# puis on calcule dessus les features temporelles avant de prédire.
import pandas as pd

# On importe les briques FastAPI dont on a besoin :
#   - `Depends`       : déclare une « dépendance » à injecter (clé API, modèle…).
#   - `FastAPI`       : la classe de l'application elle-même.
#   - `Header`        : pour lire une valeur d'en-tête HTTP (ex. X-API-Key).
#   - `HTTPException` : pour renvoyer proprement une erreur HTTP (code + message).
#   - `Request`       : l'objet requête entrante (en-têtes, IP, etc.).
#   - `UploadFile`    : représente un fichier téléversé (pour /predict-image).
#   - `status`        : constantes nommées des codes HTTP (ex. HTTP_401_...).
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, status

# `loguru.logger` : une bibliothèque de JOURNALISATION (logs) très simple et
# agréable. On l'utilise pour tracer ce qui se passe (modèle chargé, etc.) et,
# plus loin, pour attacher un identifiant de requête à chaque ligne de log.
from loguru import logger

# `Instrumentator` (de prometheus-fastapi-instrumentator) : un outil qui ajoute
# AUTOMATIQUEMENT des métriques à l'API (nombre de requêtes, latences, codes de
# réponse…) et les expose sur une route /metrics au format attendu par
# Prometheus (un système de supervision/monitoring très répandu). Cela permet de
# SURVEILLER l'API en production sans écrire soi-même le code de comptage.
from prometheus_fastapi_instrumentator import Instrumentator

# On importe le MODULE `model_store` entier sous l'alias `store`. Pourquoi le
# module entier et pas juste des fonctions ? Parce qu'on doit ÉCRIRE dans sa
# variable globale `store._BUNDLE` au démarrage. En passant par `store.`, on
# modifie bien la variable du module partagé (et non une copie locale).
import indusense.api.model_store as store

# On importe aussi directement la classe `ModelBundle` (pour annoter les types)
# et la fonction `get_model_bundle` (pour l'injecter via Depends).
from indusense.api.model_store import ModelBundle, get_model_bundle

# Les schémas Pydantic définissant le contrat d'entrée/sortie de /predict-tabular.
from indusense.api.schemas import PredictionResponse, TabularPredictionRequest

# Les garde-fous de sécurité définis dans security.py :
#   - `limit_body_size` : middleware anti-payload-géant (413).
#   - `rate_limit`      : dépendance anti-flood (429).
#   ⚠️ On branche `rate_limit_dependency` (et NON `rate_limit`) : voir sa
#      docstring — brancher `rate_limit` directement exposerait `limit`/`window`
#      en paramètres de requête (`?limit=100000` contournerait le garde-fou).
from indusense.api.security import limit_body_size, rate_limit_dependency

# La configuration centrale du projet (chemins, clé API, seuil de décision…).
from indusense.config import settings

# Fonction qui met un identifiant machine au format canonique (ex. "M-7" -> "MACH-07").
from indusense.data.loaders import normalize_machine_id

# Fonction qui ajoute les features temporelles (lags + moyennes glissantes).
from indusense.features.temporal import add_temporal_features

# Deux fonctions du modèle tabulaire :
#   - `predict_proba`   : renvoie la probabilité de panne à partir des features.
#   - `select_features` : isole les colonnes à donner au modèle (retire la cible).
from indusense.models.tabular import predict_proba, select_features


# -----------------------------------------------------------------------------
#  LIFESPAN : ce qu'on fait au DÉMARRAGE et à l'ARRÊT de l'application.
# -----------------------------------------------------------------------------
# Le décorateur `@asynccontextmanager` permet d'avoir du code « avant » et
# « après » le `yield`. FastAPI appellera ce gestionnaire automatiquement :
# le code AVANT `yield` s'exécute au démarrage ; le code APRÈS (ici, rien)
# s'exécuterait à l'extinction. C'est l'endroit idéal pour charger le modèle.
# [PÉDAGOGIE] BLOC `lifespan` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : app ; preuve : l'appelant doit pouvoir vérifier la sortie ou
# [PÉDAGOGIE] l'effet de bord annoncé.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On tente de charger le modèle UNE FOIS, au démarrage du serveur.
    # [PÉDAGOGIE] ERREUR — cette frontière distingue le chemin nominal de la stratégie explicite
    # [PÉDAGOGIE] de récupération.
    try:
        # On charge le bundle (modèle + métadonnées + seuil) et on le RANGE dans
        # la variable globale du module `store`. Comme `get_model_bundle()` relit
        # cette même variable, toutes les routes verront désormais le modèle.
        #   - `settings.model_dir`         : dossier où trouver le modèle.
        #   - `settings.decision_threshold`: seuil de décision configuré.
        store._BUNDLE = store.load_bundle(settings.model_dir, settings.decision_threshold)
        # On trace dans les logs que tout s'est bien passé.
        logger.info("Modèle chargé")
    except FileNotFoundError:
        # Si les fichiers du modèle sont introuvables (ex. pas encore entraîné),
        # on ne fait PAS planter le serveur : il démarre quand même, mais sans
        # modèle. On laisse `_BUNDLE` à None...
        store._BUNDLE = None
        # ...et on prévient via un avertissement. Conséquence : /ready répondra
        # 503 (pas prêt) tant qu'aucun modèle n'est disponible. Démarrer malgré
        # tout permet par exemple aux sondes /health de fonctionner.
        logger.warning("Aucun modèle — /ready renverra 503")
    # `yield` = « le démarrage est terminé, l'application tourne maintenant ».
    # Tout ce qui serait écrit APRÈS ce yield s'exécuterait à l'arrêt (nettoyage,
    # fermeture de connexions…). Ici on n'a rien de spécial à faire à l'arrêt.
    yield


# -----------------------------------------------------------------------------
#  CRÉATION DE L'APPLICATION + branchement des middlewares et de l'observabilité.
# -----------------------------------------------------------------------------
# On instancie l'application FastAPI. On lui donne un titre et une version (qui
# apparaîtront dans la doc auto Swagger), et on lui passe notre `lifespan` pour
# qu'elle charge le modèle au démarrage.
# [PÉDAGOGIE] CONSTANTE / CONTRAT — cette valeur nommée centralise un choix partagé au lieu de le
# [PÉDAGOGIE] disperser.
app = FastAPI(title="InduSense API", version="0.1.0", lifespan=lifespan)

# Le garde-fou `limit_body_size` sera enregistré APRÈS les autres middlewares,
# plus bas. Starlette exécute le dernier middleware ajouté en premier : cet ordre
# garantit qu'un Content-Length invalide est rejeté avant que Prometheus tente de
# l'interpréter pour sa métrique de taille de requête.

# On active l'instrumentation Prometheus :
#   - `.instrument(app)` : ajoute la collecte automatique des métriques.
#   - `.expose(app, endpoint="/metrics", include_in_schema=False)` : publie ces
#     métriques sur la route GET /metrics. `include_in_schema=False` cache cette
#     route technique de la documentation Swagger (elle ne concerne pas les
#     utilisateurs « métier », seulement les outils de supervision).
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# -----------------------------------------------------------------------------
#  MIDDLEWARE : attacher un identifiant unique à chaque requête (traçabilité).
# -----------------------------------------------------------------------------
# Le décorateur enregistre cette fonction comme middleware HTTP : elle s'exécute
# pour chaque requête, autour de l'appel à la route.
# [PÉDAGOGIE] BLOC `add_request_id` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : request, call_next ; preuve : l'appelant doit pouvoir vérifier
# [PÉDAGOGIE] la sortie ou l'effet de bord annoncé.
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # On cherche un identifiant fourni par le client dans l'en-tête "X-Request-ID".
    # S'il n'en fournit pas, on en GÉNÈRE un nouveau, unique, avec uuid4().
    # Intérêt : pouvoir suivre UNE requête précise à travers tous les logs, et la
    # corréler avec ce que voit le client (utile pour le débogage en production).
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # `logger.contextualize(request_id=rid)` ajoute automatiquement ce `request_id`
    # à TOUTES les lignes de log émises pendant le traitement de cette requête.
    # Le bloc `with` garantit que ce contexte est bien retiré à la fin.
    # [PÉDAGOGIE] RESSOURCE — le gestionnaire de contexte garantit ouverture et libération, même
    # [PÉDAGOGIE] en cas d'exception.
    with logger.contextualize(request_id=rid):
        # On laisse la requête poursuivre vers la route et on récupère la réponse.
        response = await call_next(request)

    # On renvoie aussi l'identifiant au client dans l'en-tête de réponse, pour
    # qu'il puisse le noter et le communiquer en cas de problème.
    response.headers["X-Request-ID"] = rid
    # On retourne la réponse (éventuellement enrichie) au client.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return response


# Enregistré en dernier, ce garde-fou devient la couche HTTP la plus externe.
# Il protège donc aussi les middlewares d'observabilité contre les en-têtes de
# taille malformés, puis laisse passer les requêtes valides vers la chaîne.
app.middleware("http")(limit_body_size)


# -----------------------------------------------------------------------------
#  DÉPENDANCE D'AUTHENTIFICATION : exiger une clé API valide (-> 401 sinon).
# -----------------------------------------------------------------------------
# Cette fonction sera branchée via `Depends(require_api_key)` sur les routes
# sensibles. FastAPI l'exécutera AVANT la route ; si elle lève une exception,
# la route n'est jamais atteinte.
#   - `x_api_key` : FastAPI lit pour nous l'en-tête HTTP "X-API-Key" (grâce à
#     `Header(None, alias="X-API-Key")`) et nous le donne. `None` = valeur par
#     défaut si l'en-tête est absent.
# [PÉDAGOGIE] BLOC `require_api_key` — unité de responsabilité : isoler un comportement nommable,
# [PÉDAGOGIE] testable et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : x_api_key ; preuve : l'appelant doit pouvoir vérifier la sortie
# [PÉDAGOGIE] ou l'effet de bord annoncé.
def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    # Clé absente OU invalide -> 401 (et non 422) : statut sémantiquement correct pour l'auth.
    # Détail pédagogique : on choisit 401 (« Unauthorized » = non authentifié)
    # plutôt que 422 (« données invalides »), car ici le problème n'est pas la
    # FORME de la donnée mais le fait que l'appelant n'a pas prouvé son identité.
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if x_api_key is None or x_api_key != settings.api_key:
        # On compare la clé reçue à la clé attendue (stockée dans la config). Si
        # elle manque ou ne correspond pas, on refuse l'accès avec un message clair.
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé API absente ou invalide"
        )


# -----------------------------------------------------------------------------
#  ROUTE /health — « LIVENESS » : le serveur est-il vivant ?
# -----------------------------------------------------------------------------
# `@app.get("/health")` déclare une route accessible en GET sur l'URL /health.
# [PÉDAGOGIE] BLOC `health` — unité de responsabilité : isoler un comportement nommable, testable
# [PÉDAGOGIE] et réutilisable.
# [PÉDAGOGIE] CONTRAT — entrées : aucun argument explicite ; preuve : l'appelant doit pouvoir
# [PÉDAGOGIE] vérifier la sortie ou l'effet de bord annoncé.
@app.get("/health")
def health() -> dict:
    # On renvoie un simple dictionnaire (FastAPI le convertit en JSON, code 200).
    # Cette sonde répond « ok » DÈS QUE le processus tourne, SANS vérifier le
    # modèle. C'est volontaire : un orchestrateur (ex. Kubernetes) l'utilise pour
    # savoir si le conteneur est vivant ; si /health échoue, il redémarre le pod.
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return {"status": "ok"}


# -----------------------------------------------------------------------------
#  ROUTE /ready — « READINESS » : le serveur est-il PRÊT à traiter des requêtes ?
# -----------------------------------------------------------------------------
# [PÉDAGOGIE] BLOC `ready` — frontière d'entrée : convertir une représentation externe en
# [PÉDAGOGIE] structure interne validée.
# [PÉDAGOGIE] CONTRAT — entrées : bundle ; preuve : vérifier schéma, types, ordre et erreurs
# [PÉDAGOGIE] explicites avant tout calcul aval.
@app.get("/ready")
def ready(bundle: ModelBundle | None = Depends(get_model_bundle)) -> dict:
    # Différence clé avec /health : ici on vérifie une vraie DÉPENDANCE métier,
    # le modèle. FastAPI nous l'injecte via `Depends(get_model_bundle)`.
    # Si le modèle n'est pas chargé (`bundle is None`), le service N'EST PAS prêt :
    # on répond 503 (« Service Unavailable »). Un orchestrateur cessera alors de
    # nous envoyer du trafic tant qu'on n'est pas prêt, sans pour autant nous tuer.
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if bundle is None:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=503, detail="Modèle non chargé")
    # Sinon, on est prêt : on renvoie « ready » et la version du modèle chargé
    # (pratique pour vérifier rapidement quel modèle tourne).
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return {"status": "ready", "model_version": bundle.version}


# -----------------------------------------------------------------------------
#  ROUTE /predict-tabular — la PRÉDICTION DE PANNE (le cœur métier de l'API).
# -----------------------------------------------------------------------------
# Décortiquons le décorateur :
#   - POST sur /predict-tabular (POST car le client ENVOIE des données).
#   - `response_model=PredictionResponse` : FastAPI VALIDERA et formatera la
#     réponse selon ce schéma (garantit le contrat de sortie + doc auto).
#   - `dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)]` :
#     avant d'exécuter la route, FastAPI applique D'ABORD la vérification de clé
#     API (401 si invalide) PUIS le limiteur de débit (429 si trop de requêtes).
#     (On branche `rate_limit_dependency`, pas `rate_limit` : cf. sa docstring —
#     brancher la fonction paramétrée exposerait `?limit=` et la contournerait.)
#     Mettre ces dépendances ici (et pas en argument) signifie « exécute-les
#     pour leur EFFET de contrôle, on n'a pas besoin de leur valeur de retour ».
# [PÉDAGOGIE] BLOC `predict_tabular` — phase d'inférence ou d'évaluation : appliquer un contrat
# [PÉDAGOGIE] gelé à des observations nouvelles.
# [PÉDAGOGIE] CONTRAT — entrées : payload, bundle ; preuve : contrôler ordre des features, seuil,
# [PÉDAGOGIE] métriques et provenance du modèle.
@app.post(
    "/predict-tabular",
    response_model=PredictionResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)],
)
def predict_tabular(
    # `payload` : le corps JSON de la requête, automatiquement validé par Pydantic
    # selon le schéma `TabularPredictionRequest` (machine_id + >= 7 relevés).
    # Si les données sont invalides, FastAPI renvoie 422 AVANT même d'entrer ici.
    payload: TabularPredictionRequest,
    bundle: ModelBundle | None = Depends(get_model_bundle),
) -> PredictionResponse:
    # Garde-fou : si aucun modèle n'est chargé, on ne peut pas prédire -> 503.
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if bundle is None:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    # On transforme la liste de relevés (objets Pydantic) en un tableau pandas.
    #   - `r.model_dump()` convertit chaque relevé en dictionnaire simple.
    #   - On en fait une LISTE de dictionnaires, que pandas range en lignes.
    # Résultat : un DataFrame avec les colonnes timestamp, temperature, pressure_bar.
    df = pd.DataFrame([r.model_dump() for r in payload.readings])

    # Canonicalisation au bord : un client peut envoyer M-7 / MACH_07 (cf. 95 §2).
    # On normalise vers la clé interne ``machine`` ; ``machine_id`` brut est conservé en sortie.
    # Détail : « au bord » = à l'entrée de l'API, on nettoie tout de suite l'ID pour
    # que tout le reste du pipeline travaille sur un format unique et fiable.
    # [PÉDAGOGIE] ERREUR — cette frontière distingue le chemin nominal de la stratégie explicite
    # [PÉDAGOGIE] de récupération.
    try:
        # `normalize_machine_id` met l'ID au format canonique "MACH-0N". On range
        # cette valeur unique dans une nouvelle colonne "machine" attendue par les
        # fonctions de features (qui regroupent les relevés PAR machine).
        df["machine"] = normalize_machine_id(payload.machine_id)
    except ValueError as exc:
        # Si l'ID ne contient aucun numéro exploitable, `normalize_machine_id` lève
        # une `ValueError`. On la transforme en erreur HTTP 422 (donnée invalide),
        # avec le message d'origine. `from exc` garde le lien vers l'erreur initiale
        # (utile dans les logs pour comprendre la cause).
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # On calcule les FEATURES TEMPORELLES (lags + moyennes glissantes), puis on
    # retire les lignes incomplètes avec `.dropna()`. Les premières lignes ont
    # forcément des features manquantes (pas assez de passé pour calculer un lag 6
    # ou une moyenne sur 6) : on les écarte pour ne garder que des lignes exploitables.
    feats = add_temporal_features(df).dropna()

    # Si, après nettoyage, il ne reste AUCUNE ligne valide, c'est que l'historique
    # fourni était insuffisant (trop peu de relevés pour calculer les features sur
    # au moins une mesure). On répond 422 « Historique insuffisant ». Cela complète
    # la borne `min_length=7` du schéma : la borne filtre en amont, ce test attrape
    # les cas limites restants (ex. doublons d'horodatage réduisant l'historique utile).
    # [PÉDAGOGIE] DÉCISION — cette condition matérialise une règle testable ; lire séparément le
    # [PÉDAGOGIE] cas vrai et le cas faux.
    if feats.empty:
        # [PÉDAGOGIE] FAIL FAST — refuser ici empêche un état invalide de contaminer les étapes
        # [PÉDAGOGIE] suivantes.
        raise HTTPException(status_code=422, detail="Historique insuffisant")

    # On prépare l'entrée du modèle :
    #   - `select_features(feats, bundle.target_col)` retire les colonnes qui ne
    #     sont pas des features (dont la colonne cible) : on ne donne au modèle
    #     que les variables explicatives.
    #   - `.iloc[[-1]]` ne garde que la DERNIÈRE ligne (la mesure la plus récente) :
    #     c'est sur l'état le plus actuel de la machine qu'on veut prédire. Les
    #     doubles crochets `[[-1]]` conservent un DataFrame (et non une simple
    #     ligne), format attendu par le modèle.
    X = select_features(feats, bundle.target_col).iloc[[-1]]

    # On demande au modèle la PROBABILITÉ de panne pour cette dernière mesure.
    #   - `predict_proba(...)` renvoie un tableau ; `[0]` prend le premier élément.
    #   - `float(...)` convertit ce résultat (type numpy) en nombre Python standard,
    #     attendu par le schéma de réponse (et propre à sérialiser en JSON).
    proba = float(predict_proba(bundle.model, X)[0])

    # On construit et renvoie la réponse, conforme au schéma `PredictionResponse` :
    # [PÉDAGOGIE] SORTIE — cette valeur constitue le contrat remis à l'appelant ; son type et son
    # [PÉDAGOGIE] sens doivent rester stables.
    return PredictionResponse(
        # On renvoie l'ID machine TEL QUE fourni par le client (pas la version
        # normalisée) : il s'y retrouve plus facilement.
        machine_id=payload.machine_id,
        # La probabilité de panne calculée.
        proba_panne=proba,
        # La DÉCISION : si la proba atteint/dépasse le seuil -> "alerte", sinon "ok".
        # C'est ici qu'une probabilité (nombre) devient une recommandation lisible.
        decision="alerte" if proba >= bundle.threshold else "ok",
        # La version du modèle (traçabilité).
        model_version=bundle.version,
        # Le seuil utilisé (transparence sur la règle de décision).
        threshold=bundle.threshold,
    )


# --- M25 TP 3 (option) : POST /predict-image ----------------------------------
# Version personnelle (remplace celle du jalon 04, qui ne vérifiait que le
# Content-Type déclaré) : on contrôle la signature binaire réelle du fichier.
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
    # Clé API (401) puis anti-flood (429, M26) : mêmes protections que /predict-tabular.
    dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)],
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
