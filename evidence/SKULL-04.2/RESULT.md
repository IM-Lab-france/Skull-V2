# SKULL-04.2 — résultat

## Statut

**VALIDÉ — modifications et validations locales uniquement.**

Date de validation : 2026-09-03.

## Périmètre exécuté

La tâche exécutée est exclusivement `SKULL-04.2` de
`tasks/04-SIMULATION.md`, dans le worktree isolé :

`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`

Fichiers ajoutés :

- `simulated_hardware.py` : façade servo simulée et contrôleur PCA9685 en
  mémoire ;
- `tests/unit/test_simulated_hardware.py` : tests du mode explicite, des
  traces et de l’absence de matériel réel.

## Comportement implémenté

- `SimulatedHardware` expose la même façade publique que `Hardware` :
  `set_named_angle`, `neutral`, `cleanup`, `set_pitch_offset`, `SPECS` et
  `ctrl` ;
- le constructeur refuse toute valeur autre que
  `SKULL_HARDWARE_MODE=simulated` ; il n’existe aucun fallback automatique ;
- les quatre références mécaniques sont conservées : `jaw` CH0,
  `eye_left` CH1, `eye_right` CH2 et `neck_pan` CH3 ;
- chaque commande capture le canal, le nom, l’angle demandé, l’angle clampé,
  l’impulsion calculée et un timestamp logique déterministe ;
- `neutral()` conserve la séquence réelle : mâchoire, œil gauche, œil droit,
  cou ;
- `cleanup()` exécute uniquement `off()`/`deinit()` en mémoire ;
- les offsets sont isolés par instance et n’écrivent aucun fichier ni bus.

Les valeurs des `SPECS` et la conversion angle→microsecondes reproduisent
`rpi_hardware.py`, sans importer ce module (qui charge les bibliothèques
Raspberry dès son import). Le simulateur n’importe que la bibliothèque
standard Python.

## Vérifications

Depuis le worktree isolé :

```text
python -m pytest tests/unit/test_simulated_hardware.py --collect-only -q
4 tests collected

python -m pytest -q
47 passed, 1 warning in 3.00s
```

Les tests vérifient notamment :

- refus sans mode explicite et refus avec `SKULL_HARDWARE_MODE=production` ;
- absence de `board`, `busio` et `adafruit_pca9685` ;
- clamps et impulsions des quatre canaux, dont l’offset `eye_left=-14` ;
- timestamps logiques reproductibles ;
- ordre de `neutral()` ;
- extinction et libération simulées par `cleanup()`.

Contrôles complémentaires exécutés avec succès :

```text
python -m compileall -q simulated_hardware.py tests
git diff --check
PROTOCOL_IMPORT_OK
FINAL_CHECK_OK
```

L’avertissement est celui, déjà connu, de `pydub` concernant `audioop`; il ne
provient pas du simulateur servo.

## Contrôles de non-régression et limites

- aucun import ou accès I²C, GPIO, audio réel, Bluetooth réel ou réseau réel ;
- aucune route HTTP et aucun pilote réel n’ont été modifiés par cette tâche ;
- aucun secret, aucune adresse de production et aucun webhook n’ont été
  ajoutés ;
- aucune écriture sur le Raspberry et aucun mouvement réel n’ont été
  exécutés ;
- le timestamp logique est volontairement local et déterministe ; l’horloge
  injectable et l’audio simulé relèvent de `SKULL-04.3` ;
- les constantes mécaniques sont recopiées du pilote réel : une évolution
  future de `rpi_hardware.py` devra mettre à jour le simulateur et ses tests
  dans la même tâche de référence.

## Prochaine tâche autorisée

`SKULL-04.3` — introduire une horloge injectable et un lecteur audio simulé,
sans ouvrir de device audio et sans attente réelle.
