# Security

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
private vulnerability reporting feature for this repository instead.

Include the affected version, the expected impact, and enough reproduction
details to verify the issue without exposing account credentials.

## Security boundaries

Outlook authentication, MFA, cookies, and mailbox data are handled by Outlook
and Microsoft Edge. This project does not request or store Microsoft account
credentials.

The installer requires administrator authentication because the package
installs an Edge enterprise policy and native-messaging host. It downloads the
Debian package before elevation, verifies its SHA-256 checksum, then rechecks
the exact bytes after entering the privileged phase.

Only the latest release is currently supported with security fixes.
