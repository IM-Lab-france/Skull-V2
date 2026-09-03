# Transitions playlist et état de lecture

| État initial | Événement | Résultat observé | Risque ou remarque |
|---|---|---|---|
| file vide, lecteur arrêté | ajout d’un élément puis `_ensure_playback_running` | l’élément est dépilé et démarré immédiatement | dépend de la réussite de `_start_session` |
| lecteur en lecture | ajout d’un élément | l’élément reste en file | pas de démarrage concurrent |
| lecteur en lecture | fin `completed` | entrée courante effacée, élément suivant démarré dans un thread | transition asynchrone |
| lecteur en lecture | `POST /playlist/skip` | `player.stop(reason="skip")`, réponse `skipping` | le callback de fin peut ensuite avancer la file |
| lecteur en lecture | `POST /stop` | lecteur arrêté et entrée courante effacée | la file n’est pas vidée par cette route |
| session courante présente | suppression de session | arrêt, suppression du répertoire, entrée courante effacée | opération destructive réservée à l’IHM |
| mode aléatoire | sélection | `Accueil` est exclue des candidats | exclusion insensible à la casse |
| file quelconque | deux ajouts concurrents | IDs uniques et file protégée par verrou | l’ordre dépend de l’arrivée des threads |
| lecteur arrêté | erreur Bluetooth ou audio au démarrage | démarrage refusé, entrée courante inchangée | `_start_next_from_playlist` réessaie avec temporisation |

Cette table décrit la version actuelle ; aucune correction de concurrence,
transition ou politique de retry n’est introduite dans cette tâche.
