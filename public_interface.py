#!/usr/bin/env python3
"""
Interface publique Halloween pour Servo Sync Player
- Port 5001 (UI identique)
- File d'attente partagée + cooldown 3 min par utilisateur (UUID navigateur)
- Gestion de la musique via WebSocket (et NON plus via POST/GET HTTP)
- Le serveur (ce script) pilote la lecture, surveille la fin, et lance la suivante
- Persistance fiable: data/playlist_state.json (écriture atomique)
"""

import os
import json
import time
import uuid
import shutil
import tempfile
import threading
import traceback
from pathlib import Path
from collections import deque
from datetime import datetime, timedelta, timezone

from flask import Flask, render_template_string, request, jsonify

# === Dépendance WebSocket côté client Python ===
# pip install websocket-client
import websocket  # websocket-client

app = Flask(__name__)

# =====================
# Configuration
# =====================
MAIN_WS_URL = "ws://192.168.1.116:5000/ws"  # <— adapte si besoin
WS_CONNECT_TIMEOUT = 5
WS_PING_INTERVAL = 20  # toutes les 20s
WS_PING_TIMEOUT = 10

COOLDOWN_MINUTES = 3
COOLDOWN_SECONDS = COOLDOWN_MINUTES * 60

DATA_DIR = Path("data")
STATE_PATH = DATA_DIR / "playlist_state.json"

# Si le WS est indisponible longtemps, on NE lance pas la suivante (pas de fallback HTTP).
# (optionnel) watchdog anti-blocage si on souhaite "oublier" un now_playing trop ancien même sans WS.
STALE_PLAYBACK_SECONDS = None  # ex: 1800 (30 min) ou None pour désactiver.


# =====================
# État partagé (mémoire) + persistance
# =====================
# Cooldown par utilisateur (UUID navigateur)
last_usage = {}  # user_id -> datetime (UTC)
# File d'attente commune
# item = {"song": str, "user_id": str, "requested_at": float}
queue = deque()
# Lecture en cours (vue locale)
# now_playing = {"song": str, "user_id": str|None, "started_at": float}
now_playing = None
# Dernier état playing connu reçu par WS (None|True|False)
last_playing_flag = None

# Concurrence
lock = threading.Lock()

# WS runtime
ws_obj = None
ws_connected = False
ws_lock = threading.Lock()  # protège ws_obj/ws_connected
ws_should_stop = False


# =============== Persistance ===============
def _dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _iso_to_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _write_json_atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp_state_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass


def save_state():
    with lock:
        data = {
            "last_usage": {k: _dt_to_iso(v) for k, v in last_usage.items()},
            "queue": list(queue),
            "now_playing": now_playing,
            "last_playing_flag": last_playing_flag,
            "version": 1,
            "saved_at": _dt_to_iso(datetime.now(timezone.utc)),
        }
    _write_json_atomic(STATE_PATH, data)


def load_state():
    global last_usage, queue, now_playing, last_playing_flag
    if not STATE_PATH.exists():
        return
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        lu = data.get("last_usage", {})
        q = data.get("queue", [])
        np = data.get("now_playing")
        lpf = data.get("last_playing_flag")

        _lu = {}
        for k, v in lu.items():
            dt = _iso_to_dt(v)
            if dt:
                _lu[k] = dt

        _q = deque()
        for it in q:
            if isinstance(it, dict) and "song" in it and "user_id" in it:
                _q.append(
                    {
                        "song": str(it["song"]),
                        "user_id": str(it["user_id"]),
                        "requested_at": float(it.get("requested_at", time.time())),
                    }
                )

        _np = None
        if isinstance(np, dict) and "song" in np:
            _np = {
                "song": str(np["song"]),
                "user_id": np.get("user_id"),
                "started_at": float(np.get("started_at", time.time())),
            }

        if lpf not in (None, True, False):
            lpf = None

        with lock:
            last_usage = _lu
            queue = _q
            now_playing = _np
            last_playing_flag = lpf
    except Exception:
        # Fichier corrompu: repartir propre
        with lock:
            last_usage = {}
            queue = deque()
            now_playing = None
            last_playing_flag = None


