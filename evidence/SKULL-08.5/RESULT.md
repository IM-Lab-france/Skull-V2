# SKULL-08.5 — rotation du secret fumée

- Date : 3 septembre 2026, Europe/Paris
- Statut : `PARTIEL`
- Portée : inventaire des producteurs/consommateurs et préparation locale
  d’une rotation sans valeur sensible.

## Inventaire

- Producteur legacy observé : `web_app.py`, déclenchement nommé `Accueil`,
  appel sortant borné par `curl`.
- Frontière cible locale : `SmokeAdapter` dans `adapters.py` et
  `services/playback.py`.
- Fournisseur de secret cible : référence `env:` ou `file:` résolue par
  `config.secrets`, sans affichage ni journalisation de la valeur.
- Tests externes : scénarios simulés uniquement ; aucun consommateur domotique
  réel n’a été contacté.

## Préparation validée

- `SmokeRotationPlan` impose deux références distinctes, masque les références
  dans son diagnostic et fixe l’ordre consommateur → producteur → vérification
  → retrait de l’ancien secret.
- Le plan reste bloqué tant que la double acceptation n’est pas confirmée par
  le système distant.
- Les anciens JSON et `.env` sont lus en copie locale ; une valeur webhook est
  seulement convertie en référence et signalée `redacted`.

## Blocage volontaire

La génération, la rotation, le test ancien/nouveau, le basculement du
producteur et le retrait de l’ancien secret nécessitent une confirmation
explicite, un mécanisme approuvé de gestion des secrets et l’accès au
consommateur domotique. Aucun de ces changements réels n’a été effectué.

## Vérifications

- Tests phase 8 ciblés : `23 passed` après ajout du plan et de ses tests.
- Aucun secret réel, URL webhook complète, appel réseau ou écriture distante.
