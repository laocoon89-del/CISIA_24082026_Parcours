# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — scripts/formation/demarrer_gameday.ps1
# [PÉDAGOGIE] MODULE  — J6 — Game Day, diagnostic et réponse à incident
# [PÉDAGOGIE] RÔLE    — Préparer un espace de travail isolé et vérifiable sans révéler la panne à
# [PÉDAGOGIE]           rechercher.
# [PÉDAGOGIE] THÉORIE — préserver les preuves précède toute tentative de correction
# [PÉDAGOGIE]           • une branche dédiée rend l'enquête réversible et auditable
# [PÉDAGOGIE]           • un état sain de référence aide à distinguer symptôme, cause et
# [PÉDAGOGIE]             correction
# [PÉDAGOGIE] À VOIR  — Les contrôles doivent confirmer dépôt, branche, tag de référence et
# [PÉDAGOGIE]           neutralisation des pushes accidentels.
# [PÉDAGOGIE] PIÈGE   — Ne jamais écrire dans le bundle de provenance ni commenter ici la liste
# [PÉDAGOGIE]           des incidents cachés.
# [PÉDAGOGIE] GARDE   — Toutes les lignes marquées [PÉDAGOGIE] sont des commentaires : elles
# [PÉDAGOGIE]           guident la lecture sans changer l'exécution.
# [PÉDAGOGIE] ============================================================================

# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
[CmdletBinding()]
# [PÉDAGOGIE] CONTRAT — les paramètres rendent les entrées du script explicites et validables.
param(
    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    [Parameter(Mandatory = $true)]
    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    [string]$Binome,

    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    [string]$Destination
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
)

# [PÉDAGOGIE] FAIL FAST — arrêter sur la première erreur évite de produire une fausse réussite.
$ErrorActionPreference = 'Stop'
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
$root = (& git rev-parse --show-toplevel 2>$null)
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0 -or -not $root) {
    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    throw 'Lancez ce script depuis le depot du parcours.'
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
}

# [PÉDAGOGIE] ÉTAT LOCAL — nommer cette valeur rend la décision suivante lisible et évite une
# [PÉDAGOGIE] constante cachée.
$bundle = Join-Path $root 'FORMATION/EXERCICES/J6/J6-gameday.bundle'
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if (-not (Test-Path -LiteralPath $bundle)) { throw "Bundle absent : $bundle" }

# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if (-not $Destination) {
    # [PÉDAGOGIE] ÉTAT LOCAL — nommer cette valeur rend la décision suivante lisible et évite une
    # [PÉDAGOGIE] constante cachée.
    $Destination = Join-Path (Split-Path -Parent $root) "CISIA_J6_GAMEDAY_$Binome"
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
}
# [PÉDAGOGIE] ÉTAT LOCAL — nommer cette valeur rend la décision suivante lisible et évite une
# [PÉDAGOGIE] constante cachée.
$absoluteDestination = [System.IO.Path]::GetFullPath($Destination)
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if (Test-Path -LiteralPath $absoluteDestination) {
    # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
    # [PÉDAGOGIE] autorise la suite.
    throw "Destination deja presente, aucune ecriture : $absoluteDestination"
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
}

# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
& git clone -b J6-gameday $bundle $absoluteDestination
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0) { throw 'Clone du bundle Game Day echoue.' }

# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
& git -C $absoluteDestination remote rename origin bundle-local
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0) { throw 'Renommage du remote local echoue.' }
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
& git -C $absoluteDestination remote set-url --push bundle-local DISABLED
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0) { throw 'Neutralisation du push vers le bundle echouee.' }

# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
& git -C $absoluteDestination switch -c "reparation-$Binome"
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0) { throw 'Creation de la branche de reparation echouee.' }

# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
& git -C $absoluteDestination rev-parse --verify 'v1.0-sain^{commit}'
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if ($LASTEXITCODE -ne 0) { throw 'Tag sain absent du clone.' }

# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
Write-Host "Game Day pret : $absoluteDestination"
# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
Write-Host "Branche de travail : reparation-$Binome"
# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
Write-Host 'Remote local : bundle-local (lecture seule pedagogique ; ne pas pousser)'
