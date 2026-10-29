"""Human workflow state is independent of the REVIEW signal verdict."""

from .errors import OpsError

REVIEW_STATES = ("OPEN", "IN_REVIEW", "COMPLETED")
TRANSITIONS = {
    "start": ("OPEN", "IN_REVIEW"),
    "complete": ("IN_REVIEW", "COMPLETED"),
    "reopen": ("COMPLETED", "OPEN"),
}


def validate_command(action, operator, note):
    if action not in {*TRANSITIONS, "note"}:
        raise OpsError("REVIEW_ACTION")
    if not isinstance(operator, str) or not operator.strip():
        raise OpsError("REVIEW_OPERATOR_REQUIRED")
    if action == "note" and (not isinstance(note, str) or not note.strip()):
        raise OpsError("REVIEW_NOTE_REQUIRED")
    if action != "note" and note is not None:
        raise OpsError("REVIEW_UNEXPECTED_NOTE")
    return operator.strip(), note.strip() if note is not None else None


def next_state(action, previous):
    if action == "note":
        return previous
    required, result = TRANSITIONS[action]
    if previous != required:
        raise OpsError("REVIEW_INVALID_TRANSITION")
    return result
