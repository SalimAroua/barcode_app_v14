import json
import os
import socket

import config
from app.domain.exceptions import PrinterError


DEFAULT_SETTINGS = {
    "mode": "network",
    "host": config.ZEBRA_PRINTER_HOST,
    "port": config.ZEBRA_PRINTER_PORT,
    "timeout": config.ZEBRA_PRINTER_TIMEOUT,
    "usb_printer_name": "",
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(config.PRINTER_SETTINGS_PATH):
        try:
            with open(config.PRINTER_SETTINGS_PATH, "r", encoding="utf-8") as settings_file:
                saved = json.load(settings_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise PrinterError(
                "Printer settings could not be read. Open Zebra Printer Settings and save them again."
            ) from exc
        if not isinstance(saved, dict):
            raise PrinterError("Printer settings are invalid. Open Zebra Printer Settings and save them again.")
        settings.update(saved)
    if settings.get("mode") not in ("network", "usb"):
        raise PrinterError("Printer mode is invalid. Choose Network or USB in Zebra Printer Settings.")
    return settings


def save_settings(settings):
    normalized = dict(DEFAULT_SETTINGS)
    normalized.update(settings)
    normalized["port"] = int(normalized["port"])
    normalized["timeout"] = float(normalized["timeout"])
    with open(config.PRINTER_SETTINGS_PATH, "w", encoding="utf-8") as settings_file:
        json.dump(normalized, settings_file, indent=2)


def list_usb_printers():
    try:
        import win32print
    except ImportError:
        return []

    try:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return sorted({item[2] for item in win32print.EnumPrinters(flags)})
    except Exception:
        return []


def send_zpl(zpl_bytes, settings=None):
    try:
        settings_file_exists = os.path.exists(config.PRINTER_SETTINGS_PATH)
        settings = settings or load_settings()
        if settings["mode"] == "usb":
            return _send_usb(zpl_bytes, settings["usb_printer_name"])

        host = str(settings.get("host", "")).strip()
        if not host:
            if not settings_file_exists and not config.ZEBRA_PRINTER_HOST:
                return False
            raise PrinterError("No Zebra printer host is configured. Open Zebra Printer Settings.")
        with socket.create_connection(
            (host, int(settings["port"])),
            timeout=float(settings["timeout"]),
        ) as printer:
            printer.sendall(zpl_bytes)
        return True
    except PrinterError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise PrinterError(f"Could not send the label to the Zebra printer: {exc}") from exc


def _send_usb(zpl_bytes, printer_name):
    if not printer_name:
        raise PrinterError("No USB printer is selected. Open Zebra Printer Settings and select one.")
    try:
        import win32print
    except ImportError as exc:
        raise PrinterError(
            "USB printing is unavailable because pywin32 is not installed. "
            "Install requirements-windows.txt and restart the app."
        ) from exc

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        raise PrinterError(
            f"Windows could not open printer '{printer_name}'. Check that it is installed and online."
        ) from exc
    try:
        try:
            win32print.StartDocPrinter(handle, 1, ("Barcode label", None, "RAW"))
        except Exception as exc:
            raise PrinterError(f"Could not start a RAW print job on '{printer_name}'.") from exc
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, zpl_bytes)
            win32print.EndPagePrinter(handle)
        except Exception as exc:
            raise PrinterError(f"Could not send ZPL data to '{printer_name}'.") from exc
        finally:
            try:
                win32print.EndDocPrinter(handle)
            except Exception as exc:
                raise PrinterError(f"Could not finish the print job on '{printer_name}'.") from exc
    finally:
        win32print.ClosePrinter(handle)
    return True