# TP — Data drift & métriques sur InduSense (module 31, intégré au repo)

> PSI + KS sur les capteurs réels, modèle « en production » au seuil gelé, 4 fenêtres de
> surveillance, et le tableau de bord Grafana du repo. Prérequis : `uv sync --frozen --extra dev` OK.
> Le module de calcul vit dans **`src/indusense/monitoring/drift.py`** (c'est lui que le
> module 32 branchera dans le flow) ; ses tests : `tests/test_drift_monitoring.py`.

## 1. Construire les fenêtres (source : flux capteurs complet, `data/drift_source/`)

```bash
uv run python scripts/drift_windows.py
uv run python scripts/train_drift_model.py
```

Attendu (chiffres de référence) : jointure+features **64 535 lignes** · panne_v1 ≈ 5,2 % (la
colonne `panne` = incidents réels ≈ 4,8 % est conservée pour comparaison) · validation
TEMPORELLE de décembre : PR-AUC **0,258** (prévalence 0,052), ROC **0,817** · seuil gelé
**0,03** (théorique 200/5200 ≈ 0,038) · rappel 0,867 · taux d'alerte 42,8 %.
Pourquoi un split temporel et pas aléatoire ? Mesuré sur ce repo : ROC 0,93 en aléatoire
(fuite des rolling features, m8) contre 0,82 en temporel. Pourquoi une cible contrôlée
(`panne_v1`) et pas les incidents réels ? Mesuré aussi : ROC ≈ 0,56 — les incidents du CSV ne
sont pas corrélés aux capteurs (la modélisation sérieuse du parcours se fait sur le Gold).

## 2. La ronde de surveillance — 4 fenêtres

```bash
uv run python scripts/evaluate_drift.py --fenetre 1                      # témoin (fév 2026)
uv run python scripts/evaluate_drift.py --fenetre 2                      # capteur +8 °C
uv run python scripts/evaluate_drift.py --fenetre 3                      # concept drift
uv run python scripts/evaluate_drift.py --fenetre janvier                # campagne haute charge
uv run python scripts/evaluate_drift.py --fenetre janvier --reference haute   # la contre-épreuve
```

| Fenêtre | PSI temp | Rappel | ROC | La leçon |
|---|---|---|---|---|
| 1 témoin | 0,002 | 0,822 | 0,796 | bruit de fond étalonné, tout va bien |
| 2 capteur +8 °C | **6,834** | 0,811 | 0,793 | le PSI hurle, le modèle (assis sur les deltas) tient — mais capteur menteur = données corrompues pour tout le reste : contrôle physique d'abord |
| 3 concept | 0,002 | **0,092** | **0,208** | PSI structurellement muet (X identiques), 394 pannes ratées — seul un KPI avec labels le voit |
| janvier campagne | 6,203 vs réf normale · **0,001 vs réf haute** | 0,868 | 0,812 | fausse alerte de régime → la drift spec fige des **références par régime** |

Segmentation (m31 §2.5) : ajoutez `--machine MACH-03`. Tests : `uv run pytest tests/test_drift_monitoring.py -q` → **8 passed**.

## 3. Le tableau de bord (stack compose du repo)

```bash
uv run python scripts/export_drift_metrics.py        # terminal 1 (port 9109)
docker compose up -d                                 # terminal 2 (api + db + prometheus + grafana)
```

Prometheus (`localhost:9090`, Status→Targets) doit voir DEUX cibles UP : `indusense-api`
(les métriques HTTP du m33) et `indusense-drift` (ce TP). Grafana (`localhost:3000`,
admin/admin) charge automatiquement le dashboard **« InduSense — dérive & métriques »**.
Relancez `evaluate_drift --fenetre 2` puis `3` et regardez les jauges basculer.
Sous Linux : ajouter `extra_hosts: ["host.docker.internal:host-gateway"]` au service
prometheus du compose (Docker Desktop Windows/macOS : rien à faire).

## 4. Livrable : la drift spec

Rédigez `reports/drift/drift_spec.md` : références PAR RÉGIME figées (normale = sept+nov+déc,
haute charge = octobre), fenêtre 7 j glissants par machine, PSI 10 bins figés sur la référence
(bords ±inf, NaN écartés) + KS en confirmation, alerte si PSI > 0,25 persistant 2 fenêtres,
segmentation par machine (priorité `criticality = HIGH` de machine.sql — jamais réinjectée
comme feature), KPI de second rideau : taux de confirmation des inspections (~3 j) plancher
0,05 · rappel (~15 j) plancher 0,60 · bande d'alerte 35-50 %. Réactions : PSI capteur franchi
→ étalonnage physique AVANT toute action modèle ; campagne planifiée → basculer de référence,
ne pas alerter ; rappel sous plancher → réentraînement (protocole m21 complet, puis nouvelle
référence + spec mise à jour).
