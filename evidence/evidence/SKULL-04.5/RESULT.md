# SKULL-04.5 — résultat

## Statut

**VALIDÉ — modifications et validations locales uniquement.**

Date de validation : 2026-09-03.

## Périmètre exécuté

La tâche exécutée est exclusivement `SKULL-04.5` de
`tasks/04-SIMULATION.md`, dans le worktree isolé :

`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`

Fichiers ajoutés ou modifiés pour cette tâche :

- `runtime_factory.py` : résolution du mode, validation et bundle commun ;
- `simulated_gaze.py` : adaptateur gaze sans UDP pour le bundle simulé ;
- `web_app.py` : route `GET /health/ready` qui expose le mode sans secret ;
- `install_skull.sh` : service généré épinglé en production et garde-fou ;
- `launch_servo_sync.sh` : refus du mode simulé par le lanceur production ;
- `tests/unit/test_runtime_factory.py` : tests de sélection, démarrage,
  readiness et garde-fous systemd.

Les modifications préexistantes du worktree, notamment `web_app.py`, ont été
préservées. La route ajoutée est limitée à la readiness de configuration ; elle
ne remplace pas encore les healthchecks matériels du runtime de la phase 05.

## Factory et modes

`RuntimeAdapters` est le bundle commun retourné par les deux modes. Il expose
les mêmes six ports : servo, audio, Bluetooth, ESP32, fumée et gaze.

### Simulation

Avec `SKULL_HARDWARE_MODE=simulated`, `build_adapters()` construit :

- `SimulatedHardware` ;
- `SimulatedAudioPlayer` ;
- `SimulatedBluetoothAdapter` ;
- `SimulatedESP32Adapter` ;
- `SimulatedSmokeAdapter` ;
- `SimulatedGazeAdapter`.

La construction est validée contre les six protocoles. Aucun fallback ni
import de matériel réel n’est exécuté.

### Production

Sans variable, le mode legacy reste `production`. Ce chemin exige un
`ProductionAdapterProvider` explicite qui construit les adaptateurs réels.
L’absence de fournisseur échoue clairement ; un objet dont le module commence
par `simulated_` est également refusé. La factory ne remplace jamais une
défaillance réelle par un simulateur.

Les tests utilisent uniquement des sentinelles non matérielles pour vérifier la
sélection du chemin production sur Windows. Aucun constructeur réel n’est
appelé dans cette validation.

## Readiness et production

`GET /health/ready` renvoie un JSON secret-free avec :

- `ready` ;
- `mode` ;
- `simulation` ;
- `selection`.

Un mode inconnu renvoie `ready=false` et le statut HTTP `503`. Les modes
valides renvoient `200` et le mode correspondant.

Le service systemd produit par `install_skull.sh` contient
`Environment=SKULL_HARDWARE_MODE=production` et un `ExecStartPre` qui refuse
explicitement `simulated`. Le lanceur autonome applique le même refus avec le
code de sortie `78`. Les fichiers ne sont pas exécutés sur Windows ; leur
contenu est contrôlé statiquement.

## Vérifications

Depuis le worktree isolé :

```text
python -m pytest tests/unit/test_runtime_factory.py -q
7 passed in 0.25s

python -m pytest -q
66 passed, 1 warning in 3.10s
```

Les tests vérifient notamment :

- construction du bundle simulé avec les six protocoles ;
- refus de la simulation sans variable explicite ;
- refus de la production sans fournisseur explicite ;
- rejet d’un adaptateur simulé dans un fournisseur production ;
- réponses readiness production/simulation et route `/health/ready` ;
- présence des garde-fous dans le service et le lanceur production.

Contrôles complémentaires exécutés avec succès :

```text
python -m compileall -q runtime_factory.py simulated_gaze.py tests
git diff --check
```

L’avertissement est celui, déjà connu, de `pydub` concernant `audioop`; il ne
provient pas de la factory.

## Contrôles de non-régression et limites

- aucun accès I²C, GPIO, audio réel, Bluetooth réel ou réseau réel ;
- aucun secret, aucune adresse de production et aucun webhook ajoutés ;
- aucune écriture sur le Raspberry, aucun redémarrage et aucun déploiement ;
- aucun fallback silencieux ;
- les routes legacy existantes restent inchangées par cette tâche ;
- le bundle n’est pas encore injecté dans `SyncPlayer`/`web_app` pour remplacer
  le démarrage legacy : cette intégration contrôlée et les healthchecks réels
  appartiennent à la phase 05 ;
- `/health/ready` valide la configuration du mode, pas la santé physique du
  PCA9685, du sink audio ou des services externes.

## Prochaine tâche autorisée

`SKULL-05.1` — stabiliser le runtime sans changement fonctionnel, en gardant
un seul processus propriétaire du matériel et des healthchecks séparés.
