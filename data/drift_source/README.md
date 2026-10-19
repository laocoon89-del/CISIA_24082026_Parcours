# Provenance des données de dérive InduSense

Ce dossier contient un jeu de données **pédagogique et synthétique** préparé pour le Sprint 3 CISIA.
Il ne provient ni d'un système industriel réel, ni d'AIDium, ni d'un apprenant, et ne contient aucune
donnée bancaire réelle.

Le fichier `releves_incidents.csv` a été pseudonymisé avant publication le 23 août 2026 :

- `operator_name` utilise des identifiants opaques `OPERATEUR-01` à `OPERATEUR-11` ;
- `operator_badge` utilise des identifiants opaques `BADGE-01` à `BADGE-11` ;
- les 283 incidents, dates, machines, niveaux de sévérité, commentaires et équipes ont été conservés ;
- ces deux colonnes d'opérateur sont exclues des features du modèle et de l'analyse de dérive.

Empreinte SHA-256 du CSV publié :
`EE50AAD56FA902E99445740CFE1F0EA1871195D3C3F0A90212273F9A3AC93903`.

La source maître et les éléments de fabrication restent conservés localement dans le kit formateur ;
ils ne sont pas requis pour réaliser les exercices apprenants.
