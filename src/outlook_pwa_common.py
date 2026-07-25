"""Shared configuration and desktop integration for Outlook PWA Linux."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

VERSION = "0.3.0"
APP_ID = "faolnafnngnfdaknnbpnkhgohbobgegn"
EXTENSION_ID = "mfjjkdjhfcbabopnjmjapphchleaglcp"
EXTENSION_HOST = "com.outlook_pwa_linux.link_router"
MAIL_URL = "https://outlook.office.com/mail/"
CALENDAR_URL = "https://outlook.office.com/calendar/view/month"
COMPOSE_URL = "https://outlook.office.com/mail/deeplink/compose"
NEW_EVENT_URL = "https://outlook.office.com/calendar/deeplink/compose"
POLICY_PATH = Path("/etc/opt/edge/policies/managed/outlook-pwa-linux.json")
NATIVE_HOST_PATH = Path(
    "/etc/opt/edge/native-messaging-hosts/com.outlook_pwa_linux.link_router.json"
)
SYSTEM_ICON_NAME = "outlook-pwa-linux"
ICON_SIZES = (16, 32, 48, 64, 128, 256)

DEFAULT_INTERNAL_DOMAINS = [
    "outlook.office.com",
    "outlook.live.com",
    "office.com",
    "office365.com",
    "microsoft365.com",
    "login.microsoftonline.com",
    "login.live.com",
    "microsoft.com",
    "sharepoint.com",
    "onedrive.live.com",
    "officeapps.live.com",
]


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"


def data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".local" / "share"
    )


def app_config_dir() -> Path:
    return config_home() / "outlook-pwa-linux"


def settings_path() -> Path:
    return app_config_dir() / "settings.json"


def user_data_dir() -> Path:
    return app_config_dir() / "edge-profile"


def application_dir() -> Path:
    return data_home() / "applications"


def resource_root() -> Path:
    overridden = os.environ.get("OUTLOOK_PWA_RESOURCE_ROOT")
    if overridden:
        return Path(overridden)
    source = Path(__file__).resolve().parents[1]
    if (source / "extension").is_dir() and (source / "assets").is_dir():
        return source
    installed = Path("/usr/share/outlook-pwa-linux")
    if installed.is_dir():
        return installed
    return source


def default_settings() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "default_profile": "default",
        "autostart": False,
        "mailto_handler": True,
        "route_external_links": True,
        "titlebar_style": "outlook",
        "titlebar_color": "#0f6cbd",
        "internal_domains": list(DEFAULT_INTERNAL_DOMAINS),
        "profiles": {
            "default": {
                "name": "Outlook",
                "edge_profile": "Default",
                "start_view": "mail",
                "download_directory": str(Path.home() / "Downloads"),
                "ask_download": True,
                "focus_mode": False,
                "custom_icon": "",
            }
        },
    }


def _normalize_profile(profile_id: str, profile: object) -> dict[str, Any]:
    source = profile if isinstance(profile, dict) else {}
    edge_profile = source.get("edge_profile")
    if not isinstance(edge_profile, str) or not edge_profile:
        edge_profile = "Default" if profile_id == "default" else "Profile 1"
    result = {
        "name": source.get("name")
        if isinstance(source.get("name"), str) and source.get("name")
        else profile_id.title(),
        "edge_profile": edge_profile,
        "start_view": source.get("start_view")
        if source.get("start_view") in {"mail", "calendar"}
        else "mail",
        "download_directory": source.get("download_directory")
        if isinstance(source.get("download_directory"), str)
        else str(Path.home() / "Downloads"),
        "ask_download": bool(source.get("ask_download", True)),
        "focus_mode": bool(source.get("focus_mode", False)),
        "custom_icon": source.get("custom_icon")
        if isinstance(source.get("custom_icon"), str)
        else "",
    }
    return result


def load_settings() -> dict[str, Any]:
    defaults = default_settings()
    path = settings_path()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(loaded, dict):
        return defaults

    settings = deepcopy(defaults)
    for key in (
        "default_profile",
        "autostart",
        "mailto_handler",
        "route_external_links",
        "titlebar_style",
        "titlebar_color",
        "internal_domains",
    ):
        if key in loaded:
            settings[key] = loaded[key]

    profiles = loaded.get("profiles")
    if isinstance(profiles, dict) and profiles:
        normalized: dict[str, dict[str, Any]] = {}
        for profile_id, profile in profiles.items():
            if isinstance(profile_id, str) and re.fullmatch(
                r"[a-z0-9][a-z0-9-]{0,31}", profile_id
            ):
                normalized[profile_id] = _normalize_profile(profile_id, profile)
        if normalized:
            settings["profiles"] = normalized

    if settings["default_profile"] not in settings["profiles"]:
        settings["default_profile"] = next(iter(settings["profiles"]))
    if settings["titlebar_style"] not in {"system", "outlook", "dark", "custom"}:
        settings["titlebar_style"] = "outlook"
    color = settings["titlebar_color"]
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        settings["titlebar_color"] = "#0f6cbd"
    if not isinstance(settings["internal_domains"], list):
        settings["internal_domains"] = list(DEFAULT_INTERNAL_DOMAINS)
    return settings


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.chmod(mode)
    temporary_path.replace(path)


def save_settings(settings: dict[str, Any]) -> None:
    atomic_write(
        settings_path(),
        json.dumps(settings, indent=2, sort_keys=True) + "\n",
        mode=0o600,
    )


def get_profile(
    settings: dict[str, Any], profile_id: str | None = None
) -> tuple[str, dict[str, Any]]:
    selected = profile_id or str(settings["default_profile"])
    profiles = settings["profiles"]
    if selected not in profiles:
        raise KeyError(f"unknown profile: {selected}")
    return selected, profiles[selected]


def edge_profile_token(profile: dict[str, Any]) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(profile["edge_profile"]))


def wayland_app_id(profile: dict[str, Any]) -> str:
    return f"msedge-_{APP_ID}-{edge_profile_token(profile)}"


def desktop_id(profile: dict[str, Any]) -> str:
    return f"{wayland_app_id(profile)}.desktop"


def edge_generated_desktop_id(profile: dict[str, Any]) -> str:
    return f"msedge-{APP_ID}-{edge_profile_token(profile)}.desktop"


def profile_icon(profile: dict[str, Any]) -> str:
    custom = Path(str(profile.get("custom_icon", ""))).expanduser()
    if str(custom) and custom.is_file():
        return str(custom)
    return SYSTEM_ICON_NAME


def _desktop_safe(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", " ").replace("\r", " ")


def canonical_desktop_entry(
    settings: dict[str, Any], profile_id: str, profile: dict[str, Any]
) -> str:
    name = _desktop_safe(profile["name"])
    icon = _desktop_safe(profile_icon(profile))
    return f"""[Desktop Entry]
