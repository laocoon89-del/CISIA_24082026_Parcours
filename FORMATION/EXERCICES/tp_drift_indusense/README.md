# Kit drift & métriques — InduSense (données capteurs réelles)

> **VERSION EN VIGUEUR POUR LA SESSION DU 02/09/2026.** Cette passe se joue dans ce miroir autonome
> livré avec le kit : il contient déjà les données dérivées, les scripts, les tests et un modèle régénéré
> sous **Python 3.13 / scikit-learn 1.9.0**. Il ne dépend ni du dépôt GitHub, ni des quatre fichiers sources
> bruts absents du pack. Le repo fil rouge reste utile ensuite pour le Game Day, mais ses anciens chiffres
> ne doivent pas être mélangés à ceux de ce miroir.

Transposition du TP PayGuard au fil rouge : PSI + KS sur les capteurs réels (jointure §95),
modèle en production (split temporel m8, seuil gelé par le coût), 4 fenêtres (témoin, capteur
+8 °C, concept drift, campagne haute charge) et la leçon « référence par régime ».

- **Apprenants** : `PAS_A_PAS_apprenant_indusense.md` donne l'ouverture de VS Code, les commandes,
  l'horloge J5 matin, les preuves et le dépannage sans dévoiler le corrigé.
- **Formateur** : `PAS_A_PAS_formateur_indusense.md` (+ PDF) ajoute les sorties mesurées, les trois
  leçons spécifiques et la drift spec corrigée.

Prérequis : **uv** ; ce miroir possède désormais son propre `pyproject.toml`, son `uv.lock` et sa
`.python-version`. Il ne dépend plus de l'environnement PayGuard ni du Python global du poste.
Démarrage : ouvrir PowerShell dans ce dossier, lancer `uv sync --frozen --extra dev`, vérifier
`uv run python --version` → **Python 3.13.x**, puis suivre le pas-à-pas correspondant à votre rôle :
`PAS_A_PAS_apprenant_indusense.md` en salle ; `PAS_A_PAS_formateur_indusense.md` uniquement côté formateur.
Les CSV sont déjà livrés. `scripts/build_dataset.py` documente la provenance et ne se rejoue que hors séance,
avec les quatre sources autorisées.
Vérification : `uv run python -m pytest tests/ -q` → **11 passed** avec le modèle livré ; une copie fraîche sans
`models/model.joblib` donne **10 passed, 1 skipped** jusqu'à l'entraînement.
