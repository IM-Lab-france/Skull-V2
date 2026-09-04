# SKULL-04.1 — résultat

## Statut

**VALIDÉ — modifications et validations locales uniquement.**

Date de validation : 2026-09-03.

## Périmètre exécuté

La tâche exécutée est exclusivement `SKULL-04.1` de
`tasks/04-SIMULATION.md`. Le code a été ajouté dans le worktree isolé :

`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`

Fichiers ajoutés :

- `adapters.py` : six `Protocol` Python basés uniquement sur la bibliothèque
  standard ;
- `tests/fixtures/fake_adapters.py` : faux adaptateurs déterministes ;
- `tests/fixtures/__init__.py` : package de fixtures ;
- `tests/unit/test_adapter_protocols.py` : tests d’import et de conformité.

## Contrats définis

| Protocole | Surface minimale | Erreurs documentées |
| --- | --- | --- |
| `ServoAdapter` | angle nommé, neutre, nettoyage, offset | `ValueError`, `KeyError`, `OSError`, `RuntimeError` |
| `AudioAdapter` | load, play, pause, resume, stop, status, fin de piste | `FileNotFoundError`, `ValueError`, `OSError`, `RuntimeError` |
| `BluetoothAdapter` | scan, pair, connect, info | `TimeoutError`, `ConnectionError`, `OSError` |
| `ESP32Adapter` | requête relative avec méthode et JSON facultatif | `TimeoutError`, `ConnectionError`, `OSError`, erreur de communication |
| `SmokeAdapter` | déclenchement nommé | erreur laissée à l’adaptateur et au cœur appelant |
| `GazeAdapter` | lecture de commande fraîche, arrêt | erreur laissée à l’adaptateur et au cœur appelant |

Les protocoles ne contiennent ni politique de retry, ni clamp, ni routage, ni
fallback simulé. La logique métier reste hors des adaptateurs. Le faux PCA9685
complet et l’enregistrement des canaux/angles sont explicitement reportés à
`SKULL-04.2`.

## Vérifications

Depuis le worktree de production isolé :

```text
python -m pytest -q
43 passed, 1 warning in 3.13s

python -m compileall -q adapters.py tests
git diff --check
VALIDATION_OK
```

Le test `test_protocols_import_without_raspberry_modules` confirme que les
protocoles sont importables sans `board`, `busio` ou `adafruit_pca9685`. Les
six faux adaptateurs passent `isinstance(..., Protocol)` et un test vérifie
leurs appels et valeurs de retour sans ouvrir de périphérique.

L’avertissement concerne `pydub` qui importe le module Python déprécié
`audioop`; il est antérieur à cette tâche et ne concerne pas `adapters.py`.

## Contrôles de non-régression et limites

- aucune route HTTP n’a été modifiée pour `SKULL-04.1` ;
- aucun import ou accès I²C, GPIO, audio réel, Bluetooth réel ou réseau réel ;
- aucun secret, adresse de production ou webhook n’a été ajouté ;
- aucune écriture sur le Raspberry et aucun test matériel n’a été exécuté ;
- le cœur existant n’est pas encore injecté avec ces protocoles ; cette
  intégration appartient aux tâches ultérieures ;
- la suite complète reste dépendante des faux modules déjà prévus par la
  caractérisation de phase 03.

## Prochaine tâche autorisée

`SKULL-04.2` — créer `SimulatedHardware` et comparer ses traces servo aux
valeurs de référence, avec le mode simulé explicite et sans mouvement réel.
