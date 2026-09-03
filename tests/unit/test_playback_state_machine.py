from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from domain.models import PlaybackState
from domain.state_machine import (
    PlaybackEffect,
    PlaybackEvent,
    PlaybackStateMachine,
    TransitionNotAllowedError,
    TRANSITIONS,
)


_ALL_EVENTS = tuple(PlaybackEvent)


def test_transition_table_covers_all_states_and_declares_safe_effects() -> None:
    assert set(TRANSITIONS) == set(PlaybackState)
    for state, events in TRANSITIONS.items():
        for event, transition in events.items():
            assert transition.source is state
            assert transition.event is event
            assert transition.effects
            if transition.target is PlaybackState.ERROR:
                assert PlaybackEffect.SAFE_OUTPUTS in transition.effects


@pytest.mark.parametrize(
    "source, event",
    [
        (source, event)
        for source, events in TRANSITIONS.items()
        for event in events
    ],
    ids=lambda value: value.name if hasattr(value, "name") else str(value),
)
def test_every_declared_arc_is_executable(source, event) -> None:
    machine = PlaybackStateMachine(initial_state=source)
    result = machine.transition(event)
    assert result.transition.source is source
    assert machine.state is result.transition.target


@pytest.mark.parametrize(
    "source, event",
    [
        (source, event)
        for source in PlaybackState
        for event in _ALL_EVENTS
        if event not in TRANSITIONS[source]
    ],
    ids=lambda value: value.name if hasattr(value, "name") else str(value),
)
def test_every_undeclared_arc_is_rejected_without_mutation(source, event) -> None:
    machine = PlaybackStateMachine(initial_state=source)
    with pytest.raises(TransitionNotAllowedError):
        machine.transition(event)
    assert machine.state is source


@pytest.mark.parametrize(
    "events, expected",
    [
        (("start", "started"), PlaybackState.PLAYING),
        (("start", "started", "pause"), PlaybackState.PAUSED),
        (("start", "started", "pause", "resume"), PlaybackState.PLAYING),
        (("start", "started", "completed"), PlaybackState.IDLE),
        (("start", "stop", "stopped"), PlaybackState.IDLE),
        (("start", "started", "pause", "stop", "stopped"), PlaybackState.IDLE),
        (("start", "failed", "reset"), PlaybackState.IDLE),
    ],
)
def test_authorized_arcs(events: tuple[str, ...], expected: PlaybackState) -> None:
    machine = PlaybackStateMachine()
    results = [machine.transition(event) for event in events]
    assert machine.state is expected
    assert [result.sequence for result in results] == list(range(1, len(events) + 1))


@pytest.mark.parametrize(
    "events, forbidden",
    [
        ((), "pause"),
        (("start",), "resume"),
        (("start", "started"), "started"),
        (("start", "started", "pause"), "pause"),
        (("start", "started", "completed"), "resume"),
        (("start", "failed"), "resume"),
        (("start", "stop"), "started"),
    ],
)
def test_forbidden_transitions_do_not_change_state(
    events: tuple[str, ...], forbidden: str
) -> None:
    machine = PlaybackStateMachine()
    for event in events:
        machine.transition(event)
    before = machine.state
    with pytest.raises(TransitionNotAllowedError) as exc_info:
        machine.transition(forbidden)
    assert exc_info.value.state is before
    assert machine.state is before


def test_stop_is_idempotent_and_declares_safe_outputs() -> None:
    machine = PlaybackStateMachine()
    first = machine.transition("stop")
    second = machine.transition("stop")
    assert first.state is PlaybackState.IDLE
    assert second.state is PlaybackState.IDLE
    assert PlaybackEffect.SAFE_OUTPUTS in first.effects
    assert PlaybackEffect.SAFE_OUTPUTS in second.effects


def test_error_transition_declares_safe_outputs_and_publishes_error() -> None:
    machine = PlaybackStateMachine()
    machine.transition("start")
    result = machine.transition("failed")
    assert result.state is PlaybackState.ERROR
    assert PlaybackEffect.AUDIO_STOP in result.effects
    assert PlaybackEffect.TIMELINE_STOP in result.effects
    assert PlaybackEffect.SMOKE_STOP in result.effects
    assert PlaybackEffect.SAFE_OUTPUTS in result.effects
    assert PlaybackEffect.PUBLISH_STATE in result.effects


def test_concurrent_events_are_serialized_by_one_lock() -> None:
    machine = PlaybackStateMachine()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: machine.transition("stop"), range(32)))

    assert machine.state is PlaybackState.IDLE
    assert machine.sequence == 32
    assert sorted(result.sequence for result in results) == list(range(1, 33))
