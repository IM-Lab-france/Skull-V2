# SKULL-04.4 — résultat

## Statut

**VALIDÉ — modifications et validations locales uniquement.**

Date de validation : 2026-09-03.

## Périmètre exécuté

La tâche exécutée est exclusivement `SKULL-04.4` de
`tasks/04-SIMULATION.md`, dans le worktree isolé :

`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026`

Fichiers ajoutés :

- `simulated_external.py` : adaptateurs Bluetooth, ESP32 et fumée simulés ;
- `tests/unit/test_simulated_external.py` : scénarios d’état, d’appel, de
  payload, de délai logique et d’erreur.

## Bluetooth simulé

`SimulatedBluetoothAdapter` conserve séparément :

- `discovered` ;
- `paired` ;
- `trusted` ;
- `connected` ;
- `a2dp_profile` ;
- `sink_available`.

`scan()` découvre uniquement les périphériques synthétiques visibles.
`pair()` journalise et exécute les étapes `pair → trust → connect`, ce qui
laisse les états intermédiaires inspectables lorsqu’une étape échoue.
L’absence de profil A2DP ou de sink n’est pas confondue avec l’état de
connexion. Les délais sont appliqués à l’horloge injectée et non à l’horloge
murale.

## ESP32 simulé

`SimulatedESP32Adapter` traite les contrats utilisés par le code actuel :

- `GET /api/status` ;
- `POST /api/relay` ;
- `POST /api/auto-relay` ;
- `GET` et `POST /api/button-config` ;
- `POST /api/restart`.

Chaque appel conserve le chemin, la méthode et une copie du payload JSON. Le
relais, l’auto-relay, les affectations de boutons et le compteur de restart
sont mémorisés en mémoire. Les réponses et validations de payload sont
déterministes.

## Fumée simulée

`SimulatedSmokeAdapter` mémorise chaque session déclenchée et permet de
séquencer les issues `success`, `timeout` et `http_error`. Le succès est
représenté par un retour normal et un résultat `triggered`; les deux échecs
lèvent respectivement `TimeoutError` ou `SimulatedSmokeHTTPError` avec un
statut HTTP synthétique.

## Vérifications

Depuis le worktree isolé :

```text
python -m pytest tests/unit/test_simulated_external.py --collect-only -q
7 tests collected

python -m pytest tests/unit/test_simulated_external.py -q
7 passed in 0.05s

python -m pytest -q
59 passed, 1 warning in 3.01s
```

Les tests vérifient notamment :

- les six états Bluetooth distincts et l’ordre des transitions ;
- l’état partiellement appairé après un timeout de confiance ;
- une connexion sans profil A2DP ni sink disponible ;
- les cinq familles de requêtes ESP32, leurs réponses et leurs payloads ;
- l’injection d’une erreur HTTP ESP32 et d’un délai logique ;
- les trois issues fumée et la mémorisation des déclenchements ;
- la conformité runtime à `BluetoothAdapter`, `ESP32Adapter` et
  `SmokeAdapter` ;
- l’absence de clients plateforme dans le namespace du module simulé.

Contrôles complémentaires exécutés avec succès :

```text
python -m compileall -q simulated_external.py tests
git diff --check
```

L’avertissement est celui, déjà connu, de `pydub` concernant `audioop`; il ne
provient pas des simulateurs externes.

## Contrôles de non-régression et limites

- aucun import ou accès Bluetooth réel, socket, subprocess, HTTP ou réseau
  réel ;
- aucune adresse de production, aucun secret et aucun webhook n’ont été
  ajoutés ;
- aucune route HTTP, aucun pilote réel et aucune configuration de production
  n’ont été modifiés par cette tâche ;
- aucune écriture sur le Raspberry et aucun test matériel n’ont été exécutés ;
- les simulateurs ne sont pas encore sélectionnés par une factory au démarrage
  et ne remplacent jamais automatiquement les adaptateurs réels ; cette
  sélection explicite appartient à `SKULL-04.5` ;
- le fake Bluetooth modélise le sink A2DP comme un état observé, sans ouvrir
  PulseAudio ni créer de périphérique audio.

## Prochaine tâche autorisée

`SKULL-04.5` — sélectionner les adaptateurs au démarrage selon une
configuration validée, avec production réelle obligatoire et simulation
explicitement demandée pour les tests.