Version=1.0
Type=Application
Name={name}
GenericName=Email and Calendar
Comment=Outlook in a dedicated Edge application
Exec=/usr/bin/outlook-pwa --profile {profile_id} %U
Icon={icon}
Terminal=false
Categories=Office;Email;
Keywords=Outlook;Microsoft 365;Office 365;Mail;Email;Calendar;
MimeType=x-scheme-handler/mailto;
StartupNotify=true
StartupWMClass={wayland_app_id(profile)}
NoDisplay=false
Actions=NewMessage;Calendar;NewEvent;Settings;
X-Outlook-PWA-Linux-Profile={user_data_dir()}
X-Outlook-PWA-Linux-Profile-ID={profile_id}

[Desktop Action NewMessage]
Name=New Message
Exec=/usr/bin/outlook-pwa --profile {profile_id} --compose
Icon=mail-message-new

[Desktop Action Calendar]
Name=Calendar
Exec=/usr/bin/outlook-pwa --profile {profile_id} --calendar
Icon=x-office-calendar

[Desktop Action NewEvent]
Name=New Event
Exec=/usr/bin/outlook-pwa --profile {profile_id} --new-event
Icon=x-office-calendar

[Desktop Action Settings]
Name=Settings
Exec=/usr/bin/outlook-pwa-settings
Icon=preferences-system
"""


def find_edge() -> str | None:
    overridden = os.environ.get("OUTLOOK_PWA_EDGE")
    if overridden:
        return overridden
    for candidate in (
        "/usr/bin/microsoft-edge-stable",
        "/opt/microsoft/msedge/microsoft-edge",
        "microsoft-edge-stable",
        "microsoft-edge",
    ):
        if candidate.startswith("/") and Path(candidate).is_file():
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def pwa_is_installed(profile: dict[str, Any]) -> bool:
    profile_path = user_data_dir() / str(profile["edge_profile"])
    candidates = (
        profile_path / "Web Applications" / "Manifest Resources" / APP_ID,
        profile_path / "Web Applications" / APP_ID,
    )
    return any(path.exists() for path in candidates)


def edge_is_running() -> bool:
    needle = f"--user-data-dir={user_data_dir()}".encode()
    proc = Path("/proc")
    try:
        processes = proc.iterdir()
    except OSError:
        return False
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            command = (process / "cmdline").read_bytes()
        except OSError:
            continue
        if needle in command:
            return True
    return False


def apply_edge_preferences(
    settings: dict[str, Any], profile: dict[str, Any]
) -> bool:
    """Apply preferences only while the dedicated Edge instance is stopped."""
    if edge_is_running():
        return False
    preferences = (
        user_data_dir() / str(profile["edge_profile"]) / "Preferences"
    )
    if not preferences.is_file():
        return False
    try:
        data = json.loads(preferences.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    changed = False
    download = data.setdefault("download", {})
    if not isinstance(download, dict):
        download = {}
        data["download"] = download
        changed = True
    download_directory = str(
        Path(str(profile["download_directory"])).expanduser()
    )
    ask_download = bool(profile["ask_download"])
    if download.get("default_directory") != download_directory:
        download["default_directory"] = download_directory
        changed = True
    if download.get("prompt_for_download") != ask_download:
        download["prompt_for_download"] = ask_download
        changed = True

    browser = data.setdefault("browser", {})
    if not isinstance(browser, dict):
        browser = {}
        data["browser"] = browser
        changed = True
    custom_frame = settings["titlebar_style"] != "system"
    if browser.get("custom_chrome_frame") != custom_frame:
        browser["custom_chrome_frame"] = custom_frame
        changed = True
    if not changed:
        return True
    try:
        atomic_write(
            preferences,
            json.dumps(data, separators=(",", ":"), ensure_ascii=False),
            mode=0o600,
        )
    except OSError:
        return False
    return True


def _hide_desktop_entry(content: str) -> str:
    lines = content.splitlines()
    entry_start = next(
        (index for index, line in enumerate(lines) if line == "[Desktop Entry]"),
        None,
    )
    if entry_start is None:
        return content
    entry_end = next(
        (
            index
            for index in range(entry_start + 1, len(lines))
            if lines[index].startswith("[")
        ),
        len(lines),
    )
    no_display = next(
        (
            index
            for index in range(entry_start + 1, entry_end)
            if lines[index].startswith("NoDisplay=")
        ),
        None,
    )
    if no_display is None:
        lines.insert(entry_end, "NoDisplay=true")
    else:
        lines[no_display] = "NoDisplay=true"
    return "\n".join(lines) + "\n"


def _copy_icon_if_changed(source: Path, destination: Path) -> bool:
    try:
        source_bytes = source.read_bytes()
        if destination.is_file() and destination.read_bytes() == source_bytes:
            return False
    except OSError:
        return False
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    destination.write_bytes(source_bytes)
    destination.chmod(0o644)
    return True


def sync_transparent_icons(profile: dict[str, Any]) -> int:
    changed = 0
    profile_token = edge_profile_token(profile)
    edge_icon_name = f"msedge-{APP_ID}-{profile_token}.png"
    for size in ICON_SIZES:
        source = (
            Path("/usr/share/icons/hicolor")
            / f"{size}x{size}"
            / "apps"
            / f"{SYSTEM_ICON_NAME}.png"
        )
        destination = (
            data_home()
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / edge_icon_name
        )
        if source.is_file() and _copy_icon_if_changed(source, destination):
            changed += 1
    return changed


def refresh_desktop_caches() -> None:
    desktop_database = shutil.which("update-desktop-database")
    if desktop_database and application_dir().is_dir():
        subprocess.run(
            (desktop_database, str(application_dir())),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    icon_cache = shutil.which("gtk-update-icon-cache")
    icon_directory = data_home() / "icons" / "hicolor"
    if icon_cache and icon_directory.is_dir():
        subprocess.run(
            (icon_cache, "-q", "-t", str(icon_directory)),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def reconcile_profile(
    settings: dict[str, Any], profile_id: str, profile: dict[str, Any]
) -> int:
    changed = 0
    directory = application_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    canonical_path = directory / desktop_id(profile)
    canonical = canonical_desktop_entry(settings, profile_id, profile)
    try:
        existing = canonical_path.read_text(encoding="utf-8")
    except OSError:
        existing = ""
    if existing != canonical:
        atomic_write(canonical_path, canonical, mode=0o644)
        changed += 1

    generated_path = directory / edge_generated_desktop_id(profile)
    if generated_path.is_file() and generated_path != canonical_path:
        try:
            generated = generated_path.read_text(encoding="utf-8")
            profile_argument = f"--user-data-dir={user_data_dir()}"
            edge_argument = f"--profile-directory={profile['edge_profile']}"
            if profile_argument in generated and edge_argument in generated:
                hidden = _hide_desktop_entry(generated)
                if hidden != generated:
                    atomic_write(generated_path, hidden, mode=0o644)
                    changed += 1
        except OSError:
            pass
    changed += sync_transparent_icons(profile)
    return changed


def reconcile_all(settings: dict[str, Any] | None = None) -> int:
    active = settings or load_settings()
    changed = 0
    for profile_id, profile in active["profiles"].items():
        changed += reconcile_profile(active, profile_id, profile)
    if changed:
        refresh_desktop_caches()
    return changed


def remove_profile_integration(profile: dict[str, Any]) -> None:
    """Remove launchers and copied icons for a no-longer-configured profile."""
    paths = (
        application_dir() / desktop_id(profile),
        config_home() / "autostart" / "outlook-pwa-linux.desktop",
    )
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    edge_icon_name = (
        f"msedge-{APP_ID}-{edge_profile_token(profile)}.png"
    )
    for size in ICON_SIZES:
        path = (
            data_home()
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / edge_icon_name
        )
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    refresh_desktop_caches()


def extension_enabled(settings: dict[str, Any]) -> bool:
    # The extension also supplies the integrated Settings control and automatic
    # update indicator, so it remains enabled when optional theming/routing is off.
    return True


def effective_titlebar_color(settings: dict[str, Any]) -> str:
    style = settings["titlebar_style"]
    if style == "outlook":
        return "#0f6cbd"
    if style == "dark":
        return "#202124"
    if style == "custom":
        return str(settings["titlebar_color"])
    return ""


def sync_extension(settings: dict[str, Any]) -> Path | None:
    if not extension_enabled(settings):
        return None
    source = resource_root() / "extension"
    destination = app_config_dir() / "extension"
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    current_background = "background-v030.js"
    for filename in (
        "manifest.json",
        "content.js",
        current_background,
    ):
        source_file = source / filename
        if source_file.is_file():
            shutil.copyfile(source_file, destination / filename)
            (destination / filename).chmod(0o600)
    brand_source = resource_root() / "branding" / "a5-settings.svg"
    if not brand_source.is_file():
        brand_source = resource_root() / "assets" / "branding" / "a5-settings.svg"
    if brand_source.is_file():
        shutil.copyfile(brand_source, destination / "a5-settings.svg")
        (destination / "a5-settings.svg").chmod(0o600)
    for obsolete_background in destination.glob("background*.js"):
        if obsolete_background.name != current_background:
            try:
                obsolete_background.unlink()
            except OSError:
                pass
    configuration = {
        "themeColor": effective_titlebar_color(settings),
        "routeExternalLinks": bool(settings["route_external_links"]),
        "internalDomains": settings["internal_domains"],
    }
    atomic_write(
        destination / "config.json",
        json.dumps(configuration, separators=(",", ":")) + "\n",
        mode=0o600,
    )
    theme_directory = app_config_dir() / "titlebar-theme"
    theme_manifest = theme_directory / "manifest.json"
    color = effective_titlebar_color(settings)
    if color:
        red, green, blue = (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
        )
        foreground = [255, 255, 255]
        theme = {
            "manifest_version": 3,
            "name": "Outlook Window Theme",
            "version": VERSION,
            "theme": {
                "colors": {
                    "frame": [red, green, blue],
                    "frame_inactive": [red, green, blue],
                    "toolbar": [red, green, blue],
                    "tab_text": foreground,
                    "tab_background_text": foreground,
                    "toolbar_text": foreground,
                    "bookmark_text": foreground,
                    "button_background": [red, green, blue],
                }
            },
        }
        atomic_write(
            theme_manifest,
            json.dumps(theme, indent=2) + "\n",
            mode=0o600,
        )
    else:
        try:
            theme_manifest.unlink()
        except FileNotFoundError:
            pass
    return destination


def set_autostart(enabled: bool, profile_id: str) -> None:
    path = config_home() / "autostart" / "outlook-pwa-linux.desktop"
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    content = f"""[Desktop Entry]
Type=Application
Name=Outlook background notifications
Comment=Start Outlook in the background
Exec=/usr/bin/outlook-pwa --profile {profile_id} --background
Icon={SYSTEM_ICON_NAME}
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
"""
    atomic_write(path, content, mode=0o644)


def current_mailto_handler() -> str:
    command = shutil.which("xdg-mime")
    if not command:
        return ""
    result = subprocess.run(
        (command, "query", "default", "x-scheme-handler/mailto"),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def set_mailto_handler(enabled: bool, profile: dict[str, Any]) -> None:
    command = shutil.which("xdg-mime")
    if not command:
        return
    target = desktop_id(profile)
    if not enabled and current_mailto_handler() == target:
        default_browser = ""
        xdg_settings = shutil.which("xdg-settings")
        if xdg_settings:
            result = subprocess.run(
                (xdg_settings, "get", "default-web-browser"),
                check=False,
                capture_output=True,
                text=True,
            )
            default_browser = result.stdout.strip()
        target = default_browser or "firefox_firefox.desktop"
    if enabled or current_mailto_handler() == desktop_id(profile):
        subprocess.run(
            (command, "default", target, "x-scheme-handler/mailto"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def apply_user_integration(settings: dict[str, Any]) -> int:
    if not settings_path().is_file():
        save_settings(settings)
    changed = reconcile_all(settings)
    sync_extension(settings)
    for profile in settings["profiles"].values():
        apply_edge_preferences(settings, profile)
    _, profile = get_profile(settings)
    set_autostart(bool(settings["autostart"]), str(settings["default_profile"]))
    set_mailto_handler(bool(settings["mailto_handler"]), profile)
    return changed


def profile_size(profile: dict[str, Any]) -> int:
    root = user_data_dir() / str(profile["edge_profile"])
    total = 0
    if not root.is_dir():
        return 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def next_profile(settings: dict[str, Any]) -> tuple[str, str]:
    profiles = settings["profiles"]
    index = 1
    while True:
        profile_id = "personal" if index == 1 else f"profile-{index}"
        edge_profile = f"Profile {index}"
        if profile_id not in profiles and all(
            item["edge_profile"] != edge_profile for item in profiles.values()
        ):
            return profile_id, edge_profile
        index += 1