# =============== Cooldown ===============
def cooldown_left_seconds(user_id: str) -> int:
    with lock:
        t0 = last_usage.get(user_id)
    if not t0:
        return 0
    elapsed = datetime.now(timezone.utc) - t0
    remaining = timedelta(seconds=COOLDOWN_SECONDS) - elapsed
    return max(0, int(remaining.total_seconds()))


def mark_started(song: str, user_id: str | None):
    """MAJ de l'état quand une lecture démarre (confirmée par WS/serveur)."""
    global now_playing
    with lock:
        now_playing = {"song": song, "user_id": user_id, "started_at": time.time()}
        if user_id:
            last_usage[user_id] = datetime.now(timezone.utc)
    save_state()


# =============== WebSocket client ===============
def ws_send_json(obj: dict):
    """Envoi sûr d'un JSON sur le WS, si connecté."""
    payload = json.dumps(obj)
    with ws_lock:
        w = ws_obj
        connected = ws_connected
    if not connected or w is None:
        return False
    try:
        w.send(payload)
        return True
    except Exception:
        return False


def _handle_ws_message(msg: str):
    """Traite les messages entrants WS (JSON attendu)."""
    global last_playing_flag, now_playing
    try:
        data = json.loads(msg)
    except Exception:
        return

    # On attend principalement des messages de statut:
    # {"type":"status", "playing": true|false, "current_session":"Nom?"}
    if data.get("type") == "status":
        playing = bool(data.get("playing", False))
        current = data.get("current_session")
        prev = None
        with lock:
            prev = last_playing_flag
            last_playing_flag = playing
            # Miroir local du titre courant
            if playing:
                if current:
                    if (now_playing is None) or (now_playing.get("song") != current):
                        now_playing = {
                            "song": current,
                            "user_id": (
                                now_playing.get("user_id") if now_playing else None
                            ),
                            "started_at": (
                                now_playing.get("started_at")
                                if now_playing
                                else time.time()
                            ),
                        }
                        save_state()
            else:
                if now_playing is not None:
                    now_playing = None
                    save_state()

        # Détection de fin réelle: True -> False
        if prev is True and playing is False:
            _advance_playlist()

    # On pourrait aussi gérer des acks: {"type":"ack","action":"play","ok":true}
    # mais ici on s'aligne surtout sur le statut "playing".


def _advance_playlist():
    """Lancer le prochain morceau si dispo (appelé uniquement à la fin réelle)."""
    next_item = None
    with lock:
        if queue:
            next_item = queue.popleft()
            save_state()
    if not next_item:
        return

    # Envoyer la commande play via WS
    ok = ws_send_json({"action": "play", "session": next_item["song"]})
    if not ok:
        # WS non dispo -> remettre l'item en tête pour réessayer à la prochaine fin
        with lock:
            queue.appendleft(next_item)
            save_state()
        return

    # On ne marque pas immédiatement "started" : on attend un status "playing:true"
    # Mais il est acceptable de marquer localement en optimiste si besoin:
    # mark_started(next_item["song"], next_item["user_id"])


def ws_on_open(ws):
    with ws_lock:
        global ws_connected
        ws_connected = True
    # Optionnel: s'annoncer / demander un premier status
    ws_send_json({"action": "hello", "client": "public_interface"})
    ws_send_json({"action": "get_status"})


def ws_on_close(ws, status_code, msg):
    with ws_lock:
        global ws_connected
        ws_connected = False


def ws_on_error(ws, error):
    with ws_lock:
        global ws_connected
        ws_connected = False


def ws_on_message(ws, message):
    _handle_ws_message(message)


def ws_thread():
    """Boucle de connexion WS avec auto-reconnect + ping/pong."""
    global ws_obj
    while not ws_should_stop:
        try:
            ws = websocket.WebSocketApp(
                MAIN_WS_URL,
                on_open=ws_on_open,
                on_message=ws_on_message,
                on_error=ws_on_error,
                on_close=ws_on_close,
            )
            with ws_lock:
                ws_obj = ws

            # run_forever fait les pings si spécifiés
            ws.run_forever(
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=WS_PING_TIMEOUT,
                ping_payload="ping",
            )
        except Exception:
            pass

        with ws_lock:
            ws_obj = None

        # petite pause avant tentative de reconnexion
        if ws_should_stop:
            break
        time.sleep(2)


