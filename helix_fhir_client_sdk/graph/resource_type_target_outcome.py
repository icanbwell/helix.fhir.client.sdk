from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class ResourceTypeTargetOutcome:
    """
    The outcome of one declared target type within a GraphDefinition link,
    carried on ResourceTypeCompletionEvent.target_outcomes. A link can
    declare several target types; this reports each one on its own, so a
    target that was denied or not found is not hidden by a sibling target
    that succeeded.
    """

    resource_type: str
    """The declared target type this outcome is for."""

    resource_count: int
    """Total resource count across the successful FhirGetResponse chunks this
    target retrieved. Unlike ResourceTypeCompletionEvent.resource_count,
    unsuccessful responses are left out, so a not_found target reports 0
    rather than counting its 404's OperationOutcome body."""

    outcome: Literal["success", "empty", "not_found", "scope_denied", "error"]
    """Same values and precedence as ResourceTypeCompletionEvent.outcome,
    applied to this target's responses alone. "scope_denied" means the auth
    scope disallowed this target type. A link-level failure (the link's
    fetch raised) is "error" for every target, since it can't be pinned on
    one of them."""

    error_type: str | None
    """Same as ResourceTypeCompletionEvent.error_type, for this target."""

    error_message: str | None
    """Same as ResourceTypeCompletionEvent.error_message, for this target."""
