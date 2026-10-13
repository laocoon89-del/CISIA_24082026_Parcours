# 07 — J4 matin — M29–M30

> Windows, macOS ou Linux : suivre la section Prefect/idempotence du
> [guide multiplateforme](../GUIDE_MULTIPLATEFORME_APPRENANT.md).

Objectif : passer d'un script a un pipeline orchestre, rejouable et idempotent.

Recu par le jalon : stack M28, donnees locales et demo d'idempotence.
`flows/pipeline.py` est volontairement absent : il est a creer pendant M29 et
sa version de reference n'apparait qu'au jalon 08. Aucun corrige PayGuard.

A faire : creer `flows/pipeline.py`, decomposer en tasks/flow, nommer les runs,
gerer reprise et cache, puis prouver qu'un second passage ne duplique pas les
sorties.

Avant la preuve, forcer le profil Prefect local `ephemeral` comme indique dans
le guide multiplateforme. Ne lancer la premiere commande qu'apres avoir cree
`flows/pipeline.py` pendant M29.

Preuve :

```powershell
uv run python flows/pipeline.py
uv run python scripts/demo_prefect_idempotence.py
git status --short
```

Rattrapage : pipeline local sequentiel avec traces claires ; l'UI Prefect et les
politiques de retry avancees sont de la reserve.
