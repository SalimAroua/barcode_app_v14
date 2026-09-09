"""
Tests for _render_label_output: the {{name}}-style substitution fix (was
previously broken - str.format_map treats {{ }} as escaped literal braces
and never substitutes them), verified against the actual uploaded
carte_identification_label.zpl, plus the existing single-brace fallback
path to confirm it didn't regress.

Run with: python test_label_rendering.py
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///test_label_rendering.db"

from types import SimpleNamespace  # noqa: E402
import app.services.scan_service as ss  # noqa: E402

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


# --- 1. The real uploaded template: {{name}} double-brace syntax ---
rd = SimpleNamespace(
    template_file_path="carte_identification_label.zpl",
    part_number="PN-12345",
    name="Carte identification",
    quantity_text="500",
)
session = SimpleNamespace(
    id=1, batch_label="26090712001", operator_number="OP1", line_number="LINE-12",
    plain_line_number="12", operators="Alice;Bob", target_quantity=500,
)

output_path = ss._render_label_output(session, rd)
rendered = open(output_path, encoding="utf-8").read()

check("REFERENCE placeholder is actually substituted (not left as {{REFERENCE}})",
      "{{REFERENCE}}" not in rendered and "PN-12345" in rendered)
check("QTE placeholder is actually substituted", "{{QTE}}" not in rendered and rendered.count("500") >= 1)
check("Unmapped per-step fields are left visibly marked, not silently blanked",
      "{{COUPEUR_NOM}}" in rendered)
check("Output is still valid-looking ZPL (starts with ^XA, ends with ^XZ)",
      rendered.strip().startswith("^XA") and rendered.strip().endswith("^XZ"))
check("No stray single braces left over from the old broken escaping ({REFERENCE})",
      "{REFERENCE}" not in rendered and "{QTE}" not in rendered)

os.remove(output_path)

# --- 2. REFERENCE prefers part_number, falls back to receipt name if blank ---
rd_no_part_number = SimpleNamespace(
    template_file_path="carte_identification_label.zpl",
    part_number=None, name="FallbackReceiptName", quantity_text=None,
)
session2 = SimpleNamespace(
    id=2, batch_label="X", operator_number="OP1", line_number="L1",
    plain_line_number="1", operators="", target_quantity=None,
)
output_path2 = ss._render_label_output(session2, rd_no_part_number)
rendered2 = open(output_path2, encoding="utf-8").read()
check("REFERENCE falls back to the receipt name when part_number is blank",
      "FallbackReceiptName" in rendered2)
os.remove(output_path2)

# --- 3. The built-in fallback template (no template_file_path) still works (single-brace syntax) ---
rd_no_template = SimpleNamespace(template_file_path=None, part_number="PN-X", name="X", quantity_text=None)
session3 = SimpleNamespace(
    id=3, batch_label="BATCH-3", operator_number="OP3", line_number="L3",
    plain_line_number="3", operators="", target_quantity=10,
)
output_path3 = ss._render_label_output(session3, rd_no_template)
rendered3 = open(output_path3, encoding="utf-8").read()
check("Fallback (no template file) still substitutes single-brace fields correctly",
      "BATCH-3" in rendered3 and "{batch_label}" not in rendered3)
os.remove(output_path3)

# --- 4. A missing template file path falls back gracefully (no crash) ---
rd_missing_file = SimpleNamespace(
    template_file_path="/no/such/file.zpl", part_number="PN-Y", name="Y", quantity_text=None,
)
session4 = SimpleNamespace(
    id=4, batch_label="BATCH-4", operator_number="OP4", line_number="L4",
    plain_line_number="4", operators="", target_quantity=None,
)
output_path4 = ss._render_label_output(session4, rd_missing_file)
rendered4 = open(output_path4, encoding="utf-8").read()
check("A missing template file path falls back to the built-in template instead of crashing",
      "BATCH-4" in rendered4)
os.remove(output_path4)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")
