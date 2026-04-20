"""Custom SpanProcessor to inject capture_trace_id onto every span.

Reads the capture_trace_id ContextVar (set by the capture handler at
request entry time and refreshed by the streaming adapter inside the
generator) and copies it as a span attribute.  This single mechanism
covers Sites 1 (AppRequests), 2 (Foundry agent spans), and 4
(investigation custom spans) without per-site code changes.
"""

from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Span

from second_brain.tools.classification import capture_trace_id_var


class CaptureTraceSpanProcessor(SpanProcessor):
    """Inject capture_trace_id from ContextVar onto every span.

    The ContextVar is set by the capture handler (api/capture.py) before
    returning the StreamingResponse, and refreshed by the adapter
    (streaming/adapter.py) inside the generator.  All spans created
    within that context -- including auto-instrumented Azure SDK spans --
    get the ``capture.trace_id`` attribute, which surfaces as a custom
    dimension in App Insights (Properties.capture_trace_id in KQL).
    """

    def on_start(self, span: Span, parent_context: object = None) -> None:
        trace_id = capture_trace_id_var.get("")
        if trace_id:
            span.set_attribute("capture.trace_id", trace_id)

    def on_end(self, span: "Span") -> None:
        pass  # No-op -- attribute injection happens in on_start

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
