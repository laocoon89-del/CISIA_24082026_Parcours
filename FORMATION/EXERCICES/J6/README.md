# Kit apprenant Game Day J6

Contenu autorise : briefing, guide apprenant, gabarit de post-mortem et bundle
Git autonome.

Bundle : `J6-gameday.bundle`

- Taille : **7 662 402 octets**.
- SHA-256 :
  `5D65DF7824F410190059B743A542458E45007ED6E3C1AC480F6B7DEA1E117558`.
- Refs incluses : branche cassee `J6-gameday` et tag sain certifie
  `v1.0-sain`.
- Commit de la branche cassee : `4f78a522a7100ed2dd8cfd9cd553e138d4e61d46`.

Demarrage Windows, depuis la racine du parcours :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\formation\demarrer_gameday.ps1 -Binome equipe-1
```

Demarrage macOS zsh ou Linux bash, depuis la racine du parcours :

```bash
bash scripts/formation/demarrer_gameday.sh equipe-1
```

Le bundle permet de travailler meme si GitHub est indisponible. Le tag sain est
volontairement present pour l'analyse forensic ; aucune branche reparee ne l'est.
Les scripts renomment le remote du bundle en `bundle-local` pour eviter un push
vers un fichier local. La branche et les commits sont des preuves locales. Un
remote de collaboration n'est ajoute que si le formateur fournit explicitement
son URL et sa consigne le jour J.
