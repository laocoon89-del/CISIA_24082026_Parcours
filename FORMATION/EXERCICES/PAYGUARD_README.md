# Distribution PayGuard — J4 apres-midi

Archive apprenant a utiliser : `tp_payguard_apprenants.zip`.

- Taille attendue : **785 614 octets**.
- SHA-256 attendu :
  `E8218BCC10DA6C2A6201AD92FF173FD5BD0A6AFBA3DEFBDE039BC9944883C305`.
- Miroir Git apprenant :
  `https://github.com/thomasfesq/CISIA_24082026_PayGuard`.

Verifier l'archive **avant** de l'extraire.

Windows PowerShell :

```powershell
Get-FileHash -Algorithm SHA256 .\FORMATION\EXERCICES\tp_payguard_apprenants.zip
Expand-Archive -LiteralPath .\FORMATION\EXERCICES\tp_payguard_apprenants.zip -DestinationPath .\tp_payguard
```

macOS zsh :

```bash
shasum -a 256 ./FORMATION/EXERCICES/tp_payguard_apprenants.zip
ditto -x -k ./FORMATION/EXERCICES/tp_payguard_apprenants.zip ./tp_payguard
```

Linux bash :

```bash
sha256sum ./FORMATION/EXERCICES/tp_payguard_apprenants.zip
unzip ./FORMATION/EXERCICES/tp_payguard_apprenants.zip -d ./tp_payguard
```

Dans les trois cas, ouvrir ensuite dans VS Code le dossier extrait qui contient
son propre `pyproject.toml` et `uv.lock`, puis exécuter
`uv sync --frozen --extra dev`. Ne pas mélanger cet environnement avec celui
d'InduSense. Sous Linux, ne pas reprendre une commande `brew` destinée à macOS.

L'archive ne contient pas le dossier formateur, les solutions, le modele ou le
seuil entraines, ni les rapports pre-calcules. Les labels et
`evaluate_semaine.py` ne sont a ouvrir qu'au moment annonce par le formateur.
