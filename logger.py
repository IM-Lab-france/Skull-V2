"""
Système de logging pour les commandes servo et analyse de synchronisation.
Crée des logs détaillés avec timestamps et statistiques de performance.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime


class ServoLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Créer un logger spécifique pour les servos
        self.logger = logging.getLogger("servo_commands")
        self.logger.setLevel(logging.INFO)

        # Éviter les doublons de handlers
        if not self.logger.handlers:
            # Handler pour fichier avec rotation
            log_file = (
                self.log_dir / f"servo_commands_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.INFO)

            # Format détaillé avec timestamp précis
            formatter = logging.Formatter(
                "%(asctime)s.%(msecs)03d | %(message)s", datefmt="%H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # Tracking pour analyse
        self.session_start_time: Optional[float] = None
        self.audio_start_time: Optional[float] = None
        self.audio_duration: Optional[float] = None
        self.last_servo_command_time: Optional[float] = None
        self.servo_commands: List[Dict] = []
        self.current_session: Optional[str] = None

    def start_session(self, session_name: str, audio_duration: float):
        """Démarre une nouvelle session de logging"""
        self.current_session = session_name
        self.session_start_time = time.time()
        self.audio_duration = audio_duration
        self.servo_commands.clear()
        self.last_servo_command_time = None

        self.logger.info(f"=== SESSION START: {session_name} ===")
        self.logger.info(f"Audio duration: {audio_duration:.3f}s")

    def start_audio(self):
        """Marque le début de la lecture audio"""
        self.audio_start_time = time.time()
        self.logger.info("AUDIO_START")

    def log_servo_command(self, servo_name: str, angle: float, enabled: bool = True):
        """Log une commande servo avec timestamp précis"""
        current_time = time.time()

        if self.audio_start_time:
            elapsed = current_time - self.audio_start_time
        else:
            elapsed = 0.0

        # Enregistrer pour analyse
        command_data = {
            "timestamp": current_time,
            "elapsed_audio": elapsed,
            "servo": servo_name,
            "angle": angle,
            "enabled": enabled,
        }
        self.servo_commands.append(command_data)

        if enabled:
            self.last_servo_command_time = current_time

        # Log formaté
        status = "ACTIVE" if enabled else "FROZEN"
        self.logger.info(
            f"SERVO | {elapsed:7.3f}s | {servo_name:10} | {angle:6.1f}° | {status}"
        )

    def log_audio_end(self):
        """Marque la fin de la lecture audio"""
        if self.audio_start_time:
            audio_end_time = time.time()
            actual_duration = audio_end_time - self.audio_start_time
            self.logger.info(f"AUDIO_END | Duration: {actual_duration:.3f}s")
            return audio_end_time
        return None

    def end_session(self):
        """Termine la session et génère les statistiques"""
        if not self.current_session:
            return

        session_end_time = time.time()
        self.logger.info("=== SESSION END ===")

        # Calculer les métriques
        stats = self._calculate_stats(session_end_time)

        # Logger les statistiques
        self.logger.info("=== SYNCHRONIZATION ANALYSIS ===")
        self.logger.info(
            f"Total session duration: {stats['total_session_duration']:.3f}s"
        )
        self.logger.info(
            f"Expected audio duration: {stats['expected_audio_duration']:.3f}s"
        )
        self.logger.info(
            f"Actual audio duration: {stats['actual_audio_duration']:.3f}s"
        )
        self.logger.info(f"Audio drift: {stats['audio_drift']:.3f}s")

        if stats["last_servo_delay"] is not None:
            self.logger.info(
                f"Time between audio end and last servo: {stats['last_servo_delay']:.3f}s"
            )
            if abs(stats["last_servo_delay"]) > 0.1:
                self.logger.warning(
                    f"SYNC WARNING: Last servo command {stats['last_servo_delay']:.3f}s after audio end"
                )

        self.logger.info(f"Total servo commands: {stats['total_commands']}")
        self.logger.info(f"Commands per second: {stats['commands_per_second']:.1f}")

        # Recommandations
        recommendations = self._generate_recommendations(stats)
        for rec in recommendations:
            self.logger.warning(f"RECOMMENDATION: {rec}")

        self.logger.info("=" * 50)

        # Sauvegarder les stats en JSON pour analyse ultérieure
        self._save_session_stats(stats)

        # Reset
        self.current_session = None
        self.servo_commands.clear()

    def _calculate_stats(self, session_end_time: float) -> Dict:
        """Calcule les statistiques de synchronisation"""
        stats = {
            "session_name": self.current_session,
            "total_session_duration": (
                session_end_time - self.session_start_time
                if self.session_start_time
                else 0
            ),
            "expected_audio_duration": self.audio_duration or 0,
            "actual_audio_duration": 0,
            "audio_drift": 0,
            "last_servo_delay": None,
            "total_commands": len(self.servo_commands),
            "commands_per_second": 0,
            "servo_stats": {},
        }

        if self.servo_commands and self.audio_start_time:
            # Durée audio réelle (approximation basée sur le dernier timestamp)
            last_command = max(self.servo_commands, key=lambda x: x["elapsed_audio"])
            stats["actual_audio_duration"] = last_command["elapsed_audio"]

            # Dérive audio
            stats["audio_drift"] = (
                stats["actual_audio_duration"] - stats["expected_audio_duration"]
            )

            # Délai dernier servo vs fin audio théorique
            if self.last_servo_command_time and self.audio_start_time:
                last_servo_elapsed = (
                    self.last_servo_command_time - self.audio_start_time
                )
                stats["last_servo_delay"] = (
                    last_servo_elapsed - stats["expected_audio_duration"]
                )

            # Commandes par seconde
            if stats["actual_audio_duration"] > 0:
                stats["commands_per_second"] = (
                    stats["total_commands"] / stats["actual_audio_duration"]
                )

            # Stats par servo
            servo_counts = {}
            for cmd in self.servo_commands:
                servo = cmd["servo"]
                if servo not in servo_counts:
                    servo_counts[servo] = {"active": 0, "frozen": 0}
                if cmd["enabled"]:
                    servo_counts[servo]["active"] += 1
                else:
                    servo_counts[servo]["frozen"] += 1
            stats["servo_stats"] = servo_counts

        return stats

    def _generate_recommendations(self, stats: Dict) -> List[str]:
        """Génère des recommandations basées sur les stats"""
        recommendations = []

        # Dérive audio
        if abs(stats["audio_drift"]) > 0.5:
            recommendations.append(
                f"Audio drift de {stats['audio_drift']:.3f}s détecté - vérifier la timeline"
            )

        # Délai servo/audio
        if stats["last_servo_delay"] is not None:
            if stats["last_servo_delay"] > 0.2:
                recommendations.append(
                    "Dernière commande servo trop tardive - timeline trop longue"
                )
            elif stats["last_servo_delay"] < -0.2:
                recommendations.append(
                    "Dernière commande servo trop précoce - timeline trop courte"
                )

        # Fréquence des commandes
        if stats["commands_per_second"] < 30:
            recommendations.append(
                f"Fréquence faible ({stats['commands_per_second']:.1f} cmd/s) - augmenter la résolution"
            )
        elif stats["commands_per_second"] > 100:
            recommendations.append(
                f"Fréquence élevée ({stats['commands_per_second']:.1f} cmd/s) - possibles saccades"
            )

        return recommendations

    def _save_session_stats(self, stats: Dict):
        """Sauvegarde les stats de session en JSON"""
        stats_file = (
            self.log_dir
            / f"session_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        # Ajouter timestamp pour le nom de fichier
        stats["timestamp"] = datetime.now().isoformat()

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def get_latest_log_file(self) -> Path:
        """Retourne le chemin du fichier de log actuel"""
        return self.log_dir / f"servo_commands_{datetime.now().strftime('%Y%m%d')}.log"


# Instance globale
servo_logger = ServoLogger()
