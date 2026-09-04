# SKULL-08.4 — importer la configuration legacy

- Date : 4 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : conversion locale en lecture seule d’une copie de l’archive de
  configuration legacy ; aucun accès au Raspberry, service, DNS, Bluetooth,
  ESP32, sonnette ou réseau n’a été exécuté.

## Résultat

Le convertisseur séparé `config/migrate_legacy.py` lit les anciens JSON et
fichiers dotenv, produit un TOML candidat déterministe et un rapport JSON. Il
refuse toute cible déjà présente et ne modifie ni ne supprime les sources.

Sur la copie extraite de l’archive locale `backups/SKULL-01.3/skull-runtime.tar.gz` :

- 13 entrées converties ;
- 0 valeur redigée ;
- 0 clé inconnue ;
- 3 blocages explicitement rapportés ;
- 0 erreur de lecture ou de validation.

La compatibilité legacy `neck` est convertie vers la clé cible `neck_pan`.
Les deux fichiers de catégories sont conservés comme blocages explicites car le
schéma phase 8 ne définit pas encore leur destination :

- `button_categories: destination absente du schéma phase 8` ;
- `session_categories: destination absente du schéma phase 8`.

L’adresse historique de l’ESP32 est conservée uniquement comme fallback
désactivé ; son activation reste bloquée tant qu’un nom DNS n’est pas défini :

- `esp32.host: nom DNS requis avant activation`.

Aucune valeur secrète n’a été copiée dans le TOML, le rapport, les tests ou la
preuve. Le webhook n’a pas été rotaté : `SKULL-08.5` est annulée et son modèle
événement → action est reporté à la phase 13.

## Vérifications d’acceptation

- Conversion effectuée sur une copie extraite ; l’archive et les sources
  legacy originales sont restées intactes.
- Idempotence vérifiée : les deux TOML candidats sont identiques et les deux
  rapports sont identiques.
- Non-écrasement vérifié : une cible préexistante provoque une sortie 1 et son
  contenu `KEEP` est conservé.
- `python -m pytest -q tests/config` : `33 passed` ; avec
  `tests/test_configuration_examples.py`, `36 passed`.
- `python -m pytest -q` : `271 passed`, 1 avertissement externe connu lié à
  `pydub/audioop`.
- `python -m compileall -q config tests/config` : OK.
- `python -m config.validate config/skull.example.toml` : OK, sortie redigée.
- `git diff --check` : OK, avec seulement les avertissements Git de conversion
  de fins de ligne Windows.
- Contrôle du diff : 0 URL HTTP complète, 0 ligne d’affectation de secret et
  aucune valeur secrète affichée.

## Limites et rollback

La tâche ne peut pas être déclarée complète tant que les deux destinations de
catégories ne sont pas décidées et que le nom DNS de l’ESP32 n’est pas défini.
Cette preuve ne valide donc ni l’activation runtime de l’ESP32 ni une migration
de production.

Le rollback est assuré localement par la sélection de l’ancien chargeur et par
la conservation des sources legacy. Aucun état distant n’a changé. Les
modifications locales sont limitées au convertisseur, à son test et aux fichiers
de pilotage de cette tâche.
