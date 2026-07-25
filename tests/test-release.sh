#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
version=$(tr -d '[:space:]' < "$project_root/VERSION")
asset_name="outlook-pwa-linux_${version}_amd64.deb"
release_source=$(mktemp -d)
verified_download=$(mktemp -d)
tampered_source=$(mktemp -d)
tampered_download=$(mktemp -d)
package_root=$(mktemp -d)

# Invoked by the trap below.
# shellcheck disable=SC2329
cleanup() {
    rm -rf -- \
        "$release_source" \
        "$verified_download" \
        "$tampered_source" \
        "$tampered_download" \
        "$package_root"
}
trap cleanup EXIT HUP INT TERM

sh -n \
    "$project_root/install-outlook" \
    "$project_root/scripts/prepare-release.sh"

test "$("$project_root/install-outlook" --version)" = \
    "install-outlook $version"
test -x "$project_root/dist/install-outlook"
test -f "$project_root/dist/$asset_name"
test -f "$project_root/dist/SHA256SUMS"
dpkg-deb --extract "$project_root/dist/$asset_name" "$package_root"
test -x "$package_root/usr/lib/outlook-pwa-linux/outlook-update-helper"
test -f "$package_root/usr/lib/outlook-pwa-linux/outlook_pwa_updater.py"
test -f \
    "$package_root/usr/share/polkit-1/actions/com.outlook_pwa_linux.update.policy"
test -f \
    "$package_root/usr/share/outlook-pwa-linux/extension/background-v030.js"
test -f \
    "$package_root/usr/share/outlook-pwa-linux/extension/a5-settings.svg"
test -f \
    "$package_root/usr/share/outlook-pwa-linux/branding/a5-settings.svg"
test ! -e \
    "$package_root/usr/share/outlook-pwa-linux/extension/background-v029.js"
python3 - <<PY
import xml.etree.ElementTree as ET
ET.parse(
    "$package_root/usr/share/polkit-1/actions/"
    "com.outlook_pwa_linux.update.policy"
)
PY
dpkg-deb --field "$project_root/dist/$asset_name" Depends |
    grep -Eq '(^|, )pkexec(,|$)'
first_package_checksum=$(
    sha256sum "$project_root/dist/$asset_name" | awk '{ print $1 }'
)
"$project_root/scripts/build-deb.sh" >/dev/null
second_package_checksum=$(
    sha256sum "$project_root/dist/$asset_name" | awk '{ print $1 }'
)
test "$first_package_checksum" = "$second_package_checksum"
(
    cd "$project_root/dist"
    sha256sum --check --strict SHA256SUMS
)

mkdir -p "$release_source/v$version"
install -m 0644 \
    "$project_root/dist/$asset_name" \
    "$release_source/v$version/$asset_name"
install -m 0644 \
    "$project_root/dist/SHA256SUMS" \
    "$release_source/v$version/SHA256SUMS"

OUTLOOK_PWA_RELEASE_BASE_URL="file://$release_source/v$version" \
OUTLOOK_PWA_ALLOW_INSECURE_TEST_URL=1 \
    "$project_root/install-outlook" \
        --download-only "$verified_download"

cmp \
    "$project_root/dist/$asset_name" \
    "$verified_download/$asset_name"
(
    cd "$verified_download"
    sha256sum --check --strict --ignore-missing SHA256SUMS
)

mkdir -p "$tampered_source/v$version"
install -m 0644 \
    "$release_source/v$version/$asset_name" \
    "$tampered_source/v$version/$asset_name"
install -m 0644 \
    "$release_source/v$version/SHA256SUMS" \
    "$tampered_source/v$version/SHA256SUMS"
printf 'tampered\n' >> "$tampered_source/v$version/$asset_name"

if OUTLOOK_PWA_RELEASE_BASE_URL="file://$tampered_source/v$version" \
    OUTLOOK_PWA_ALLOW_INSECURE_TEST_URL=1 \
        "$project_root/install-outlook" \
            --download-only "$tampered_download" \
            >"$tampered_download/output.log" 2>&1; then
    echo "The installer accepted a tampered package." >&2
    exit 1
fi
grep -q \
    'release checksum verification failed' \
    "$tampered_download/output.log"
test ! -e "$tampered_download/$asset_name"

echo "Outlook v$version release verification passed."
