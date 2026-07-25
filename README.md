# Outlook for Linux

[![CI](https://github.com/andershfranzen/outlook-pwa-linux/actions/workflows/ci.yml/badge.svg)](https://github.com/andershfranzen/outlook-pwa-linux/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/andershfranzen/outlook-pwa-linux)](https://github.com/andershfranzen/outlook-pwa-linux/releases/latest)
[![License: MIT](https://img.shields.io/github/license/andershfranzen/outlook-pwa-linux)](LICENSE)

<p align="center">
  <img src="assets/icons/128x128/outlook-pwa-linux.png"
       width="96"
       height="96"
       alt="Outlook">
</p>

An unofficial, lightweight Outlook desktop integration for Debian and Ubuntu.
It uses Microsoft Edge's installed web-app engine for Outlook while leaving
Firefox—or your chosen browser—as the system default.

## Features

- Outlook Mail, Calendar, People, Tasks, OneDrive, SharePoint, and Microsoft 365
  pages stay inside one app window;
- isolated work and personal Outlook profiles with separate dock identities;
- native GTK 4/Libadwaita settings integrated into Outlook's own toolbar;
- Outlook blue, dark, system, or custom title-bar colors;
- external web links open in the system browser;
- Focus mode for a fullscreen, chrome-free Outlook window;
- configurable start view, downloads, save prompts, and dock icons;
- optional background startup for notifications;
- Outlook handling for `mailto:` links;
- desktop actions for Mail, Calendar, New Message, New Event, and Settings.

No account credentials are requested or stored by the installer. Microsoft
sign-in, MFA, cookies, and notification permissions remain inside Outlook and
its dedicated Edge data directory.

## Requirements

- 64-bit x86 (`amd64`) Ubuntu or Debian;
- administrator access during installation;
- an internet connection.

GNOME on Wayland is the primary tested desktop. Other Debian-based desktops
may work, but have not yet received the same integration testing.

## Install

Download the small bootstrap installer from the latest GitHub release, inspect
it if desired, then run it as your normal user:

```sh
curl --proto '=https' --tlsv1.2 -fLO \
  https://github.com/andershfranzen/outlook-pwa-linux/releases/latest/download/install-outlook
chmod +x install-outlook
./install-outlook
```

If the GitHub CLI is installed, the bootstrap itself can be authenticated
before it is executed:

```sh
gh attestation verify install-outlook \
  --repo andershfranzen/outlook-pwa-linux
```

The installer:

1. downloads the versioned Debian package without administrator privileges;
2. verifies the package against the release's SHA-256 manifest;
3. requests administrator authentication;
4. verifies the exact package bytes again after elevation;
5. configures Microsoft's official Edge repository and verifies its signing-key
   fingerprint;
6. installs Edge, the Outlook package, and required desktop libraries.

It preserves the existing system-default browser. Re-running the installer
upgrades the package and keeps Outlook accounts and settings.

To verify the release without installing it:

```sh
./install-outlook --download-only outlook-release
cd outlook-release
sha256sum --check --strict --ignore-missing SHA256SUMS
gh attestation verify outlook-pwa-linux_0.2.9_amd64.deb \
  --repo andershfranzen/outlook-pwa-linux
```

The GitHub CLI is only needed for the optional build-provenance check.

### Install the Debian package directly

If Microsoft's Edge repository is already configured, download the `.deb` and
`SHA256SUMS` from the release page, verify them, then use:

```sh
sudo apt install ./outlook-pwa-linux_0.2.9_amd64.deb
```

The bootstrap installer is recommended on a clean system because a bare `.deb`
cannot configure the external repository needed to resolve its Edge dependency.

## Settings and commands

Open Settings from the sliders icon beside Outlook's own gear button, from the
Outlook dock menu, or with:

```sh
outlook-pwa-settings
```

Useful launcher commands:

```sh
outlook-pwa
outlook-pwa --calendar
outlook-pwa --compose someone@example.com
outlook-pwa --new-event
outlook-pwa --focus
outlook-pwa --list-profiles
outlook-pwa --diagnose
```

The dedicated Edge data and wrapper settings live in
`~/.config/outlook-pwa-linux` unless `XDG_CONFIG_HOME` is set.

## Build from source

The developer installer builds the package locally, installs its dependencies,
and launches Outlook:

```sh
make test
./scripts/install.sh
```

Create the exact release asset set without installing it:

```sh
make release
```

This writes the versioned `.deb`, `install-outlook`, and `SHA256SUMS` to
`dist/`, then exercises both the valid download path and a deliberately
tampered-package failure path. Package timestamps are normalized with
`SOURCE_DATE_EPOCH`, and the test requires two builds from the same source to
produce an identical `.deb`.

Before the first public release, enable **Release immutability** in the GitHub
repository settings. Pushing a matching version tag then runs the release
workflow:

```sh
version=$(tr -d '[:space:]' < VERSION)
git tag -a "v$version" -m "Outlook $version"
git push origin "v$version"
```

The workflow tests, builds, generates GitHub/Sigstore provenance attestations,
and publishes the three release assets.

## Contributing and support

Bug reports and focused feature proposals are welcome in
[GitHub Issues](https://github.com/andershfranzen/outlook-pwa-linux/issues).
Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
Report suspected vulnerabilities privately as described in
[SECURITY.md](SECURITY.md).

## Window top bar

The title-bar option uses the standard web-app theme-color mechanism supported
by Edge. This preserves native window dragging, resize controls, GNOME dock
matching, and keyboard behavior. Focus mode is available when no top bar is
preferred; press F11 to leave fullscreen.

## Link routing

A small bundled Edge extension watches links clicked inside Outlook. HTTP(S)
links outside configured Microsoft and Office domains are sent to a restricted
native-messaging helper, which opens the system default browser. The helper
does not execute shell commands and rejects non-HTTP(S) URLs.

## Uninstall

```sh
./scripts/uninstall.sh
```

This removes the Debian package, Edge policy, and native helper, but preserves
local Outlook sessions and leaves Edge installed. To also remove local Outlook
data:

```sh
./scripts/uninstall.sh --remove-profile
```

## Implementation notes

The package uses Chromium's `WebAppInstallForceList` policy with Outlook's web
app ID. Its launcher uses Edge's per-profile desktop identity so GNOME and
Wayland associate each dock icon with the correct window.

The managed policy is machine-wide because Edge reads Linux policy from
`/etc/opt/edge/policies/managed`. Outlook may therefore also be provisioned in
other Edge profiles while the package is installed. The launcher always uses
its dedicated data directory.

Microsoft Edge, Microsoft Outlook, and their trademarks belong to Microsoft.
This project is not affiliated with or endorsed by Microsoft and does not
redistribute Microsoft software. See `assets/NOTICE` for the artwork notice.
