#!/bin/sh
set -eu
umask 022

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
version=$(tr -d '[:space:]' < "$project_root/VERSION")
source_date_epoch=$(tr -d '[:space:]' < "$project_root/SOURCE_DATE_EPOCH")
package_name="outlook-pwa-linux_${version}_amd64.deb"
package_path="$project_root/dist/$package_name"
release_installer="$project_root/dist/install-outlook"
checksums="$project_root/dist/SHA256SUMS"

installer_version=$("$project_root/install-outlook" --version | awk '{ print $2 }')
control_version=$(awk '$1 == "Version:" { print $2; exit }' "$project_root/packaging/control")
manifest_version=$(jq -r .version "$project_root/extension/manifest.json")
common_version=$(
    PYTHONPATH="$project_root/src" python3 -c \
        'from outlook_pwa_common import VERSION; print(VERSION)'
)

for candidate in \
    "$installer_version" \
    "$control_version" \
    "$manifest_version" \
    "$common_version"; do
    if [ "$candidate" != "$version" ]; then
        echo "Release version mismatch: expected $version, found $candidate" >&2
        exit 1
    fi
done

case "$source_date_epoch" in
    ''|*[!0-9]*)
        echo "SOURCE_DATE_EPOCH must contain a Unix timestamp." >&2
        exit 1
        ;;
esac

"$project_root/scripts/build-deb.sh"
test "$(dpkg-deb --field "$package_path" Version)" = "$version"
test "$(dpkg-deb --field "$package_path" Architecture)" = "amd64"

install -m 0755 "$project_root/install-outlook" "$release_installer"
(
    cd "$project_root/dist"
    sha256sum "$package_name" install-outlook > "$checksums"
)

printf '%s\n' \
    "$package_path" \
    "$release_installer" \
    "$checksums"
