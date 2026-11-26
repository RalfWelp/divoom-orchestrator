"""Administrator-only management of the pixelart directory."""

import ctypes
import errno
import os
from pathlib import Path
import shutil
import sys
import sysconfig
from contextlib import AsyncExitStack

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "divoom_orchestrator"


def _name(name: str) -> str:
    if (not name or name != name.strip() or name in (".", "..")
            or any(char in '/\\<>:"|?*' or ord(char) < 32 for char in name)):
        raise ValueError("Ungültiger Ordnername")
    return name


def _path(root: Path, value: str, *, directory: bool) -> tuple[Path, Path]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    relative = Path(value)
    if not value or "\\" in value or relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError("Pfad muss innerhalb von pixelart liegen")
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
            raise ValueError("Symbolische Links können nicht verwaltet werden")
    target = target.resolve(strict=True)
    if not target.is_relative_to(root):
        raise ValueError("Pfad muss innerhalb von pixelart liegen")
    if directory and not target.is_dir():
        raise NotADirectoryError(str(target))
    if not directory and (not target.is_file() or target.suffix.lower() != ".gif"):
        raise ValueError("Die Datei ist kein vorhandenes GIF")
    return root, target


def _no_links(directory: Path) -> None:
    def fail(error):
        raise error

    for current, dirs, files in os.walk(directory, followlinks=False, onerror=fail):
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("Ordner mit symbolischen Links können nicht verwaltet werden")


def create(root: Path, parent: str, name: str) -> str:
    root, directory = _path(root, parent, directory=True)
    target = directory / _name(name)
    target.mkdir()
    return target.relative_to(root).as_posix()


def duplicate(root: Path, source: str, parent: str, name: str) -> str:
    root, directory = _path(root, source, directory=True)
    _, destination = _path(root, parent, directory=True)
    if directory == root:
        raise ValueError("Der pixelart-Hauptordner kann nicht dupliziert werden")
    if destination == directory or destination.is_relative_to(directory):
        raise ValueError("Ein Ordner kann nicht in sich selbst dupliziert werden")
    _no_links(directory)
    target = destination / _name(name)
    target.mkdir()
    try:
        shutil.copytree(directory, target, dirs_exist_ok=True)
    except (OSError, shutil.Error):
        try:
            shutil.rmtree(target)
        except OSError as cleanup_error:
            raise OSError(f"Kopie fehlgeschlagen; unvollständiger Ordner {target.name} konnte nicht entfernt werden: {cleanup_error}") from cleanup_error
        raise
    return target.relative_to(root).as_posix()


def _rename_no_replace(source: Path, target: Path) -> None:
    if sys.platform == "win32":
        os.rename(source, target)
        return
    if sys.platform != "linux":
        raise OSError("Sicheres Verschieben ohne Überschreiben wird auf diesem System nicht unterstützt")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is not None:
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    else:
        # musl may not expose renameat2; use the Linux ABI only for known architectures.
        calls = {
            "linux-x86_64": (316, 8), "linux-aarch64": (276, 8),
            "linux-armv7l": (382, 4), "linux-armv6l": (382, 4),
            "linux-i686": (353, 4), "linux-i386": (353, 4),
        }
        spec = calls.get(sysconfig.get_platform())
        if spec is None or ctypes.sizeof(ctypes.c_void_p) != spec[1]:
            raise OSError("Sicheres Verschieben ohne Überschreiben ist für diese Architektur nicht verfügbar")
        syscall = libc.syscall
        syscall.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                            ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        syscall.restype = ctypes.c_long
        result = syscall(spec[0], -100, os.fsencode(source), -100, os.fsencode(target), 1)
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, "Im Ziel existiert bereits ein Eintrag mit diesem Namen", str(target))
        raise OSError(error, os.strerror(error), str(source))


def move(root: Path, source: str, parent: str, kind: str) -> str:
    root, item = _path(root, source, directory=kind == "folder")
    _, destination = _path(root, parent, directory=True)
    if item == root:
        raise ValueError("Der pixelart-Hauptordner kann nicht verschoben werden")
    if kind == "folder":
        if destination == item or destination.is_relative_to(item):
            raise ValueError("Ein Ordner kann nicht in sich selbst verschoben werden")
        _no_links(item)
    target = destination / item.name
    if target == item:
        raise FileExistsError("Der Eintrag befindet sich bereits im Zielordner")
    _rename_no_replace(item, target)
    return target.relative_to(root).as_posix()


