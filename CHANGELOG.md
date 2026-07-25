# Changelog

## 0.3.0

- Added automatic daily checks against the latest immutable GitHub release.
- Added an update indicator to Outlook’s integrated Linux settings control.
- Replaced the generic sliders glyph with an a5 settings mark derived from the
  original Instrument Serif logo artwork.
- Added download, verification, installation, and restart controls to the
  native Settings window.
- Required GitHub’s asset digest and `SHA256SUMS` to agree before installation.
- Added a minimal privileged helper that independently revalidates the latest
  release, closes the verification race, and installs only the expected Debian
  package after administrator authentication.

## 0.2.9

- Preserved Outlook's official Settings button and click behavior.
- Gave the Outlook for Linux settings control an independent adjacent hitbox.
- Removed inherited Outlook toolbar classes that could overlap the two buttons.
- Expanded Outlook's reserved toolbar region so the gear stays clear of the
  account avatar.

## 0.2.8

First public release candidate.

- Integrated native settings access directly into Outlook.
- Added isolated work and personal profiles.
- Added Outlook-blue, dark, system, and custom title-bar styles.
- Kept Outlook, Calendar, People, Tasks, and Microsoft 365 pages in the app.
- Routed external links to the system browser.
- Added mailto handling, notification startup, focus mode, and desktop actions.
- Added a verified bootstrap installer and deterministic GitHub release workflow.
