from __future__ import annotations

import pytest

from config.secrets import resolve_secret
from config.schema import ConfigurationError


def test_env_secret_is_resolved_without_being_part_of_configuration_output() -> None:
    assert resolve_secret("env:TEST_SKULL_SECRET", environ={"TEST_SKULL_SECRET": "value-never-logged"}) == "value-never-logged"


def test_file_secret_is_read_only(tmp_path) -> None:
    path = tmp_path / "secrets.env"
    path.write_text("value-never-logged\n", encoding="utf-8")
    before = path.read_bytes()
    assert resolve_secret(f"file:{path}") == "value-never-logged"
    assert path.read_bytes() == before


@pytest.mark.parametrize("reference", ["value", "env:bad-name", "file:relative.env"])
def test_invalid_secret_reference_is_safe(reference: str) -> None:
    with pytest.raises(ConfigurationError, match="Secret indisponible") as error:
        resolve_secret(reference)
    assert "value-never-logged" not in str(error.value)
