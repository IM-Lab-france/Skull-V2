# SKULL-05.4 — résultat

## Statut

**VALIDÉ — healthchecks sans effet de bord validés localement.**

Date : 2026-09-03.

La tâche a été exécutée dans le worktree isolé de production. Aucun service,
matériel ou fichier du Raspberry n’a été modifié.

## Contrats réalisés

- `GET /health/live` retourne 200 dès que le processus HTTP répond ;
- `GET /health/ready` retourne 503 tant que la configuration ou les composants
  runtime obligatoires ne sont pas prêts ;
- `GET /health/ready` retourne 200 uniquement lorsque le mode est valide et
  que le lecteur principal et la boucle audio sont initialisés ;
- le mode public vaut `real` ou `simulated` ;
- la réponse contient uniquement `status`, `version`, `mode` et `checks` ;
- aucun endpoint de santé n’invoque la lazy initialization, une session, un
  servo, l’audio, Bluetooth, un socket externe ou le webhook.

## Réponses vérifiées

À froid en mode simulé :

```text
GET /health/live  → 200, status=ok
GET /health/ready → 503, status=not_ready
```

Après initialisation des deux composants simulés :

```text
GET /health/ready → 200, status=ready, mode=simulated
```

Configuration invalide ou composant manquant :

```text
GET /health/ready → 503
```

Les réponses ne contiennent ni secret, ni chemin privé, ni sortie brute de
commande.

## Fichiers modifiés dans cette tâche

- `web_app.py` : fonctions de snapshot santé et routes `/health/live` et
  `/health/ready` ;
- `tests/unit/test_healthchecks.py` : tests 200/503, rapidité et absence
  d’initialisation ;
- `tests/unit/test_runtime_factory.py` et `tests/unit/test_wsgi_runtime.py` :
  adaptation aux contrats readiness corrigés.

Les modifications antérieures ont été conservées. La preuve `SKULL-05.3` a
été ajustée pour indiquer que le smoke test simulé utilise live à 200 et ready
à 503 sans runtime matériel initialisé.

## Tests et validations

Commandes exécutées dans
`C:\Users\cedri\Documents\Codex\Skull-V2-production-2026` :

```text
python -m pytest tests/unit/test_healthchecks.py tests/unit/test_startup_determinism.py tests/unit/test_wsgi_runtime.py tests/unit/test_runtime_factory.py -q
19 passed, 1 warning

python -m pytest -q
78 passed, 1 warning

python -m compileall -q web_app.py playlist_web.py runtime_factory.py runtime_lock.py wsgi_entry.py tests
git diff --check
```

Le warning restant est celui, déjà connu, de `pydub` concernant le module
Python déprécié `audioop`.

Les tests health vérifient aussi que la réponse readiness reste rapide
(moins d’une seconde) et ne déclenche aucune dépendance externe indisponible.

## Critères d’acceptation

- tests 200/503 couvrant configuration, runtime prêt et composant manquant :
  **validé** ;
- réponse sous une seconde avec dépendances externes indisponibles :
  **validé** ;
- mode `real`/`simulated` visible sans ambiguïté : **validé** ;
- absence d’effets de bord : **validé par tests d’import et de healthcheck** ;
- compatibilité des routes legacy : **suite complète verte**.

## Risques et limites

- le runtime distant n’a pas été redémarré et conserve encore les anciens
  healthchecks jusqu’au déploiement futur ;
- la readiness réelle sur le Raspberry devra être vérifiée après installation
  de la candidate, sans lancer de session ni mouvement ;
- l’authentification des routes reste traitée dans la phase sécurité.

## Rollback

Aucun déploiement n’ayant été effectué, aucun rollback distant n’est requis.
La candidate locale peut être restaurée après revue du diff en conservant les
modifications précédentes ; ne pas utiliser de reset ou de nettoyage Git
destructif.

## Prochaine tâche autorisée

`SKULL-05.5` : borner les appels réseau, rendre Bluetooth non bloquant et
ajouter la rotation/rétention des logs.
