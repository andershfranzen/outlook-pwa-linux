#!/bin/sh
set -eu
umask 022

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
version=$(tr -d '[:space:]' < "$project_root/VERSION")
source_date_epoch=$(tr -d '[:space:]' < "$project_root/SOURCE_DATE_EPOCH")
stage_dir="$project_root/build/root"
output="$project_root/dist/outlook-pwa-linux_${version}_amd64.deb"

case "$source_date_epoch" in
    ''|*[!0-9]*)
        echo "SOURCE_DATE_EPOCH must contain a Unix timestamp." >&2
        exit 1
        ;;
esac
SOURCE_DATE_EPOCH=$source_date_epoch
export SOURCE_DATE_EPOCH

case "$stage_dir" in
    "$project_root"/build/root) ;;
    *)
        echo "Refusing to clean unexpected staging path: $stage_dir" >&2
        exit 1
        ;;
esac

if [ -e "$stage_dir" ]; then
    rm -rf -- "$stage_dir"
fi

mkdir -p \
    "$stage_dir/DEBIAN" \
    "$stage_dir/etc/opt/edge/native-messaging-hosts" \
    "$stage_dir/etc/opt/edge/policies/managed" \
    "$stage_dir/usr/bin" \
    "$stage_dir/usr/lib/outlook-pwa-linux" \
    "$stage_dir/usr/share/applications" \
    "$stage_dir/usr/share/doc/outlook-pwa-linux" \
    "$stage_dir/usr/share/outlook-pwa-linux/extension"

install -m 0644 "$project_root/packaging/control" "$stage_dir/DEBIAN/control"
install -m 0644 "$project_root/packaging/conffiles" "$stage_dir/DEBIAN/conffiles"
install -m 0755 "$project_root/packaging/postinst" "$stage_dir/DEBIAN/postinst"
install -m 0755 "$project_root/packaging/postrm" "$stage_dir/DEBIAN/postrm"
install -m 0755 "$project_root/src/outlook-pwa" "$stage_dir/usr/bin/outlook-pwa"
install -m 0755 \
    "$project_root/src/outlook-pwa-settings" \
    "$stage_dir/usr/bin/outlook-pwa-settings"
install -m 0644 \
    "$project_root/src/outlook_pwa_common.py" \
    "$stage_dir/usr/lib/outlook-pwa-linux/outlook_pwa_common.py"
install -m 0755 \
    "$project_root/src/outlook-link-router" \
    "$stage_dir/usr/lib/outlook-pwa-linux/outlook-link-router"
install -m 0644 \
    "$project_root/packaging/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop" \
    "$stage_dir/usr/share/applications/msedge-_faolnafnngnfdaknnbpnkhgohbobgegn-Default.desktop"
install -m 0644 \
    "$project_root/packaging/com.outlook_pwa_linux.settings.desktop" \
    "$stage_dir/usr/share/applications/com.outlook_pwa_linux.settings.desktop"
for size in 16 32 48 64 128 256; do
    icon_dir="$stage_dir/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$icon_dir"
    install -m 0644 \
        "$project_root/assets/icons/${size}x${size}/outlook-pwa-linux.png" \
        "$icon_dir/outlook-pwa-linux.png"
done
for extension_file in manifest.json content.js background-v029.js config.json; do
    install -m 0644 \
        "$project_root/extension/$extension_file" \
        "$stage_dir/usr/share/outlook-pwa-linux/extension/$extension_file"
done
install -m 0644 \
    "$project_root/packaging/outlook-pwa-policy.json" \
    "$stage_dir/etc/opt/edge/policies/managed/outlook-pwa-linux.json"
install -m 0644 \
    "$project_root/packaging/native-host.json" \
    "$stage_dir/etc/opt/edge/native-messaging-hosts/com.outlook_pwa_linux.link_router.json"
install -m 0644 "$project_root/README.md" \
    "$stage_dir/usr/share/doc/outlook-pwa-linux/README.md"
install -m 0644 "$project_root/LICENSE" \
    "$stage_dir/usr/share/doc/outlook-pwa-linux/copyright"
install -m 0644 "$project_root/assets/NOTICE" \
    "$stage_dir/usr/share/doc/outlook-pwa-linux/artwork-notice"

mkdir -p "$project_root/dist"
dpkg-deb --root-owner-group --build "$stage_dir" "$output"
echo "$output"
