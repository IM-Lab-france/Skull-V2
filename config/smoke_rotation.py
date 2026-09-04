"""Safe, value-free plan for rotating the smoke webhook reference."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .schema import ConfigurationError


_REF = re.compile(r"^(?:env:[A-Z][A-Z0-9_]*|file:/[^\r\n]+)$")


def _check_ref(value: str, field: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ConfigurationError(f"Rotation fumée: {field}: référence invalide")
    return value


@dataclass(frozen=True)
class SmokeRotationPlan:
    """References and gates for a rotation; never contains secret contents."""

    current_ref: str
    next_ref: str
    dual_acceptance_confirmed: bool = False

    def __post_init__(self) -> None:
        _check_ref(self.current_ref, "current_ref")
        _check_ref(self.next_ref, "next_ref")
        if self.current_ref == self.next_ref:
            raise ConfigurationError("Rotation fumée: références identiques")

    @property
    def ready_for_consumer_deploy(self) -> bool:
        return self.dual_acceptance_confirmed

    def steps(self) -> tuple[str, ...]:
        return (
            "deploy-consumer-next",
            "switch-producer-next",
            "verify-next",
            "retire-consumer-current",
        )

    def redacted_dict(self) -> dict[str, object]:
        return {
            "current_ref": "<secret-ref>",
            "next_ref": "<secret-ref>",
            "dual_acceptance_confirmed": self.dual_acceptance_confirmed,
            "ready_for_consumer_deploy": self.ready_for_consumer_deploy,
            "steps": list(self.steps()),
        }


__all__ = ["SmokeRotationPlan"]
