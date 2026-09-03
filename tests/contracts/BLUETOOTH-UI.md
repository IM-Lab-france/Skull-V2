# Contrat IHM Bluetooth

L’IHM utilise les opérations explicites suivantes. Chaque opération reçoit une
adresse Bluetooth validée et renvoie `ok`, `operation`, `state` et, en cas de
succès, son résultat. `state` est rafraîchi après l’appel, y compris lorsqu’il
échoue ; les sorties brutes de `bluetoothctl` ne sont jamais renvoyées.

| Route | Effet unique | Précondition IHM |
|---|---|---|
| `POST /bluetooth/scan` | Découvrir | aucune |
| `POST /bluetooth/pair` | Appairer | périphérique découvert |
| `POST /bluetooth/trust` | Autoriser les reconnexions | appairé |
| `POST /bluetooth/connect` | Établir la liaison | appairé et de confiance |
| `POST /bluetooth/select-output` | Sélectionner le sink | connecté et profil Audio Sink prouvé |
| `POST /bluetooth/test-audio` | Lecture bornée confirmée | connecté, profil et sink prouvés |

La route legacy `POST /pair` conserve son comportement historique combiné pour
les anciens clients. Elle n’est plus appelée par l’IHM.

Le test audio exige `confirm: true`, une durée de 100 à 3000 ms et un volume de
0 à 20. La sélection PulseAudio et la lecture physique restent explicitement
retenues par leurs tâches dédiées tant que leurs adaptateurs ne sont pas
validés.