# =============== Playlist supervisor (watchdog / optional) ===============
def playlist_watchdog():
    """
    Optionnel: si STALE_PLAYBACK_SECONDS est configuré et que le WS tombe,
    on peut "oublier" un now_playing trop ancien pour éviter une UI figée.
    (Ne démarre jamais un morceau: déclenchements uniquement via WS)
    """
    if not STALE_PLAYBACK_SECONDS:
        return
    while True:
        try:
            with ws_lock:
                connected = ws_connected
            if not connected:
                with lock:
                    if (
                        now_playing
                        and (time.time() - now_playing["started_at"])
                        > STALE_PLAYBACK_SECONDS
                    ):
                        # On considère fini localement (uniquement pour l'affichage)
                        # Le démarrage suivant nécessite toujours une transition WS réelle.
                        # Ici on ne lance rien, juste on "libère" l'affichage.
                        pass
            time.sleep(5)
        except Exception:
            time.sleep(5)


# =============== HTML (UI identique) ===============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎃 Skull Player Halloween</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Georgia', serif;
            background: linear-gradient(45deg, #1a0033, #330066, #660033);
            background-size: 400% 400%;
            animation: spookyGradient 15s ease infinite;
            color: #ff6600;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }
        @keyframes spookyGradient { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        body::before {
            content: '';
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background:
                radial-gradient(circle at 20% 30%, rgba(255, 102, 0, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 70%, rgba(138, 43, 226, 0.1) 0%, transparent 50%);
            pointer-events: none;
        }
        .container { max-width: 500px; margin: 0 auto; padding: 20px; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; position: relative; z-index: 1; }
        .skull-header { text-align: center; margin-bottom: 40px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-10px); } }
        .skull-title {
            font-size: clamp(2rem, 8vw, 3.5rem); font-weight: bold;
            text-shadow: 0 0 20px #ff6600, 0 0 40px #ff6600, 3px 3px 0px #cc3300;
            margin-bottom: 10px; filter: drop-shadow(0 0 10px rgba(255, 102, 0, 0.8));
        }
        .skull-subtitle { font-size: 1.2rem; color: #cc99ff; text-shadow: 0 0 10px #663399; opacity: 0.9; }
        .main-card {
            background: linear-gradient(135deg, rgba(0,0,0,0.7), rgba(51,0,51,0.8));
            border: 2px solid #ff6600; border-radius: 20px; padding: 30px 25px;
            box-shadow: 0 0 30px rgba(255, 102, 0, 0.3), inset 0 0 20px rgba(0,0,0,0.3);
            backdrop-filter: blur(5px); position: relative; overflow: hidden;
        }
        .main-card::before {
            content: ''; position: absolute; top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, #ff6600, #cc3300, #663399, #ff6600);
            background-size: 400% 400%; animation: borderGlow 3s ease infinite; border-radius: 20px; z-index: -1;
        }
        @keyframes borderGlow { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        .playlist { margin-bottom: 30px; }
        .playlist-title { font-size: 1.3rem; text-align: center; margin-bottom: 20px; color: #ffaa00; text-shadow: 0 0 10px #ff6600; }
        .song-item {
            background: rgba(0,0,0,0.5); border: 1px solid #ff6600; border-radius: 15px; padding: 15px;
            margin: 10px 0; cursor: pointer; transition: all 0.3s ease; position: relative; overflow: hidden;
        }
        .song-item:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(255, 102, 0, 0.4); border-color: #ffaa00; }
        .song-item.selected { background: linear-gradient(135deg, rgba(255, 102, 0, 0.2), rgba(204, 51, 0, 0.3)); border-color: #ffaa00; box-shadow: 0 0 20px rgba(255, 102, 0, 0.5); }
        .song-name { font-size: 1.1rem; font-weight: bold; color: #ffcc99; text-shadow: 0 0 5px #ff6600; }
        .play-button {
            width: 100%; background: linear-gradient(135deg, #ff6600, #cc3300); border: none; border-radius: 15px; padding: 20px;
            font-size: 1.4rem; font-weight: bold; color: white; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 2px;
            text-shadow: 0 0 10px rgba(0,0,0,0.5); margin-top: 20px; position: relative; overflow: hidden;
        }
        .play-button::before {
            content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent); transition: left 0.5s;
        }
        .play-button:hover::before { left: 100%; }
        .play-button:hover { transform: scale(1.05); box-shadow: 0 0 30px rgba(255, 102, 0, 0.6); }
        .play-button:disabled { background: linear-gradient(135deg, #666, #444); cursor: not-allowed; opacity: 0.6; transform: none; box-shadow: none; }
        .cooldown { text-align: center; margin-top: 15px; padding: 15px; background: rgba(204, 51, 0, 0.2); border: 1px solid #cc3300; border-radius: 10px; color: #ffcccc; font-size: 0.9rem; }
        .status { text-align: center; margin-top: 20px; padding: 15px; border-radius: 10px; font-weight: bold; }
        .status.success { background: rgba(0, 255, 0, 0.1); border: 1px solid #00cc00; color: #aaffaa; }
        .status.error { background: rgba(255, 0, 0, 0.1); border: 1px solid #cc0000; color: #ffaaaa; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 2px solid #ff6600; border-radius: 50%; border-top-color: transparent; animation: spin 1s linear infinite; margin-right: 10px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .footer { text-align: center; margin-top: 40px; font-size: 0.8rem; color: #996633; opacity: 0.7; }
        @media (max-width: 480px) {
            .container { padding: 15px; }
            .main-card { padding: 20px 15px; }
            .skull-title { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="skull-header">
            <div class="skull-title">💀 Skull Player</div>
            <div class="skull-subtitle">Lancez votre musique préférée</div>
        </div>

        <div class="main-card">
            <div class="playlist">
                <div class="playlist-title">🎵 Choisissez votre chanson</div>
                <div id="songList"><!-- Songs will be loaded here --></div>
            </div>

            <button id="playButton" class="play-button" disabled>
                ▶️ Jouer la musique
            </button>

            <!-- Playlist commune -->
            <div class="playlist" style="margin-top:25px">
                <div class="playlist-title">📜 Playlist</div>
                <div id="nowPlaying" class="song-item" style="display:none;"></div>
                <div id="queueList"></div>
            </div>

            <div id="cooldownMessage" class="cooldown" style="display: none;"></div>
            <div id="statusMessage" class="status" style="display: none;"></div>
        </div>

        <div class="footer">🎃 Halloween Skull Experience 🎃</div>
    </div>

    <script>
        // UUID navigateur
        const UUID_KEY = 'skull_user_uuid';
        function genUUIDv4() {
            if (window.crypto && crypto.getRandomValues) {
                const buf = new Uint8Array(16);
                crypto.getRandomValues(buf);
                buf[6] = (buf[6] & 0x0f) | 0x40;
                buf[8] = (buf[8] & 0x3f) | 0x80;
                const toHex = b => b.toString(16).padStart(2, '0');
                return [...buf].map(toHex).join('').replace(
                    /^(.{8})(.{4})(.{4})(.{4})(.{12})$/,
                    '$1-$2-$3-$4-$5'
                );
            }
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                const r = Math.random()*16|0, v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
        function getUserUUID() {
            try {
                let id = localStorage.getItem(UUID_KEY);
                if (!id) {
                    id = genUUIDv4();
                    localStorage.setItem(UUID_KEY, id);
                }
                return id;
            } catch(e) {
                return genUUIDv4();
            }
        }

        let selectedSong = null;

        function showMessage(message, type = 'info', duration = 3000) {
            const statusEl = document.getElementById('statusMessage');
            statusEl.textContent = message;
            statusEl.className = `status ${type}`;
            statusEl.style.display = 'block';
            setTimeout(() => { statusEl.style.display = 'none'; }, duration);
        }

        function showCooldown(seconds) {
            const cooldownEl = document.getElementById('cooldownMessage');
            if (seconds <= 0) {
                cooldownEl.style.display = 'none';
                updatePlayButton();
                return;
            }
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const timeStr = minutes > 0 ? `${minutes}m ${secs}s` : `${secs}s`;
            cooldownEl.textContent = `⏰ Attendez encore ${timeStr} avant de rejouer`;
            cooldownEl.style.display = 'block';
            setTimeout(() => showCooldown(seconds - 1), 1000);
        }

        function updatePlayButton() {
            const button = document.getElementById('playButton');
            button.disabled = !selectedSong;
            if (selectedSong) {
                button.textContent = `▶️ Jouer "${selectedSong}"`;
            } else {
                button.textContent = '▶️ Choisissez une chanson';
            }
        }

        function selectSong(ev, songName) {
            selectedSong = songName;
            document.querySelectorAll('.song-item').forEach(item => item.classList.remove('selected'));
            ev.currentTarget.classList.add('selected');
            updatePlayButton();
        }

        async function playSelected() {
            if (!selectedSong) return;

            const userId = getUserUUID();
            const button = document.getElementById('playButton');
            const originalText = button.textContent;

            button.disabled = true;
            button.innerHTML = '<div class="loading"></div>Lancement en cours...';

            try {
                const response = await fetch('/play', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ song: selectedSong, user_id: userId })
                });
                const result = await response.json();

                if (response.status === 200 && result.success) {
                    showMessage('🎵 Musique lancée avec succès !', 'success');
                    showCooldown(result.cooldown_seconds);
                } else if (response.status === 202 && result.queued) {
                    showMessage(`🧾 Ajouté à la file (#${result.position}).`, 'success');
                } else if (response.status === 429) {
                    showMessage(result.message || 'Cooldown actif', 'error');
                    if (result.cooldown_seconds) showCooldown(result.cooldown_seconds);
                } else {
                    showMessage(result.error || 'Erreur inconnue', 'error');
                }
            } catch (error) {
                showMessage('Erreur de connexion', 'error');
            } finally {
                button.textContent = originalText;
                updatePlayButton();
                loadQueue();
            }
        }

        async function loadSongs() {
            try {
                const response = await fetch('/songs');
                const data = await response.json();
                const songList = document.getElementById('songList');
                songList.innerHTML = '';

                if (!data.songs || data.songs.length === 0) {
                    songList.innerHTML = '<div style="text-align: center; color: #999;">Aucune chanson disponible</div>';
                    return;
                }

                data.songs.forEach(song => {
                    const songItem = document.createElement('div');
                    songItem.className = 'song-item';
                    songItem.innerHTML = `<div class="song-name">${song}</div>`;
                    songItem.addEventListener('click', (ev) => selectSong(ev, song));
                    songList.appendChild(songItem);
                });
            } catch (error) {
                console.error('Erreur lors du chargement des chansons:', error);
            }
        }

        async function loadQueue() {
            try {
                const res = await fetch('/queue');
                const data = await res.json();

                // Now playing (pas de timer à l'écran)
                const np = document.getElementById('nowPlaying');
                if (data.now_playing && data.now_playing.song) {
                    np.style.display = 'block';
                    np.innerHTML = `<div class="song-name">▶️ Now playing: ${data.now_playing.song}</div>`;
                } else {
                    np.style.display = 'none';
                }

                // Queue
                const q = document.getElementById('queueList');
                q.innerHTML = '';
                if (!data.upcoming || data.upcoming.length === 0) {
                    q.innerHTML = '<div style="text-align:center; color:#999;">Aucun titre en attente</div>';
                } else {
                    data.upcoming.forEach((item, idx) => {
                        const el = document.createElement('div');
                        el.className = 'song-item';
                        el.innerHTML = `<div class="song-name">#${idx+1} — ${item.song}</div>`;
                        q.appendChild(el);
                    });
                }
            } catch (e) { /* silencieux */ }
        }

        document.getElementById('playButton').addEventListener('click', playSelected);

        // Init
        loadSongs();
        updatePlayButton();
        loadQueue();
        setInterval(loadQueue, 4000);
    </script>
</body>
</html>
"""


# =============== Routes HTTP UI (inchangées) ===============
def _get_sessions_via_disk_or_stub():
    """
    Tu peux remplacer cette fonction pour récupérer la liste autrement (WS/HTTP).
    Ici, on lit un fichier statique si présent: data/sessions.json
    Sinon, on renvoie une petite liste de test.
    """
    p = DATA_DIR / "sessions.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                js = json.load(f)
            if isinstance(js, list):
                return [str(x) for x in js]
        except Exception:
            pass
    # Fallback démo :
    return ["Halloween_Intro", "Spooky_Beat", "Ghost_Theme", "Pumpkin_Party"]


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/songs")
def songs():
    # TODO: si tu as un WS "list_sessions", adapte pour synchroniser.
    sessions = _get_sessions_via_disk_or_stub()
    return jsonify({"songs": sessions})


@app.route("/queue")
def get_queue():
    try:
        with lock:
            np = now_playing.copy() if now_playing else None
            items = list(queue)
            return jsonify(
                now_playing=np,
                upcoming=[
                    {"song": it["song"], "user_id": it["user_id"]} for it in items
                ],
            )
    except Exception as e:
        return (
            jsonify(
                now_playing=None, upcoming=[], error="queue_exception", detail=str(e)
            ),
            500,
        )


@app.route("/play", methods=["POST"])
def play():
    """
    Enfile une chanson si cooldown OK.
    Démarrage immédiat UNIQUEMENT si ws_connected == True, last_playing_flag == False
    et file vide + rien en cours (côté interface).
    Sinon on enqueue.
    """
    data = request.get_json(silent=True) or {}
    song_name = data.get("song")
    user_id = data.get("user_id")

    if not song_name:
        return jsonify({"success": False, "error": "Nom de chanson requis"}), 400
    if not user_id or not isinstance(user_id, str) or len(user_id) < 8:
        return jsonify({"success": False, "error": "user_id invalide"}), 400

    left = cooldown_left_seconds(user_id)
    if left > 0:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Attendez encore {left // 60}m {left % 60}s",
                    "cooldown_seconds": left,
                }
            ),
            429,
        )

    with lock:
        file_vide_local = len(queue) == 0 and now_playing is None

    with ws_lock:
        connected = ws_connected
    idle_remote = last_playing_flag is False

    # Démarrage immédiat si:
    # - WS connecté
    # - état distant idle (dernière info reçue)
    # - file vide localement et rien en cours
    if connected and idle_remote and file_vide_local:
        ok = ws_send_json({"action": "play", "session": song_name})
        if ok:
            # On attendra l'événement status:playing:true pour "mark_started" (source de vérité)
            # mais on peut marquer optimiste si tu préfères :
            # mark_started(song_name, user_id)
            # et laisser le status corriger si besoin.
            with lock:
                last_usage[user_id] = datetime.now(timezone.utc)  # cooldown immédiat
            save_state()
            return jsonify({"success": True, "cooldown_seconds": COOLDOWN_SECONDS}), 200

    # Sinon, on ajoute à la file
    with lock:
        queue.append(
            {"song": song_name, "user_id": user_id, "requested_at": time.time()}
        )
        position = len(queue)
        save_state()
    return jsonify({"queued": True, "position": position}), 202


# =============== Boot ===============
if __name__ == "__main__":
    print("🎃 Interface publique Halloween (WebSocket-powered)")
    print("Port UI: 5001")
    print(f"WS vers serveur principal: {MAIN_WS_URL}")
    print(f"État persistant: {STATE_PATH}")
    print(f"Cooldown: {COOLDOWN_MINUTES} minutes / utilisateur")

    # Charger l'état du disque
    load_state()

    # Démarrer WS + watchdog
    t_ws = threading.Thread(target=ws_thread, daemon=True)
    t_ws.start()

    if STALE_PLAYBACK_SECONDS:
        t_watch = threading.Thread(target=playlist_watchdog, daemon=True)
        t_watch.start()

    # Lancer Flask
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
