"""
Minimal hardware driver for Raspberry Pi 4 + PCA9685 controlling 4 servos.
No simulation: this module requires real I2C hardware and Adafruit libraries.

Channel mapping (fixed):
- jaw        -> CH 0
- eye_left   -> CH 1
- eye_right  -> CH 2
- neck_pan   -> CH 3

Angles are in degrees [0..180]. Per-servo mechanical clamps are enforced.

MODIFIED: Intégré avec système de logging pour traçage des commandes servo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

# Hard dependency: raise at import time if missing (no simulation).
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Adafruit PCA9685 stack is required (no simulation). Install on RPi: "
        "pip install adafruit-circuitpython-pca9685 adafruit-blinka"
    ) from e

# Import du système de logging
from logger import servo_logger


# ----------------------------- Servo model ---------------------------------
@dataclass
class ServoSpec:
    channel: int
    min_us: int = 500  # microseconds @ 0°
    max_us: int = 2500  # microseconds @ 180°
    min_deg: float = 0.0
    max_deg: float = 180.0
    pitch_offset: float = 0.0

    def clamp(self, deg: float) -> float:
        return max(self.min_deg, min(self.max_deg, deg))

    def angle_to_us(self, deg: float) -> float:
        d = self.clamp(deg + self.pitch_offset)
        span = self.max_us - self.min_us
        return self.min_us + (d / 180.0) * span


class PCA9685Controller:
    """Thin wrapper around Adafruit PCA9685 to drive pulses in microseconds."""

    def __init__(self, address: int = 0x40, frequency: int = 50):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(self.i2c, address=address)
        self.pca.frequency = frequency
        self._period_us = 1_000_000.0 / frequency

    def set_pulse_us(self, channel: int, pulse_us: float) -> None:
        # Convert desired microseconds to 16-bit duty cycle for PCA9685
        pulse_us = max(0.0, min(self._period_us, float(pulse_us)))
        duty = int((pulse_us / self._period_us) * 0xFFFF)
        self.pca.channels[channel].duty_cycle = duty

    def off(self) -> None:
        for ch in range(16):
            self.pca.channels[ch].duty_cycle = 0

    def deinit(self) -> None:
        try:
            self.off()
        finally:
            self.pca.deinit()


class Hardware:
    """High-level facade exposing named servos with clamps.

    Usage:
        hw = Hardware()
        hw.set_named_angle("jaw", 140)
        hw.cleanup()
    """

    # Fixed mapping + mechanical clamps
    SPECS: Dict[str, ServoSpec] = {
        "jaw": ServoSpec(channel=0, min_deg=110, max_deg=185, pitch_offset=0.0),
        "eye_left": ServoSpec(channel=1, min_deg=60, max_deg=120, pitch_offset=-14),
        "eye_right": ServoSpec(channel=2, min_deg=60, max_deg=120, pitch_offset=0.0),
        "neck_pan": ServoSpec(channel=3, min_deg=0, max_deg=180, pitch_offset=0.0),
    }

    def __init__(self, address: int = 0x40, frequency: int = 50):
        self.ctrl = PCA9685Controller(address=address, frequency=frequency)

    def set_named_angle(self, name: str, deg: float, log_enabled: bool = True) -> None:
        """
        Positionne un servo à l'angle donné.

        Args:
            name: nom du servo ("jaw", "eye_left", "eye_right", "neck_pan")
            deg: angle en degrés
            log_enabled: indique si le servo est activé (pour logging)
        """
        spec = self.SPECS[name]
        clamped_deg = spec.clamp(deg)
        us = spec.angle_to_us(clamped_deg)

        # Envoyer la commande au matériel
        self.ctrl.set_pulse_us(spec.channel, us)

        # Logger la commande (avec l'angle clampé effectif)
        servo_logger.log_servo_command(name, clamped_deg, log_enabled)

        # Warning si l'angle a été clampé
        if abs(clamped_deg - deg) > 0.1:
            servo_logger.logger.warning(
                f"CLAMP | {name} | Requested: {deg:.1f}° → Clamped: {clamped_deg:.1f}°"
            )

    def neutral(self) -> None:
        """Move to safe neutral positions"""
        servo_logger.logger.info("NEUTRAL_POSITION")
        self.set_named_angle("jaw", 180, log_enabled=True)  # slightly closed
        self.set_named_angle("eye_left", 90, log_enabled=True)
        self.set_named_angle("eye_right", 90, log_enabled=True)
        self.set_named_angle("neck_pan", 90, log_enabled=True)

    def cleanup(self) -> None:
        servo_logger.logger.info("HARDWARE_CLEANUP")
        self.ctrl.deinit()

    def set_pitch_offset(self, servo_name: str, offset: float) -> None:
        """Définit l'offset de pitch pour un servo"""
        if servo_name in self.SPECS:
            self.SPECS[servo_name].pitch_offset = offset
            servo_logger.logger.info(
                f"PITCH_OFFSET | {servo_name} | Offset: {offset:.1f}°"
            )


__all__ = ["Hardware", "ServoSpec", "PCA9685Controller"]
