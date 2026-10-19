# TP drift InduSense — mode apprenant

> **Choisir son système.** Le pas à pas principal affiche les commandes Windows
> PowerShell. Sur macOS zsh ou Linux bash, garder la même horloge et ouvrir en
> parallèle [`COMMANDES_MACOS_LINUX.md`](COMMANDES_MACOS_LINUX.md), qui fournit
> chaque bloc équivalent sans changer les résultats attendus.

Ce dossier est le miroir autonome utilisé pendant le J5 matin (modules 31-32). Il contient les données,
le modèle, les scripts et les tests nécessaires. Il ne dépend ni du dépôt GitHub ni du TP PayGuard.

## Ouvrir le bon dossier

1. Décompressez le pack dans un dossier court : `C:\CISIA\Sprint3` sous Windows,
   ou `~/CISIA/Sprint3` sous macOS/Linux.
2. Ouvrez **Visual Studio Code** depuis le menu Démarrer, le Dock ou le menu des applications.
3. Dans VS Code : **Fichier > Ouvrir le dossier…** puis choisissez
   `PACK_APPRENANTS_SPRINT3_CISIA_20260824\05_DONNEES_ET_EXERCICES\tp_drift_indusense`.
4. Dans VS Code : **Terminal > Nouveau terminal**. Le terminal doit afficher le chemin du dossier
   `tp_drift_indusense` avant toute commande.

## Préflight reproductible

Sous Windows, dans PowerShell, exécutez une ligne à la fois :

```powershell
uv sync --frozen --extra dev
if ($LASTEXITCODE -ne 0) { throw "Installation verrouillée impossible." }
uv run python --version
uv run python -m pytest tests/ -q
```

Résultats attendus avant l'exercice : Python **3.13.x** et **11 tests réussis**. Le fichier `uv.lock`
ne doit pas changer. Si le chemin contient OneDrive, des accents ou est très long et que l'installation
échoue, recopiez le dossier dans `C:\CISIA\Sprint3\tp_drift_indusense`, puis recommencez.
Sous macOS/Linux, utilisez `~/CISIA/Sprint3/tp_drift_indusense` et le préflight
de `COMMANDES_MACOS_LINUX.md`.

## Support à suivre

Ouvrez `PAS_A_PAS_apprenant_indusense.md`. Il donne l'horloge, les commandes, les preuves à produire
et le dépannage sans livrer les résultats de référence du formateur. Les fichiers produits pendant le
TP vont dans `reports\` ; conservez-les comme preuves et ne remplacez pas les fichiers du modèle livré.
