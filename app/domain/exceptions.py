class TemplateError(Exception):
    """Raised when a ReceiptDefinition's template can't be compiled at all
    (bad config) - as opposed to a scan simply failing validation."""


class MissingSessionFieldError(TemplateError):
    """A placeholder needs a ScanSession (LineNumber, OpNumber, ...) but
    none was provided."""


class UnknownPlaceholderError(TemplateError):
    """A placeholder name in template_tokens isn't recognized."""


class InvalidRegexTokenError(TemplateError):
    """A regex-mode token's pattern doesn't compile."""


class IncompletePairError(Exception):
    """A second primary scan was attempted before the open unit's
    companion label was scanned."""
