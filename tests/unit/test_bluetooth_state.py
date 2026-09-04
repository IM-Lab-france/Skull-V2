from __future__ import annotations

import pytest

from domain.bluetooth import (
    A2DP_AUDIO_SINK_UUID,
    BluetoothDeviceState,
    parse_bluez_properties,
    parse_bluez_uuids,
    validate_bluetooth_address,
)
from tests.fixtures.bluetooth_observations import (
    BLE_NON_AUDIO,
    JBL_QUANTUM_360,
    SOUNDLINK_MINI,
)


@pytest.mark.parametrize(
    ("observation", "name", "audio_sink", "connected"),
    [
        (JBL_QUANTUM_360, "JBL Quantum 360", True, True),
        (SOUNDLINK_MINI, "SoundLink Mini", True, False),
        (BLE_NON_AUDIO, "BLE Sensor", False, True),
    ],
)
def test_known_bluetooth_fixtures_produce_distinct_audio_states(
    observation: str, name: str, audio_sink: bool, connected: bool
) -> None:
    state = BluetoothDeviceState.from_bluez_info(
        observation.splitlines()[0].split()[1], observation, updated_at=10.0
    )

    assert state.name == name
    assert state.discovered is True
    assert state.connected is connected
    assert state.audio_sink_capable is audio_sink
    assert state.pulse_sink is None
    assert state.last_error is None
    assert state.updated_at == 10.0


def test_properties_and_uuids_are_parsed_separately() -> None:
    properties = parse_bluez_properties(JBL_QUANTUM_360)
    uuids = parse_bluez_uuids(JBL_QUANTUM_360)

    assert properties == {
        "name": "JBL Quantum 360",
        "paired": True,
        "trusted": True,
        "connected": True,
    }
    assert uuids == frozenset({A2DP_AUDIO_SINK_UUID})


def test_unknown_information_is_not_reported_as_connected_or_audio_ready() -> None:
    state = BluetoothDeviceState(
        address="AA:BB:CC:DD:EE:04",
        name=None,
        discovered=None,
        paired=None,
        trusted=None,
        connected=None,
        audio_sink_capable=None,
        pulse_sink=None,
        last_error="information temporarily unavailable",
        updated_at=20.0,
    )

    assert state.discovered is None
    assert state.connected is None
    assert state.audio_sink_capable is None
    assert state.pulse_sink is None
    assert state.last_error is not None


@pytest.mark.parametrize("address", ["", "AA:BB:CC:DD:EE", "AA:BB:CC:DD:EE:GG"])
def test_bluetooth_address_validation_is_strict(address: str) -> None:
    with pytest.raises(ValueError):
        validate_bluetooth_address(address)


def test_state_mapping_contains_no_legacy_sink_claim() -> None:
    state = BluetoothDeviceState.from_bluez_info(
        BLE_NON_AUDIO.splitlines()[0].split()[1], BLE_NON_AUDIO
    )

    mapping = state.as_mapping()
    assert mapping["audio_sink_capable"] is False
    assert mapping["pulse_sink"] is None
    assert "sink_available" not in mapping
