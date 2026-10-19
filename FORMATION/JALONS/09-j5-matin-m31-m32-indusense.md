# 09 — J5 matin — M31–M32 InduSense

> Windows, macOS ou Linux : suivre la section drift InduSense du
> [guide multiplateforme](../GUIDE_MULTIPLATEFORME_APPRENANT.md).

Objectif : transferer la methode de drift vers les capteurs InduSense.

Recu par le jalon : le TP autonome
`FORMATION/EXERCICES/tp_drift_indusense`, avec donnees de reference et fenetres,
fiche TP, scripts de travail et modele de rapport. Aucun dashboard final.

A faire : choisir la reference, calculer PSI par feature et fenetre, separer
drift de donnees et baisse de performance, eviter toute reponse automatique.

Preuve, depuis la racine d'une copie locale courte du TP autonome et non depuis
la racine du depot InduSense :

```text
uv sync --frozen --extra dev
uv run python scripts/train_model.py
uv run python scripts/drift_lab.py --fenetre 1 --reference normale
uv run python scripts/evaluate_fenetre.py --fenetre 1
uv run python -m pytest tests -q -p no:cacheprovider
```

Les scripts et tests places a la racine par le jalon suivant ne sont pas
attendus au jalon 09 et ne font pas partie de cette preuve.

Rattrapage : une reference, une fenetre, une feature, une decision ; les fenetres
supplementaires forment la reserve.

### Garde-fou Windows : chemin court

Le TP autonome doit etre place dans un chemin court, par exemple
`C:\CISIA\tp_drift_indusense`. Un checkout tres profond peut depasser la limite
de chargement d'une extension compilee scikit-learn et produire un trompeur
`ModuleNotFoundError: ..._datasets_pair` alors que le fichier est present.
Deplacer/copier le TP vers un chemin court, puis relancer `uv sync --frozen
--extra dev`; ne pas modifier le lock pour masquer ce probleme de chemin.
