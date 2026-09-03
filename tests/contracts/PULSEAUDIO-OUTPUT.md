# Contrat de sortie PulseAudio

`PulseAudioOutputAdapter` ne considère jamais `connected=true` comme une
preuve audio suffisante. Pour une adresse Bluetooth donnée, il exige :

1. une carte `bluez_card.<adresse>` identifiée exactement ;
2. le profil actif `a2dp_sink` ;
3. un unique sink Bluetooth correspondant à l’adresse, sous la nomenclature
   PulseAudio `bluez_sink.<adresse>.*` ou PipeWire `bluez_output.<adresse>.*`,
   non suspendu et devenu le sink par défaut par son nom stable.

L’attente de création du sink est bornée par
`PLAYLIST_PULSE_AUDIO_WAIT_TIMEOUT` et `PLAYLIST_PULSE_AUDIO_POLL_INTERVAL`.
Les commandes ne modifient ni volume ni mute.

Quand le processus tourne comme unité systemd sans environnement de session,
l’adaptateur cible explicitement le socket utilisateur canonique
`unix:/run/user/<uid>/pulse/native`, sauf si `PULSE_SERVER` ou
`XDG_RUNTIME_DIR` est déjà défini. Cette séparation évite de confondre
l’absence de contexte de session avec l’absence de PulseAudio.

Un fallback local est désactivé par défaut. Il ne peut être utilisé que si
`PLAYLIST_PULSE_AUDIO_FALLBACK_SINK` contient un identifiant explicite et que
`PLAYLIST_PULSE_AUDIO_FALLBACK_ENABLED` vaut `1`, `true`, `yes` ou `on`. La
réponse marque alors `fallback_used: true`, afin qu’aucun basculement ne soit
silencieux.
