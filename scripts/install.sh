#!/bin/sh
set -eu
umask 022

MICROSOFT_KEY_FINGERPRINT="BC528686B50D79E339D3721CEB3E94ADBE1229CF"
MICROSOFT_KEY_URL="https://packages.microsoft.com/keys/microsoft.asc"
MICROSOFT_EDGE_REPO="https://packages.microsoft.com/repos/edge"

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
version=$(tr -d '[:space:]' < "$project_root/VERSION")
package_path="$project_root/dist/outlook-pwa-linux_${version}_amd64.deb"
root_mode=0
no_launch=0

usage() {
    cat <<'EOF'
Usage: ./scripts/install.sh [--no-launch]

Build and install Outlook PWA for Linux. Administrator authentication is
requested through PolicyKit when available.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --as-root)
            root_mode=1
            shift
            if [ "$#" -eq 0 ]; then
                echo "--as-root requires the package path." >&2
                exit 2
            fi
            package_path=$1
            ;;
        --no-launch)
            no_launch=1
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

install_as_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "The privileged installation phase must run as root." >&2
        exit 1
    fi
    if [ "$(dpkg --print-architecture)" != "amd64" ]; then
        echo "This package currently supports amd64 systems only." >&2
        exit 1
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "apt-get was not found; Debian or Ubuntu is required." >&2
        exit 1
    fi
    if [ ! -f "$package_path" ]; then
        echo "Package not found: $package_path" >&2
        exit 1
    fi

    previous_x_browser=$(
        update-alternatives --query x-www-browser 2>/dev/null |
            awk '$1 == "Value:" { print $2; exit }' || true
    )
    previous_gnome_browser=$(
        update-alternatives --query gnome-www-browser 2>/dev/null |
            awk '$1 == "Value:" { print $2; exit }' || true
    )

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg

    key_file=$(mktemp)
    package_copy=$(mktemp /tmp/outlook-pwa-linux.XXXXXX.deb)
    trap 'rm -f -- "$key_file" "$package_copy"' EXIT HUP INT TERM
    install -m 0644 "$package_path" "$package_copy"
    curl --proto '=https' --tlsv1.2 -fsSL "$MICROSOFT_KEY_URL" -o "$key_file"
    downloaded_fingerprint=$(
        gpg --batch --show-keys --with-colons "$key_file" |
            awk -F: '$1 == "fpr" { print $10; exit }'
    )
    if [ "$downloaded_fingerprint" != "$MICROSOFT_KEY_FINGERPRINT" ]; then
        echo "Microsoft key fingerprint mismatch." >&2
        echo "Expected: $MICROSOFT_KEY_FINGERPRINT" >&2
        echo "Received: ${downloaded_fingerprint:-none}" >&2
        exit 1
    fi

    install -d -m 0755 /etc/apt/keyrings
    gpg --batch --yes --dearmor \
        --output /etc/apt/keyrings/microsoft-edge.gpg "$key_file"
    chmod 0644 /etc/apt/keyrings/microsoft-edge.gpg
    printf '%s\n' \
        "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft-edge.gpg] $MICROSOFT_EDGE_REPO stable main" \
        > /etc/apt/sources.list.d/microsoft-edge-stable.list

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y microsoft-edge-stable
    if [ -n "$previous_x_browser" ] &&
        [ "$previous_x_browser" != "/usr/bin/microsoft-edge-stable" ]; then
        update-alternatives --set x-www-browser "$previous_x_browser" || true
    fi
    if [ -n "$previous_gnome_browser" ] &&
        [ "$previous_gnome_browser" != "/usr/bin/microsoft-edge-stable" ]; then
        update-alternatives --set gnome-www-browser "$previous_gnome_browser" || true
    fi
    if [ -f /etc/apt/sources.list.d/microsoft-edge.sources ] &&
        [ -f /usr/share/keyrings/microsoft-edge.gpg ]; then
        rm -f \
            /etc/apt/sources.list.d/microsoft-edge-stable.list \
            /etc/apt/keyrings/microsoft-edge.gpg
    fi
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$package_copy"
}

if [ "$root_mode" -eq 1 ]; then
    install_as_root
    exit 0
fi

"$script_dir/build-deb.sh"

if [ "$(id -u)" -eq 0 ]; then
    install_as_root
elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$0" --as-root "$package_path" --no-launch
elif command -v sudo >/dev/null 2>&1; then
    sudo "$0" --as-root "$package_path" --no-launch
else
    echo "Neither pkexec nor sudo is available for administrator authentication." >&2
    exit 1
fi

if [ "$no_launch" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    /usr/bin/outlook-pwa
    printf '\nOutlook is installed. Complete Microsoft sign-in in the window that opens.\n'
else
    printf '\nOutlook PWA for Linux is installed.\n'
fi
