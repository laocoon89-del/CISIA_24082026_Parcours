# Reprise J6 apres dejeuner — checklist apprenant

Continuer sur la branche `reparation-<binome>` du matin. Ne pas recreer le clone,
ne pas fusionner la branche saine et ne pas regarder de corrige.

## Avant la premiere modification

- [ ] `git status` est compris et la branche courante est `reparation-*`.
- [ ] La chronologie du matin est enregistree.
- [ ] La derniere hypothese testee est nommee avec sa preuve.

## Phases 3–6

- [ ] API et securite : contrat, 401/422/429/413, readiness.
- [ ] Infra : image, Compose, healthchecks, reseau et volumes.
- [ ] Observabilite : cible Prometheus, dashboard, alerte et resolution.
- [ ] CI : pipeline honnete, lock inchange, test de non-regression.
- [ ] Rollback : retour arriere teste et preuve conservee.

## Cloture

- [ ] Stack restauree et tests cibles verts.
- [ ] Aucun secret ni journal sensible dans Git.
- [ ] PR draft ou comparaison de commits lisible.
- [ ] Post-mortem factuel, sans chercher un coupable.
- [ ] Chaque action preventive a une priorite, un responsable et une echeance.
