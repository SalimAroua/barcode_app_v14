# Packaging as a standalone Windows app

This turns the app into a folder you can copy to any Windows machine and
run without installing Python. Building has to happen **on Windows** -
PyInstaller packages for the OS it runs on, it can't cross-compile a
Windows build from Linux/Mac.

## One-time setup (on the Windows machine that will build it)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

## Build

```powershell
pyinstaller main.spec
```

This produces `dist\BarcodePlaceholderApp\` - a folder containing
`BarcodePlaceholderApp.exe` plus everything it needs. **Copy the whole
folder**, not just the .exe - the app won't run without the files
alongside it (this is a "one-folder" build, not a single-file .exe; see
"Why one-folder, not one-file" below).

## Running it

Double-click `BarcodePlaceholderApp.exe` inside that folder. First run
creates `barcode.db` right next to the .exe and seeds the default
SuperUser (`admin` / `admin123`, unless you set
`SEED_SUPERUSER_USERNAME`/`SEED_SUPERUSER_PASSWORD` env vars before first
run) - same as running `python main.py` from source.

The database always lives next to the .exe itself, regardless of which
folder you launch it from (double-click, desktop shortcut, a shortcut
with a different "Start in" folder, etc. all work the same way) - this
was specifically fixed in `config.py` rather than left to depend on the
current working directory.

### Zebra printer setup

Zebra printers can receive raw ZPL over TCP port 9100. Configure the
shop-floor printer before starting the application:

```powershell
$env:ZEBRA_PRINTER_HOST = "192.168.1.50"
$env:ZEBRA_PRINTER_PORT = "9100"
$env:ZEBRA_PRINTER_TIMEOUT = "5"
```

Receipt label templates should be ZPL files containing the supported fields
`{batch_label}`, `{receipt_name}`, `{operator_number}`, `{line_number}`, and
`{target_quantity}`. When the target is reached, the app writes the rendered
`.zpl` artifact and sends the same bytes directly to the Zebra printer. If
`ZEBRA_PRINTER_HOST` is empty, no network connection is attempted and the
`.zpl` artifact is retained for offline testing.

The Admin dashboard includes **Zebra Printer Settings**, where the printer
mode can be selected without editing environment variables:

- **Network printer (TCP):** enter the printer IP/hostname, port, and timeout.
- **USB printer (Windows spooler):** install the Zebra printer in Windows,
  install `requirements-windows.txt`, select its Windows printer name, and
  use **Send Test Label**.

For USB mode, the installed Zebra driver must accept RAW printer data. The
application sends ZPL directly through the Windows spooler; it does not use
the Windows print-rendering pipeline.

## Deploying to other machines

Zip up `dist\BarcodePlaceholderApp\` and copy it to another Windows PC -
no Python installation needed there. Keep `barcode.db` if you want to
carry existing data over; delete it if you want that machine to start
fresh.

## Updating to a new version

1. Build the new version into a fresh `dist\BarcodePlaceholderApp\`.
2. Copy the **old** `barcode.db` into the new folder (overwriting the
   fresh one PyInstaller/first-run would create).
3. Run it. `run_migrations_to_head()` runs automatically on startup and
   brings the database schema up to date - this is exactly what Alembic
   migrations are for (see the "Alembic migrations" section of the main
   project docs).

## Why one-folder, not one-file

PyInstaller can also build a single `.exe` that contains everything
zipped inside it (`--onefile`). That's convenient to hand someone, but
it's a bad fit here specifically because of Alembic: `env.py` and every
migration script under `migrations/versions/` are loaded by Alembic
directly from disk at runtime (not through Python's normal `import`
system), and a one-file build only extracts its bundled contents to a
**temporary** folder that's deleted after the process exits. That extra
extraction step also means antivirus software flags one-file PyInstaller
builds far more often than one-folder builds. One-folder avoids both
problems: the files Alembic needs are just sitting there on disk,
permanently, next to the .exe.

## What's bundled and why (`main.spec`)

- `alembic.ini` and the whole `migrations/` folder are included as real,
  uncompressed files (not compiled into the app's bundled Python
  archive) - required because Alembic reads them from disk by path.
- `logging.config` is explicitly listed as a hidden import. This one is
  easy to miss: PyInstaller decides what to bundle by statically
  analyzing which modules your code imports, but `migrations/env.py`
  isn't `import`-ed anywhere - Alembic loads it dynamically at runtime as
  a data file. Its own import of `logging.config` is therefore invisible
  to PyInstaller's analysis and has to be listed by hand, or the packaged
  app crashes on first launch with `ModuleNotFoundError: No module named
  'logging.config'`. (Caught by actually building and running the app
  during development, not by reading the code.)
- `PySide6` is deliberately **not** run through `collect_all()`. It
  already ships its own official PyInstaller hooks (visible in the build
  log as `Processing standard module hook 'hook-PySide6.*.py'`), so
  `collect_all()` is redundant there - and on a real Windows build it
  turned out actively harmful: `collect_all()`'s submodule-enumeration
  step works by actually importing every submodule in an isolated
  subprocess, which for a package as large as PySide6 means fully
  bootstrapping Qt/shiboken just to build a module list. That crashed
  outright (`libshiboken/signature: could not initialize part 2`) in
  testing. Fixed by dropping PySide6 from the `collect_all()` loop
  entirely and trusting its built-in hooks, which is also what the
  official PySide6 + PyInstaller docs recommend.
- `alembic` **is** run through `collect_all()`, since it doesn't ship a
  dedicated PyInstaller hook of its own.

## Validated so far

This `main.spec` was built and run end-to-end as a Linux binary (the same
PyInstaller mechanics apply cross-platform - bundling data files, hidden
imports, frozen path handling - only the OS-specific binaries differ, and
pip/PyInstaller already resolve those correctly per platform):
- Builds cleanly with no errors
- Boots, runs migrations, creates `barcode.db` next to the executable
  (not the working directory it was launched from), and seeds the
  default SuperUser
- A second launch is a clean no-op (already-migrated, already-seeded)
- Launching from a completely unrelated working directory still finds
  its files and writes the database in the right place

**A real Windows build was also attempted** and hit one real, Windows-specific
issue: `collect_all("PySide6")` crashed during the build itself (not at
runtime) with `libshiboken/signature: could not initialize part 2`. See
"What's bundled and why" above for the cause and fix - dropping PySide6
from `collect_all()` and relying on its own built-in hooks instead. That
fix was re-validated with another full Linux build + run afterward, but
the Windows build itself hasn't been re-attempted with the fix yet.

**Still to confirm on Windows:** that `pyinstaller main.spec` completes
without the shiboken crash now that PySide6 is out of `collect_all()`,
and that the resulting `.exe` launches and renders correctly.
