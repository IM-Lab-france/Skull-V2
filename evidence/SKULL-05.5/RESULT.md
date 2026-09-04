# SKULL-05.5 — résultat

## Statut

**VALIDÉ — bornes réseau, Bluetooth et logs vérifiées localement.**

Date : 2026-09-03.

La tâche a été exécutée dans le worktree isolé de production. Aucun service,
matériel, secret ou fichier du Raspberry n’a été modifié.

## Résultats

- Les appels HTTP `requests`/`urlopen` et les commandes applicatives
  `subprocess.run` possèdent une borne explicite vérifiée par AST.
- Le webhook fumée conserve son timeout et ne révèle plus son URL dans les
  diagnostics ; les erreurs ESP32 et playlist sont contrôlées.
- La connexion Bluetooth n’est plus exécutée dans `ExecStartPre`. Elle reste
  déclenchée uniquement par les opérations qui en ont besoin, donc une
  enceinte éteinte ne bloque pas le démarrage du service.
- Les logs servo utilisent une rotation de 10 MiB avec 5 sauvegardes par
  défaut ; les stats JSON sont limitées aux 100 dernières sessions.
- Le répertoire vise `0750`, les fichiers `0640`, avec le compte `skull` via
  l’installateur. Une indisponibilité du stockage bascule vers stderr sans
  interrompre le runtime.

## Tests exécutés

Dans `C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` :

```text
python -m pytest tests/unit/test_runtime_safety.py -q
6 passed

python -m pytest tests/unit/test_external_dependencies_characterization.py tests/unit/test_runtime_safety.py -q
14 passed, 1 warning

python -m pytest -q
86 passed, 1 warning
```

Les scénarios couvrent : serveur muet et DNS indisponible via adaptateur local,
commande Bluetooth suspendue via `TimeoutExpired`, URL webhook secrète,
rotation, rétention et répertoire de logs indisponible.

## Limites

- La candidate n’est pas déployée sur le Raspberry ; la nouvelle unité
  systemd et les permissions devront être vérifiées pendant `SKULL-05.6`.
- `urllib.request` ne sépare pas nativement le timeout de connexion et le
  timeout total : `ESP32_HTTP_TIMEOUT` applique la borne la plus stricte des
  deux valeurs configurées (`PLAYLIST_ESP32_CONNECT_TIMEOUT` et
  `PLAYLIST_ESP32_TIMEOUT`). Une future extraction d’adaptateur pourra affiner
  la distinction connexion/lecture.
- Le warning `pydub/audioop` reste connu et sans rapport avec cette tâche.

## Prochaine tâche autorisée

`SKULL-05.6` : préparer l’instance candidate parallèle, uniquement après
confirmation explicite pour toute création de venv, unité systemd ou ouverture
de port sur le Raspberry.
