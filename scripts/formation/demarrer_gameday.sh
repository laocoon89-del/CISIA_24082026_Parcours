#!/usr/bin/env bash
# [PÉDAGOGIE] ============================================================================
# [PÉDAGOGIE] FICHIER — scripts/formation/demarrer_gameday.sh
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

# [PÉDAGOGIE] FAIL FAST — arrêter sur la première erreur évite de produire une fausse réussite.
set -euo pipefail

# [PÉDAGOGIE] FONCTION — encapsule une étape nommée afin de pouvoir la lire, la tester et la
# [PÉDAGOGIE] réutiliser.
usage() {
  # [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
  echo "Usage: bash scripts/formation/demarrer_gameday.sh IDENTIFIANT [DESTINATION]" >&2
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
}

# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if [[ $# -lt 1 || $# -gt 2 ]]; then
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  usage
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  exit 2
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
fi

# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
binome="$1"
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if [[ ! "$binome" =~ ^[A-Za-z0-9._-]+$ ]]; then
  # [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
  echo "Identifiant invalide : lettres, chiffres, point, tiret ou underscore uniquement." >&2
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  exit 2
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
fi

# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  # [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
  echo "Lancez ce script depuis le depot du parcours." >&2
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  exit 1
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
}
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
bundle="$root/FORMATION/EXERCICES/J6/J6-gameday.bundle"
# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if [[ ! -f "$bundle" ]]; then
  # [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
  echo "Bundle absent : $bundle" >&2
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  exit 1
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
fi

# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if [[ $# -eq 2 ]]; then
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  destination="$2"
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
else
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  destination="$(dirname "$root")/CISIA_J6_GAMEDAY_$binome"
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
fi

# [PÉDAGOGIE] DÉCISION — tester le prérequis avant l'action rend le chemin d'échec compréhensible.
if [[ -e "$destination" ]]; then
  # [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
  echo "Destination deja presente, aucune ecriture : $destination" >&2
  # [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
  # [PÉDAGOGIE] autorise la suite.
  exit 1
# [PÉDAGOGIE] ÉTAPE — lire cette commande comme une intention, puis identifier la preuve qui
# [PÉDAGOGIE] autorise la suite.
fi

# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
git clone -b J6-gameday "$bundle" "$destination"
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
git -C "$destination" remote rename origin bundle-local
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
git -C "$destination" remote set-url --push bundle-local DISABLED
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
git -C "$destination" switch -c "reparation-$binome"
# [PÉDAGOGIE] GIT — rendre branche, commit et état local vérifiables avant toute intégration.
git -C "$destination" rev-parse --verify 'v1.0-sain^{commit}' >/dev/null

# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
echo "Game Day pret : $destination"
# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
echo "Branche de travail : reparation-$binome"
# [PÉDAGOGIE] OBSERVABILITÉ — ce message annonce l'étape ou sa preuve sans afficher de secret.
echo "Remote local : bundle-local (lecture seule pedagogique ; ne pas pousser)"
