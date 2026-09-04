# SKULL-02.3 — dependances reproductibles

## Statut

**VALIDÉ — dépendances verrouillées et validation ARM64 réussie.**

## Resultats

- Imports Python reels inspectes dans les modules du worktree.
- Dependances directes separees dans `requirements.in`.
- Dependances directes de `playlist_web.py` separees dans
  `requirements-playlist.in`.
- `requirements.lock` reprend les dépendances du freeze principal de
  `evidence/SKULL-01.2/`, puis a été régénéré par `pip-compile`.
- `requirements-playlist.lock` reprend les dépendances du freeze playlist de
  `evidence/SKULL-01.2/`, puis a été régénéré par `pip-compile`.
- Dependances systeme Raspberry documentees dans `DEPENDENCIES.md`.
- `python -m compileall -q .` : succès dans le conteneur de test.
- Les deux locks ont été régénérés par `pip-compile` avec Python 3.11.
- Installation complète des deux locks réussie dans un venv éphémère
  `linux/arm64` sous Docker Desktop.
- Imports de contrôle réussis : Flask, NumPy, pydub, requests, sounddevice et
  soundfile (`IMPORTS_OK`).
- Le moteur audio et FFmpeg ont été rendus disponibles dans le conteneur avec
  PortAudio, ALSA et libsndfile ; aucune interface I2C, GPIO ou Bluetooth n’a
  été exposée au test.

## Limites

La validation a utilisé Docker Desktop 4.89.0 avec le moteur Docker 29.7.2 et
un conteneur `python:3.11-slim` en `linux/arm64`, sous émulation sur le poste
Windows x86_64. Le venv, le conteneur et les paquets installés ont été
éphémères ; la compatibilité réelle avec les bibliothèques matérielles du
Raspberry reste à confirmer lors d’une future validation sur le Skull.

## Fichiers

```text
requirements.in
requirements-playlist.in
requirements.lock
requirements-playlist.lock
DEPENDENCIES.md
```

Aucun secret, `.env`, log, venv persistant ou fichier runtime n’a été ajouté.
Aucun push ni changement Raspberry n’a été effectué.
