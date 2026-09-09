"""Focused tests for concrete ZPL placeholder rendering."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.scan_service import _render_label_output


def test_operator_and_step_placeholders(tmp_path):
    zpl = """^XA
^FO10,10^FD{{REFERENCE}}^FS
^FO10,40^FD{{QTE}}^FS
^FO10,70^FD{{COUPEUR_NOM}} / {{COUPEUR_DATE}}^FS
^FO10,100^FD{{GL_COUPE_NOM}} / {{GL_COUPE_DATE}}^FS
^FO10,130^FD{{INSERTION_FILS_NOM}} / {{INSERTION_FILS_DATE}}^FS
^FO10,160^FD{{ENRUBANAGE_NOM}} / {{ENRUBANAGE_DATE}}^FS
^FO10,190^FD{{EOL_NOM}} / {{EOL_DATE}}^FS
^FO10,220^FD{{INSERTION_CLIPS_NOM}} / {{INSERTION_CLIPS_DATE}}^FS
^FO10,250^FD{{GL_ASSEMBLAGE_NOM}} / {{GL_ASSEMBLAGE_DATE}}^FS
^FO10,280^FD{{OPERATOR_8_NOM}} / {{OPERATOR_10_DATE}}^FS
^XZ"""
    template = tmp_path / "label.zpl"
    template.write_text(zpl, encoding="utf-8")

    receipt = SimpleNamespace(
        template_file_path=str(template),
        name="R1",
        part_number="PN-12345",
        quantity_text="500",
    )
    session = SimpleNamespace(
        id=1,
        batch_label="26090901001",
        operator_number="Alice",
        operators="Alice; Bob; Carol; Dan; Eva; Frank; Grace; Henry; Irene; Jack",
        line_number="L01",
        plain_line_number="01",
        target_quantity=500,
        started_at=datetime(2026, 9, 9, 8, 30, tzinfo=timezone.utc),
    )

    output = Path(_render_label_output(session, receipt)).read_text(encoding="utf-8")
    assert "PN-12345" in output
    assert "500" in output
    assert "Alice / 09/09/2026" in output
    assert "Bob / 09/09/2026" in output
    assert "Grace / 09/09/2026" in output
    assert "Henry / 09/09/2026" in output
    assert "Jack / 09/09/2026" in output
    assert "{{COUPEUR_NOM}}" not in output


def test_unknown_double_brace_placeholder_is_preserved(tmp_path):
    template = tmp_path / "label.zpl"
    template.write_text("^XA^FD{{UNKNOWN}}^FS^XZ", encoding="utf-8")
    receipt = SimpleNamespace(template_file_path=str(template), name="R", part_number="PN", quantity_text="1")
    session = SimpleNamespace(
        id=2, batch_label="B", operator_number="A", operators="A", line_number="L",
        plain_line_number="L", target_quantity=1,
        started_at=datetime.now(timezone.utc),
    )
    output = Path(_render_label_output(session, receipt)).read_text(encoding="utf-8")
    assert "{{UNKNOWN}}" in output
