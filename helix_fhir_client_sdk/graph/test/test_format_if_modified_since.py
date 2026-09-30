from datetime import UTC, datetime, timedelta, timezone

from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)

_format = SimulatedGraphProcessorMixin._format_if_modified_since


def test_emits_an_explicit_time_component() -> None:
    """Cerner rejects a bare date on Encounter/Procedure searches with
    "date: must have a time" (DCON-5571), so the value must carry a time."""
    assert _format(datetime(2026, 9, 14, 8, 31, 14, 812000, tzinfo=UTC)) == "2026-09-14T00:00:00.000Z"


def test_pinned_to_midnight_so_the_search_window_is_never_narrowed() -> None:
    """The time is pinned to midnight rather than the value's own time. Using
    the exact last-run instant would narrow the window and skip records whose
    clinical date falls earlier the same day."""
    early = _format(datetime(2026, 9, 14, 0, 0, 1, tzinfo=UTC))
    late = _format(datetime(2026, 9, 14, 23, 59, 59, tzinfo=UTC))
    assert early == late == "2026-09-14T00:00:00.000Z"


def test_naive_datetime_is_treated_as_utc() -> None:
    assert _format(datetime(2026, 9, 14, 8, 31, 14)) == "2026-09-14T00:00:00.000Z"


def test_aware_datetime_is_converted_to_utc_before_truncating() -> None:
    """A non-UTC value must be converted first, since the conversion can move
    it onto a different calendar day."""
    # 2026-09-14T20:00-08:00 is 2026-09-15T04:00Z, so the UTC date is the 15th
    pacific = timezone(timedelta(hours=-8))
    assert _format(datetime(2026, 9, 14, 20, 0, 0, tzinfo=pacific)) == "2026-09-15T00:00:00.000Z"


def test_colons_are_left_literal() -> None:
    """Oracle's documented examples use literal colons; percent-encoding them
    is legal but needlessly relies on the server decoding it."""
    assert "%3A" not in _format(datetime(2026, 9, 14, tzinfo=UTC))


def test_result_is_safe_to_substitute_into_a_graph_param() -> None:
    """The emitted value lands in params like "patient={ref}&date=ge{ifModifiedSince}",
    so it must not introduce characters that would split the query string."""
    formatted = _format(datetime(2026, 9, 14, tzinfo=UTC))
    assert "&" not in formatted
    assert "=" not in formatted
    assert f"patient=Patient/1&date=ge{formatted}" == ("patient=Patient/1&date=ge2026-09-14T00:00:00.000Z")
