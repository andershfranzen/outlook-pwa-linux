#!/bin/sh
set -eu

remove_profile=0
root_mode=0

usage() {
    cat <<'EOF'
Usage: ./scripts/uninstall.sh [--remove-profile]

Remove the Outlook PWA Debian package. Microsoft Edge and its repository are
left installed. Local Outlook session data is retained unless --remove-profile
is explicitly supplied.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --as-root)
            root_mode=1
            ;;
        --remove-profile)
            remove_profile=1
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

if [ "$root_mode" -eq 1 ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "The privileged removal phase must run as root." >&2
        exit 1
    fi
    apt-get remove --purge -y outlook-pwa-linux
    exit 0
fi

if [ "$(id -u)" -eq 0 ]; then
    apt-get remove --purge -y outlook-pwa-linux
elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$0" --as-root
elif command -v sudo >/dev/null 2>&1; then
    sudo "$0" --as-root
else
    echo "Neither pkexec nor sudo is available for administrator authentication." >&2
    exit 1
fi

if [ "$remove_profile" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
    config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
    profile_root="$config_home/outlook-pwa-linux"
    case "$profile_root" in
        "$config_home"/outlook-pwa-linux)
            if [ -d "$profile_root" ]; then
                rm -rf -- "$profile_root"
                echo "Removed local Outlook profile: $profile_root"
            fi
            ;;
        *)
            echo "Refusing to remove unexpected profile path: $profile_root" >&2
            exit 1
            ;;
    esac
fi

echo "Outlook PWA for Linux was removed."
