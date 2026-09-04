# SKULL-04.3 — résultat

## Statut

**VALIDÉ — modifications et validations locales uniquement.**

Date de validation : 2026-09-03.

## Périmètre exécuté

La tâche exécutée est exclusivement `SKULL-04.3` de
`tasks/04-SIMULATION.md`, dans le worktree isolé :

`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`

Fichiers ajoutés :

- `simulation_clock.py` : protocole d’horloge et `SimulatedClock` ;
- `simulated_audio.py` : `SimulatedAudioPlayer` et alias `SimulatedAudio` ;
- `tests/unit/test_simulated_audio.py` : tests de l’horloge, des transitions,
  de la fin de piste et de la dérive.

## Comportement implémenté

- `Clock` limite la dépendance à `monotonic()` et `sleep(seconds)` ;
- `SimulatedClock.sleep()` avance le temps logique sans bloquer et
  `advance()` permet au test de piloter le temps explicitement ;
- `SimulatedAudioPlayer` reçoit une durée configurable et une horloge
  injectable ;
- `load`, `play`, `pause`, `resume`, `stop` et `status` sont disponibles et
  conformes à `AudioAdapter` ;
- `tick()` observe l’horloge et `advance()` avance une horloge simulée puis
  applique l’évolution ;
- les états `stopped`, `playing`, `paused` et `completed` sont distincts ;
- la callback de fin reçoit `completed` une seule fois par lecture ;
- l’arrêt conserve la position pour le diagnostic et empêche tout avancement
  ultérieur tant qu’une nouvelle lecture n’est pas lancée.

La simulation ne lit pas de fichier, ne démarre pas de thread, n’ouvre pas de
device audio et n’appelle ni `time.sleep`, ni `sounddevice`, ni `soundfile`, ni
`pydub`, ni `simpleaudio`.

## Vérifications

Depuis le worktree isolé :

```text
python -m pytest tests/unit/test_simulated_audio.py --collect-only -q
5 tests collected

python -m pytest tests/unit/test_simulated_audio.py -q
5 passed in 0.03s

python -m pytest -q
52 passed, 1 warning in 3.07s

python -m compileall -q simulation_clock.py simulated_audio.py tests
git diff --check
SIM_AUDIO_IMPORT_OK
VALIDATION_OK
```

Les tests vérifient notamment :

- l’avance logique de 300 secondes en moins d’une seconde ;
- play → pause → resume avec position gelée pendant la pause ;
- stop avec raison et position conservée ;
- fin de piste à la durée exacte, sans callback dupliquée ;
- calcul reproductible de la dérive : position audio moins position timeline ;
- refus des durées négatives et des durées de sommeil négatives ;
- conformité runtime à `AudioAdapter` et `Clock`.

L’avertissement est celui, déjà connu, de `pydub` concernant `audioop`; il ne
provient pas des nouveaux modules simulés.

## Contrôles de non-régression et limites

- aucun import ou accès I²C, GPIO, audio réel, Bluetooth réel ou réseau réel ;
- aucune route HTTP, aucun pilote réel et aucune logique de production n’ont
  été modifiés par cette tâche ;
- aucun secret, aucune adresse de production et aucun webhook n’ont été
  ajoutés ;
- aucune écriture sur le Raspberry et aucun test matériel n’ont été exécutés ;
- `SyncPlayer` n’utilise pas encore cette horloge : son injection dans le cœur
  et la sélection centralisée des adaptateurs relèvent des tâches ultérieures ;
- l’horloge simulée est volontairement pilotée par le test et ne modélise pas
  encore les délais Bluetooth/ESP32/fumée de `SKULL-04.4`.

## Prochaine tâche autorisée

`SKULL-04.4` — simuler Bluetooth, ESP32 et fumée avec états, appels et erreurs
inspectables sans réseau réel.
