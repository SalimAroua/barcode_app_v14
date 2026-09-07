from datetime import datetime, timezone

from app.domain.exceptions import TemplateError
from app.domain.validator import validate_scanned_barcode as _validate


def validate(scanned_value, receipt_def, scan_session=None, use_now=None):
    """Returns a ValidationResult. If the template itself is misconfigured
    (unknown placeholder, invalid regex, missing session field), that is
    surfaced as a TemplateError - a receipt-authoring bug, not a scan
    failure - so callers should let it propagate/report distinctly.
    """
    now = use_now or datetime.now(timezone.utc)
    return _validate(scanned_value, receipt_def, scan_session, now)
