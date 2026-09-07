"""
Unit tests for the "frozen app" path-resolution logic in config.py and
migrations_runner.py, without needing an actual ~5-minute PyInstaller
build to check it. (test_packaging_build.py, if you run it, does the full
real build as an end-to-end check; this file is the fast version for
everyday runs.)

Run with: python test_packaging_paths.py
"""
import importlib.util
import os
import sys


results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


def load_fresh_module(path, name):
    """Load a fresh instance of a module from a file path, bypassing
    sys.modules caching, so re-importing after changing sys.frozen
    actually re-runs the module's top-level code."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- 1. config.py: not frozen -> default DB path is next to config.py itself ---
if hasattr(sys, "frozen"):
    del sys.frozen  # shouldn't be set in a normal test run, but just in case

config_normal = load_fresh_module(os.path.join(PROJECT_ROOT, "config.py"), "config_normal_test")
expected_normal_db = os.path.join(PROJECT_ROOT, "barcode.db")
check(
    "Non-frozen: default DB path is next to config.py (source layout)",
    config_normal.DATABASE_URL == f"sqlite:///{expected_normal_db}",
)

# --- 2. config.py: frozen -> default DB path is next to sys.executable ---
fake_exe_dir = "/fake/dist/BarcodePlaceholderApp"
original_executable = sys.executable
sys.frozen = True
sys.executable = os.path.join(fake_exe_dir, "BarcodePlaceholderApp.exe")
try:
    config_frozen = load_fresh_module(os.path.join(PROJECT_ROOT, "config.py"), "config_frozen_test")
    expected_frozen_db = os.path.join(fake_exe_dir, "barcode.db")
    check(
        "Frozen: default DB path is next to the .exe, not the working directory",
        config_frozen.DATABASE_URL == f"sqlite:///{expected_frozen_db}",
    )
finally:
    del sys.frozen
    sys.executable = original_executable

# --- 3. config.py: DATABASE_URL env var override still wins in both cases ---
os.environ["DATABASE_URL"] = "sqlite:///explicit_override.db"
try:
    config_override = load_fresh_module(os.path.join(PROJECT_ROOT, "config.py"), "config_override_test")
    check("Explicit DATABASE_URL env var overrides the computed default",
          config_override.DATABASE_URL == "sqlite:///explicit_override.db")
finally:
    del os.environ["DATABASE_URL"]

# --- 4. migrations_runner.py: not frozen -> bundle root is this file's own directory ---
mr_normal = load_fresh_module(os.path.join(PROJECT_ROOT, "migrations_runner.py"), "mr_normal_test")
check(
    "Non-frozen: migrations/alembic.ini resolved relative to the source tree",
    mr_normal._PROJECT_ROOT == PROJECT_ROOT and os.path.isfile(mr_normal._ALEMBIC_INI),
)

# --- 5. migrations_runner.py: frozen -> bundle root is sys._MEIPASS, NOT __file__ ---
fake_meipass = "/fake/_MEIPASS_extraction_dir"
sys.frozen = True
sys._MEIPASS = fake_meipass
try:
    mr_frozen = load_fresh_module(os.path.join(PROJECT_ROOT, "migrations_runner.py"), "mr_frozen_test")
    check(
        "Frozen: migrations/alembic.ini resolved relative to sys._MEIPASS, not __file__",
        mr_frozen._PROJECT_ROOT == fake_meipass
        and mr_frozen._ALEMBIC_INI == os.path.join(fake_meipass, "alembic.ini"),
    )
finally:
    del sys.frozen
    del sys._MEIPASS

# --- 6. main.spec actually bundles alembic.ini and migrations/ as datas ---
spec_text = open(os.path.join(PROJECT_ROOT, "main.spec")).read()
check("main.spec bundles alembic.ini as a data file", '"alembic.ini"' in spec_text)
check("main.spec bundles the migrations/ folder as data files", '"migrations"' in spec_text)
check("main.spec hidden-imports logging.config (env.py's invisible-to-PyInstaller import)",
      "logging.config" in spec_text)
check("main.spec does NOT run PySide6 through collect_all (crashed on Windows - see comments)",
      'for pkg in ("alembic",):' in spec_text)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")
