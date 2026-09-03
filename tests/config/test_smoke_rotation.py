from __future__ import annotations

import pytest

from config.schema import ConfigurationError
from config.smoke_rotation import SmokeRotationPlan


def test_rotation_plan_is_value_free_and_requires_dual_acceptance() -> None:
    plan = SmokeRotationPlan("env:OLD_SKULL_SECRET", "file:/etc/skull/next-secret")
    assert plan.ready_for_consumer_deploy is False
    assert plan.steps() == (
        "deploy-consumer-next",
        "switch-producer-next",
        "verify-next",
        "retire-consumer-current",
    )
    diagnostic = plan.redacted_dict()
    assert diagnostic["current_ref"] == "<secret-ref>"
    assert diagnostic["next_ref"] == "<secret-ref>"
    assert "OLD_SKULL_SECRET" not in str(diagnostic)


def test_rotation_plan_can_be_unblocked_only_by_explicit_flag() -> None:
    plan = SmokeRotationPlan("env:OLD_SKULL_SECRET", "env:NEXT_SKULL_SECRET", True)
    assert plan.ready_for_consumer_deploy is True


@pytest.mark.parametrize(
    ("current", "next"),
    [("old", "env:NEXT_SKULL_SECRET"), ("env:OLD_SKULL_SECRET", "env:OLD_SKULL_SECRET"), ("env:bad-name", "env:NEXT_SKULL_SECRET")],
)
def test_rotation_plan_rejects_invalid_or_identical_references(current: str, next: str) -> None:
    with pytest.raises(ConfigurationError, match="Rotation fumée"):
        SmokeRotationPlan(current, next)
