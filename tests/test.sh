#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
launcher="$project_root/src/outlook-pwa"
test_home=$(mktemp -d)
trap 'rm -rf -- "$test_home"' EXIT HUP INT TERM
export OUTLOOK_PWA_EDGE="/opt/microsoft/msedge/microsoft-edge"
export OUTLOOK_PWA_RESOURCE_ROOT="$project_root"
export XDG_CONFIG_HOME="$test_home/config"
export XDG_DATA_HOME="$test_home/data"

python3 -m py_compile \
    "$project_root/src/outlook-pwa" \
    "$project_root/src/outlook-pwa-settings" \
    "$project_root/src/outlook-link-router" \
    "$project_root/src/outlook_pwa_common.py"

PYTHONPATH="$project_root/src" python3 - <<'PY'
from copy import deepcopy
import json
import os
from pathlib import Path

import outlook_pwa_common as common

settings = common.default_settings()
assert settings["titlebar_style"] == "outlook"
assert common.effective_titlebar_color(settings) == "#0f6cbd"
profile = settings["profiles"]["default"]
assert common.desktop_id(profile) == (
    "msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
)

second = deepcopy(profile)
second["name"] = "Personal Outlook"
second["edge_profile"] = "Profile 1"
settings["profiles"]["personal"] = second
assert common.desktop_id(second).endswith("-Profile_1.desktop")

common.save_settings(settings)
loaded = common.load_settings()
assert loaded["profiles"]["personal"]["name"] == "Personal Outlook"

preferences = common.user_data_dir() / "Default" / "Preferences"
preferences.parent.mkdir(parents=True)
preferences.write_text('{"browser":{},"download":{}}')
assert common.apply_edge_preferences(loaded, loaded["profiles"]["default"])
edge_preferences = json.loads(preferences.read_text())
assert edge_preferences["browser"]["custom_chrome_frame"] is True
assert edge_preferences["download"]["prompt_for_download"] is True

extension = common.sync_extension(loaded)
configuration = json.loads((extension / "config.json").read_text())
assert configuration["themeColor"] == "#0f6cbd"
assert configuration["routeExternalLinks"] is True
theme = json.loads(
    (common.app_config_dir() / "titlebar-theme" / "manifest.json").read_text()
)
assert theme["theme"]["colors"]["frame"] == [15, 108, 189]

desktop = common.canonical_desktop_entry(loaded, "personal", second)
assert "Exec=/usr/bin/outlook-pwa --profile personal %U" in desktop
assert "StartupWMClass=msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Profile_1" in desktop
PY

mail_command=$("$launcher" --dry-run)
calendar_command=$("$launcher" --calendar --dry-run)
focus_command=$("$launcher" --focus --dry-run)
personal_command=$("$launcher" --profile personal --dry-run)
compose_command=$(
    "$launcher" --dry-run \
        'mailto:person@example.com?subject=Hello%20there&body=Test%20body'
)
diagnostics=$("$launcher" --diagnose)

case "$mail_command" in
    *"--profile-directory=Default"*"--app=https://outlook.office.com/mail/"*) ;;
    *)
        echo "Mail launch command is incorrect: $mail_command" >&2
        exit 1
        ;;
esac

case "$calendar_command" in
    *"--app=https://outlook.office.com/calendar/view/month"*) ;;
    *)
        echo "Calendar launch command is incorrect: $calendar_command" >&2
        exit 1
        ;;
esac

case "$focus_command" in
    *"--start-fullscreen"*) ;;
    *)
        echo "Focus-mode launch command is incorrect: $focus_command" >&2
        exit 1
        ;;
esac

case "$personal_command" in
    *"--profile-directory=Profile 1"*) ;;
    *)
        echo "Profile launch command is incorrect: $personal_command" >&2
        exit 1
        ;;
esac

case "$compose_command" in
    *"to=person%40example.com"*"subject=Hello%20there"*"body=Test%20body"*) ;;
    *)
        echo "mailto conversion is incorrect: $compose_command" >&2
        exit 1
        ;;
esac

printf '%s\n' "$diagnostics" | jq -e \
    '.edge_installed == true and .titlebar_style == "outlook"' >/dev/null

mkdir -p \
    "$XDG_CONFIG_HOME/outlook-pwa-linux/edge-profile/Default/Web Applications/Manifest Resources/faolnafnngnfdaknnbpnkhgohbobgegn" \
    "$XDG_DATA_HOME/applications"
printf '%s\n' \
    '[Desktop Entry]' \
    'Type=Application' \
    'Name=Outlook' \
    "Exec=/opt/microsoft/msedge/microsoft-edge --user-data-dir=$XDG_CONFIG_HOME/outlook-pwa-linux/edge-profile --profile-directory=Default --app-id=faolnafnngnfdaknnbpnkhgohbobgegn" \
    > "$XDG_DATA_HOME/applications/msedge-faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"

"$launcher" --reconcile-launchers
grep -qx 'NoDisplay=true' \
    "$XDG_DATA_HOME/applications/msedge-faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
grep -qx 'NoDisplay=false' \
    "$XDG_DATA_HOME/applications/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
grep -qx 'Exec=/usr/bin/outlook-pwa --profile default %U' \
    "$XDG_DATA_HOME/applications/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
grep -qx 'Icon=outlook-pwa-linux' \
    "$XDG_DATA_HOME/applications/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
desktop-file-validate \
    "$XDG_DATA_HOME/applications/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"

PROJECT_ROOT="$project_root" python3 - <<'PY'
import json
import os
from pathlib import Path
import struct
import subprocess

root = Path(os.environ["PROJECT_ROOT"])
message = json.dumps({"url": "https://example.com/test"}).encode()
payload = struct.pack("=I", len(message)) + message
environment = os.environ.copy()
environment["OUTLOOK_PWA_LINK_ROUTER_DRY_RUN"] = "1"
result = subprocess.run(
    [str(root / "src/outlook-link-router")],
    input=payload,
    capture_output=True,
    check=True,
    env=environment,
)
length = struct.unpack("=I", result.stdout[:4])[0]
response = json.loads(result.stdout[4:4 + length])
assert response == {"ok": True}
PY

desktop-file-validate \
    "$project_root/packaging/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop" \
    "$project_root/packaging/com.outlook_pwa_linux.settings.desktop"
jq -e '.manifest_version == 3 and .version == "0.2.8"' \
    "$project_root/extension/manifest.json" >/dev/null
jq -e \
    '.WebAppInstallForceList[0].fallback_app_name == "Outlook"
     and (.WebAppInstallForceList[0] | has("custom_name") | not)' \
    "$project_root/packaging/outlook-pwa-policy.json" >/dev/null
if command -v node >/dev/null 2>&1; then
    node --check "$project_root/extension/content.js"
    node --check "$project_root/extension/background-v028.js"
fi

echo "Outlook v0.2.8 tests passed."
