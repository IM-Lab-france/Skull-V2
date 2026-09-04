# Résultat SKULL-03.2

- Date : 3 septembre 2026
- Statut : VALIDÉ
- Portée : caractérisation locale de `timeline.py`, sans audio, réseau,
  Raspberry, I²C, GPIO ou mouvement.
- Fichiers ajoutés dans le worktree : fixtures synthétiques JSON et
  `tests/unit/test_timeline_characterization.py`. Le parseur `timeline.py`
  n’a pas été modifié.
- Validation : `python -m pytest --collect-only -q` — 12 tests collectés ;
  `python -m pytest -q` — 12 tests réussis ; `python -m compileall -q .` et
  `git diff --check` réussis.
- Couverture : racines `timeline`, `keyframes`, `frames` et canaux top-level ;
  timestamps en bordure ; keyframes simultanées ; canaux absents ; fichier
  vide, JSON invalide et format inconnu ; mâchoire à 0/50/100 % ; valeurs hors
  limites et durée nulle.
- Référence figée : les durées, nombres de frames, timestamps et angles sont
  vérifiés par assertions dans le test. Les inversions et valeurs hors plage
  observées sont détaillées dans [MECHANICAL-RISKS.md](MECHANICAL-RISKS.md).
- Écart ou risque : les fixtures sont synthétiques et ne prouvent pas la
  sécurité mécanique réelle. Une correction du parseur et toute validation
  physique relèvent de tâches ultérieures.
- Rollback : supprimer les fixtures, le test et le rapport de risque de cette
  tâche ; restaurer uniquement les entrées de suivi correspondantes.

Aucune donnée de production, session audio, adresse privée, MAC ou secret n’a
été copié dans Git.
