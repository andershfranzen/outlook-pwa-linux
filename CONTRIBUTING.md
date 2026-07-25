# Contributing

Thanks for helping improve Outlook for Linux.

## Before opening an issue

- Check existing issues for the same problem.
- Run `outlook-pwa --diagnose` and include the relevant non-sensitive output.
- Never post Microsoft account credentials, cookies, mailbox content, or a
  browser profile.
- Confirm whether the problem also occurs in Outlook on the web.

## Development

Install the build-time tools:

```sh
sudo apt install desktop-file-utils jq shellcheck
```

Then run:

```sh
make release
```

This runs the Python, JavaScript, desktop-entry, shell, package, deterministic
build, verified-download, and tamper-rejection checks.

Keep changes focused and avoid adding Electron or another bundled browser
runtime. The project deliberately uses the system-installed Microsoft Edge
web-app engine.

## Pull requests

- Explain the user-visible behavior and why it belongs in the wrapper.
- Add or update tests for functional changes.
- Update `README.md` or `CHANGELOG.md` when appropriate.
- Keep account-specific paths and generated `build/` or `dist/` files out of
  commits.

All contributions are licensed under the repository's MIT license.
