# Pas à pas apprenant — Drift InduSense, passe 2 des modules 31-32

> **Windows, macOS ou Linux.** Les blocs ci-dessous sont la voie Windows
> PowerShell. Sous macOS zsh ou Linux bash, ouvrez à côté
> [`COMMANDES_MACOS_LINUX.md`](COMMANDES_MACOS_LINUX.md) : il reprend les mêmes
> créneaux, commandes et preuves avec la syntaxe POSIX exacte.

Cette activité se déroule **J5 matin, de 09h00 à 12h30**, dans le miroir autonome
`tp_drift_indusense`. Elle prolonge PayGuard sur les capteurs InduSense. Le miroir contient ses données
dérivées, son modèle, ses tests et son propre environnement verrouillé ; ne cherchez ni dépôt GitHub ni
fichier source supplémentaire.

## Avant 09h00 — ouvrir exactement le bon dossier

1. Dans l'Explorateur Windows, placez le pack dans un chemin court, par exemple
   `%USERPROFILE%\CISIA\S3`.
2. Dans VS Code : **Fichier > Ouvrir le dossier**.
3. Choisissez
   `PACK_APPRENANTS_SPRINT3_CISIA_20260824\05_DONNEES_ET_EXERCICES\tp_drift_indusense`.
4. Dans VS Code : **Terminal > Nouveau terminal**. Le prompt doit se terminer par
   `tp_drift_indusense`.
5. Gardez ouverts `README.md`, `scripts\drift_lab.py`, `scripts\evaluate_fenetre.py`,
   `scripts\alerting_demo.py` et le dossier `reports`.

## 09h00-09h10 — préflight reproductible

Copiez ce bloc dans le **terminal PowerShell de VS Code** :

```powershell
Test-Path -LiteralPath .\pyproject.toml
Test-Path -LiteralPath .\uv.lock
Test-Path -LiteralPath .\data\reference_normale.csv
uv sync --frozen --extra dev
uv run python --version
uv run python -c "import sklearn; print(sklearn.__version__)"
git status --short -- uv.lock 2>$null
```

Attendu : trois `True`, Python **3.13.x**, scikit-learn **1.9.0** et aucune mutation de `uv.lock`.
Le dossier n'est pas nécessairement un dépôt Git : si la dernière commande ne produit rien, continuez.

## 09h10-09h50 — modèle, référence et protocole

```powershell
uv run python .\scripts\train_model.py
Get-Content -LiteralPath .\models\threshold.json
```

Notez dans votre journal : population de train, fenêtre de validation, seuil gelé, rappel, précision et
taux d'alerte. Ne comparez jamais un PSI sans écrire sa **population**, sa **référence** et son **binning**.

## 09h50-10h20 — ronde des quatre fenêtres

Exécutez les commandes une par une et notez, pour chacune, référence, PSI température, PSI pression,
rappel et taux d'alerte :

```powershell
uv run python .\scripts\drift_lab.py --fenetre 1 --reference normale
uv run python .\scripts\evaluate_fenetre.py --fenetre 1

uv run python .\scripts\drift_lab.py --fenetre 2 --reference normale
uv run python .\scripts\evaluate_fenetre.py --fenetre 2

uv run python .\scripts\drift_lab.py --fenetre 3 --reference normale
uv run python .\scripts\evaluate_fenetre.py --fenetre 3

uv run python .\scripts\drift_lab.py --fenetre janvier --reference normale
uv run python .\scripts\evaluate_fenetre.py --fenetre janvier
```

À expliquer en une phrase par cas : fenêtre témoin ; dérive de capteur ; concept drift ; changement de
régime. Un PSI élevé ne prouve pas que le modèle est dégradé, et un PSI faible ne prouve pas l'inverse.

## 10h20-10h30 — pause

Enregistrez vos notes et laissez le terminal ouvert. Ne lancez aucun autre installateur.

## 10h30-10h50 — contre-épreuve de référence

```powershell
uv run python .\scripts\drift_lab.py --fenetre janvier --reference haute
uv run python .\scripts\drift_lab.py --fenetre 2 --reference normale --machine MACH-03
```

Comparez janvier contre les deux références. Votre conclusion doit dire pourquoi une référence par
régime réduit les fausses alertes, sans masquer une dérive de capteur réelle.

## 10h50-11h15 — rapport JSON et anti-spam M32

```powershell
uv run python .\scripts\alerting_demo.py --report-out .\reports\drift_report_f2.json
Get-Content -LiteralPath .\reports\drift_report_f2.json
```

Preuve attendue : séquence **0 → 1 → 0**, une seule ligne `drift_events` et un rapport JSON lisible.
La troisième valeur `0` prouve le cooldown ; elle ne signifie pas que la dérive a disparu.

## 11h15-12h05 — tests, contrat de branchement et drift spec

```powershell
uv run python -m pytest .\tests\test_alerting_demo.py -q -p no:cacheprovider
uv run python -m pytest .\tests -q -p no:cacheprovider
Select-String -LiteralPath .\scripts\alerting_demo.py -Pattern 'drift_events','cooldown_hours','INSERT INTO'
```

La suite complète doit finir avec **11 passed**. Complétez ensuite votre drift spec : références et
régimes, fenêtre/fréquence, features/tests, seuils, cooldown, KPI métier, réaction humaine et limites.

## 12h05-12h30 — preuves à déposer

- tableau des quatre fenêtres avec référence nommée ;
- paire de rapports janvier `normale` / `haute` ;
- `reports\drift_report_f2.json` ;
- capture `0 → 1 → 0` et `11 passed` ;
- drift spec ;
- schéma `ingest → features → predict → drift_check → store/report → notify`.

## Dépannage sans muter le lock

- `No pyproject.toml found` : VS Code a ouvert le dossier parent ; rouvrez `tp_drift_indusense`.
- `ModuleNotFoundError` sur un sous-module interne de scikit-learn : redécompressez le pack dans
  `%USERPROFILE%\CISIA\S3`, puis rejouez `uv sync --frozen --extra dev`.
- Python n'est pas 3.13 : utilisez `uv run python`, jamais `python` tout court.
- CSV absent : repartez d'une copie fraîche du miroir ; ne fabriquez pas de données de remplacement.
- Rapport déjà présent : créez un nom horodaté ; ne supprimez pas une preuve existante.
- Hors ligne : utilisez le cache préparé ; si le sync reste impossible, analysez les rapports fournis et
  marquez l'exécution comme non rejouée au lieu d'inventer une sortie.
