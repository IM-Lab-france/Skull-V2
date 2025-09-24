# gaze_receiver.py
# Récepteur UDP résilient aux reloaders Flask : ne bind que dans le bon process.
# - En mode debug Flask, le parent du reloader N'ECOUTE PAS (pas de bind).
# - Le worker (WERKZEUG_RUN_MAIN="true") écoute normalement.
# - Hors Flask debug (prod, script simple) : écoute normalement.
#
# API:
#   gr = GazeReceiver(host="127.0.0.1", port=5005)
#   cmd = gr.get_command()   # démarre l'écoute si nécessaire, renvoie la commande fraîche ou None
#   gr.ensure_started()      # optionnel: démarrer explicitement
#   gr.stop()                # arrêter proprement

import os
import socket
import json
import threading
import time
from typing import Optional


def _is_flask_debug_parent() -> bool:
    """
    Détecte le processus 'parent' du reloader Flask.
    - Quand Flask debug est actif, le parent lance un enfant avec WERKZEUG_RUN_MAIN="true".
      Le parent n'a PAS cette variable et n'écoute pas HTTP.
    - On NE DOIT PAS binder l'UDP dans le parent, pour éviter 'Address already in use'.
    """
    # Si on force via env, on respecte
    force = os.environ.get("GAZE_FORCE_START")
    if force in ("1", "true", "yes", "on"):
        return False

    flask_debug = os.environ.get("FLASK_DEBUG") in ("1", "true", "True")
    is_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    # Cas classique: debug ON et on est le parent (pas is_child)
    if flask_debug and not is_child:
        return True

    return False


class GazeReceiver:
    # Garde-fou: empêchez 2 démarrages dans LE MÊME process
    _started_in_process = False
    _class_lock = threading.Lock()

    def __init__(
        self, host: str = "127.0.0.1", port: int = 5005, autostart: bool = True
    ):
        self.host = host
        self.port = port

        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.running = threading.Event()
        self.running.clear()

        self.latest = None
        self.lock = threading.Lock()

        # Si on est dans le parent du reloader Flask -> démarrage différé (pas de bind ici)
        self._deferred = _is_flask_debug_parent()

        if autostart and not self._deferred:
            self.ensure_started()

    def ensure_started(self):
        """Démarre le bind + thread de réception si ce n'est pas déjà fait dans CE process."""
        if self.running.is_set():
            return

        with self._class_lock:
            if GazeReceiver._started_in_process:
                # déjà démarré dans ce process
                return

            # Création socket + bind
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # (Optionnel) permettre un redémarrage rapide après crash
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass

            try:
                self.sock.bind((self.host, self.port))
            except OSError as e:
                # Message explicite pour comprendre le contexte
                raise OSError(
                    f"[GazeReceiver] Impossible de binder {self.host}:{self.port} "
                    f"(peut-être déjà occupé par un autre process). Détail: {e}"
                )

            self.sock.setblocking(False)

            # Thread de réception
            self.running.set()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

            GazeReceiver._started_in_process = True

    def _loop(self):
        while self.running.is_set():
            try:
                data, _ = self.sock.recvfrom(8192)
                if not data:
                    time.sleep(0.01)
                    continue
                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    time.sleep(0.005)
                    continue
                with self.lock:
                    self.latest = msg
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                # ne pas faire crasher le thread
                print(f"[GazeReceiver] socket error: {e}")
                time.sleep(0.1)

    def get_command(self):
        """
        Retourne la dernière commande fraîche (selon ttl_ms), sinon None.
        Démarre l'écoute à la volée si elle était différée.
        """
        if not self.running.is_set() and not self._deferred:
            # cas: autostart=False -> on démarre à la demande
            self.ensure_started()
        elif self._deferred:
            # On était dans le parent Flask; on ne doit pas écouter ici.
            # Retourne None proprement (le worker fera l'écoute).
            return None

        with self.lock:
            cmd = self.latest

        if not cmd:
            return None

        now = time.time()
        ts = float(cmd.get("ts", now))
        ttl_ms = int(cmd.get("ttl_ms", 250))
        if now - ts > (ttl_ms / 1000.0):
            return None

        return cmd

    def stop(self, timeout: float = 1.0):
        self.running.clear()
        try:
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=timeout)
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        finally:
            self.sock = None
        with self._class_lock:
            GazeReceiver._started_in_process = False