def delete(root: Path, source: str, kind: str) -> None:
    root, item = _path(root, source, directory=kind == "folder")
    if item == root:
        raise ValueError("Der pixelart-Hauptordner kann nicht gelöscht werden")
    if kind == "folder":
        _no_links(item)
        shutil.rmtree(item)
    else:
        item.unlink()


def _contains(parent: str, child: str) -> bool:
    return Path(child).is_relative_to(Path(parent))


def references(data: dict, source: str, kind: str) -> list[str]:
    """Find saved and dynamic uses that would be broken by a mutation."""
    used = []
    events = data["events"].events
    rotation = data["rotation"].config
    for name, event in events.items():
        if ((kind == "folder" and _contains(source, event["folder"]))
                or any((kind == "folder" and _contains(source, step["file"])) or Path(step["file"]) == Path(source)
                       for step in event["steps"])):
            used.append(f"Event: {name}")
    if rotation and ((kind == "folder" and _contains(source, rotation["folder"]))
                     or any((kind == "folder" and _contains(source, step["file"])) or Path(step["file"]) == Path(source)
                            for step in rotation["steps"])):
        used.append("Rotation: Startanimation")
    if any((kind == "folder" and _contains(source, filename)) or Path(filename) == Path(source)
           for filename in data["durations"].values):
        used.append("gespeicherte Playlist-Anzeigezeiten")
    fallbacks = ("fehler/start.gif", "fehler/datum.gif", "fehler/wetter.gif", "fehler/trigger.gif", "fehler/text.gif")
    if any((kind == "folder" and _contains(source, filename)) or Path(filename) == Path(source) for filename in fallbacks):
        used.append("Fehlerbilder der Rotation und Events")
    if rotation and "weather" in rotation.get("blocks", []) and "weather" not in rotation.get("inactive_blocks", []):
        if ((kind == "folder" and (_contains(source, "wetter") or _contains("wetter", source)))
                or (kind == "gif" and _contains("wetter", source))):
            used.append("Wetterrotation")
    return used


def _runtime(hass):
    data = hass.data[DOMAIN]
    if any(data.get(key) is None for key in ("events", "rotation", "durations", "controller")):
        raise HomeAssistantError("Integration ist nicht geladen")
    return data


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/media_create",
    vol.Required("parent"): str,
    vol.Required("name"): str,
})
@websocket_api.async_response
async def websocket_create(hass, connection, msg):
    try:
        data = _runtime(hass)
        result = await hass.async_add_executor_job(create, data["events"].root, msg["parent"], msg["name"])
        connection.send_result(msg["id"], result)
    except (OSError, ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "media_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/media_duplicate",
    vol.Required("source"): str,
    vol.Required("parent"): str,
    vol.Required("name"): str,
})
@websocket_api.async_response
async def websocket_duplicate(hass, connection, msg):
    try:
        data = _runtime(hass)
        async with data["rotation"]._lock:
            result = await hass.async_add_executor_job(
                duplicate, data["events"].root, msg["source"], msg["parent"], msg["name"]
            )
        connection.send_result(msg["id"], result)
    except (OSError, ValueError, shutil.Error, HomeAssistantError) as err:
        connection.send_error(msg["id"], "media_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/media_mutate",
    vol.Required("action"): vol.In(["move", "delete"]),
    vol.Required("kind"): vol.In(["folder", "gif"]),
    vol.Required("source"): str,
    vol.Optional("parent"): str,
})
@websocket_api.async_response
async def websocket_mutate(hass, connection, msg):
    try:
        data = _runtime(hass)
        async with AsyncExitStack() as stack:
            for key in ("rotation", "events", "durations", "controller"):
                await stack.enter_async_context(data[key]._lock)
            if data["controller"].running:
                raise ValueError("Bitte zuerst die laufende Rotation oder Playlist stoppen")
            root, item = await hass.async_add_executor_job(
                lambda: _path(data["events"].root, msg["source"], directory=msg["kind"] == "folder")
            )
            source = item.relative_to(root).as_posix()
            used = references(data, source, msg["kind"])
            if used:
                raise ValueError("Wird verwendet von: " + ", ".join(used))
            if msg["action"] == "move":
                if "parent" not in msg:
                    raise ValueError("Zielordner fehlt")
                result = await hass.async_add_executor_job(move, root, source, msg["parent"], msg["kind"])
            else:
                await hass.async_add_executor_job(delete, root, source, msg["kind"])
                result = None
        connection.send_result(msg["id"], result)
    except (OSError, ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "media_error", str(err))


def register(hass):
    for command in (websocket_create, websocket_duplicate, websocket_mutate):
        websocket_api.async_register_command(hass, command)
