"""Fixed, non-sensitive operational failure codes."""


class OpsError(RuntimeError):
    """원문을 포함하지 않는 고정 진단 코드."""


class BudgetExhausted(RuntimeError):
    """The fixed collection session budget has no remaining request."""


class TransportError(RuntimeError):
    """A network request failed; credentials and response bodies are not exposed."""


class SemanticConformanceError(RuntimeError):
    """A conformance failure may carry a safe, publishable diagnostic read model."""

    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report
