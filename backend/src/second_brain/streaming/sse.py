"""SSE encoding helper and AG-UI event constructors.

Produces `data: {json}\\n\\n` formatted strings for the react-native-sse
EventSource client. No `event:` field -- the client listens for the default
"message" event type.

Event type names follow the Phase 8 contract:
  STEP_START, STEP_END, CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR
"""

import json


def encode_sse(data: dict) -> str:
    """Format a dict as an SSE data event.

    The mobile react-native-sse EventSource listens for the default
    'message' event type. No 'event:' field is needed.
    """
    return f"data: {json.dumps(data)}\n\n"


def step_start_event(step_name: str) -> dict:
    """Construct a STEP_START event payload."""
    return {"type": "STEP_START", "stepName": step_name}


def step_end_event(step_name: str) -> dict:
    """Construct a STEP_END event payload."""
    return {"type": "STEP_END", "stepName": step_name}


def classified_event(inbox_item_id: str, bucket: str, confidence: float) -> dict:
    """Construct a CLASSIFIED event payload."""
    return {
        "type": "CLASSIFIED",
        "value": {
            "inboxItemId": inbox_item_id,
            "bucket": bucket,
            "confidence": confidence,
        },
    }


def misunderstood_event(thread_id: str, inbox_item_id: str, question_text: str) -> dict:
    """Construct a MISUNDERSTOOD event payload."""
    return {
        "type": "MISUNDERSTOOD",
        "value": {
            "threadId": thread_id,
            "inboxItemId": inbox_item_id,
            "questionText": question_text,
        },
    }


def unresolved_event(inbox_item_id: str) -> dict:
    """Construct an UNRESOLVED event payload."""
    return {
        "type": "UNRESOLVED",
        "value": {
            "inboxItemId": inbox_item_id,
        },
    }


def complete_event(thread_id: str, run_id: str) -> dict:
    """Construct a COMPLETE event payload."""
    return {
        "type": "COMPLETE",
        "threadId": thread_id,
        "runId": run_id,
    }


def error_event(message: str) -> dict:
    """Construct an ERROR event payload."""
    return {
        "type": "ERROR",
        "message": message,
    }
