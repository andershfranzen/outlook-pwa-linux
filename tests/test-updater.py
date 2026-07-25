#!/usr/bin/python3
"""Unit and tamper tests for the in-app updater."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import outlook_pwa_updater as updater  # noqa: E402

helper_loader = importlib.machinery.SourceFileLoader(
    "outlook_update_helper",
    str(PROJECT_ROOT / "src" / "outlook-update-helper"),
)
helper_spec = importlib.util.spec_from_loader(helper_loader.name, helper_loader)
assert helper_spec is not None
helper = importlib.util.module_from_spec(helper_spec)
helper_loader.exec_module(helper)


def asset(name: str, version: str, payload: bytes) -> dict[str, object]:
    return {
        "name": name,
        "browser_download_url": (
            "https://github.com/andershfranzen/outlook-pwa-linux/"
            f"releases/download/v{version}/{name}"
        ),
        "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
        "size": len(payload),
        "state": "uploaded",
    }


def release_document(version: str = "0.3.1") -> dict[str, object]:
    package_name = f"outlook-pwa-linux_{version}_amd64.deb"
    package = b"test Debian package"
    checksums = (
        f"{hashlib.sha256(package).hexdigest()}  {package_name}\n".encode()
    )
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "immutable": True,
        "published_at": "2026-07-25T12:00:00Z",
        "assets": [
            asset(package_name, version, package),
            asset("SHA256SUMS", version, checksums),
        ],
    }


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = io.BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)


class FakeOpener:
    def __init__(self, payload: bytes):
        self.payload = payload

    def open(self, _request, timeout: int):
        self.timeout = timeout
        return FakeResponse(self.payload)


class UpdaterTests(unittest.TestCase):
    def test_version_comparison_is_numeric(self) -> None:
        self.assertGreater(
            updater.version_tuple("0.10.0"),
            updater.version_tuple("0.9.9"),
        )
        with self.assertRaises(updater.UpdateError):
            updater.version_tuple("0.3")
        with self.assertRaises(updater.UpdateError):
            updater.version_tuple("0.3.1-beta")

    def test_valid_immutable_release(self) -> None:
        release = updater.parse_release(release_document())
        self.assertEqual(release.version, "0.3.1")
        self.assertTrue(release.available)
        self.assertEqual(
            release.package.name,
            "outlook-pwa-linux_0.3.1_amd64.deb",
        )

    def test_current_or_older_release_is_not_an_update(self) -> None:
        self.assertFalse(updater.parse_release(release_document("0.3.0")).available)
        self.assertFalse(updater.parse_release(release_document("0.2.9")).available)

    def test_mutable_release_is_rejected(self) -> None:
        document = release_document()
        document["immutable"] = False
        with self.assertRaisesRegex(updater.UpdateError, "not immutable"):
            updater.parse_release(document)

    def test_wrong_asset_url_is_rejected(self) -> None:
        document = release_document()
        document["assets"][0]["browser_download_url"] = (  # type: ignore[index]
            "https://example.com/update.deb"
        )
        with self.assertRaisesRegex(updater.UpdateError, "unexpected URL"):
            updater.parse_release(document)

    def test_missing_digest_is_rejected(self) -> None:
        document = release_document()
        document["assets"][0]["digest"] = None  # type: ignore[index]
        with self.assertRaisesRegex(updater.UpdateError, "did not provide"):
            updater.parse_release(document)

    def test_api_payload_is_parsed(self) -> None:
        payload = json.dumps(release_document()).encode()
        release = updater.fetch_latest_release(
            opener=FakeOpener(payload),
        )
        self.assertEqual(release.version, "0.3.1")

    def test_verified_download_is_written_atomically(self) -> None:
        payload = b"verified update bytes"
        name = "outlook-pwa-linux_0.3.1_amd64.deb"
        release_asset = updater.ReleaseAsset(
            name=name,
            url=(
                "https://github.com/andershfranzen/outlook-pwa-linux/"
                f"releases/download/v0.3.1/{name}"
            ),
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / name
            updater._download(  # noqa: SLF001 - targeted integrity test
                release_asset,
                destination,
                opener=FakeOpener(payload),
            )
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_tampered_download_is_rejected_and_removed(self) -> None:
        expected = b"expected update"
        tampered = b"tampered update"
        name = "outlook-pwa-linux_0.3.1_amd64.deb"
        release_asset = updater.ReleaseAsset(
            name=name,
            url=(
                "https://github.com/andershfranzen/outlook-pwa-linux/"
                f"releases/download/v0.3.1/{name}"
            ),
            sha256=hashlib.sha256(expected).hexdigest(),
            size=len(tampered),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / name
            with self.assertRaisesRegex(updater.UpdateError, "digest"):
                updater._download(  # noqa: SLF001
                    release_asset,
                    destination,
                    opener=FakeOpener(tampered),
                )
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name(f".{name}.part").exists())

    def test_checksum_manifest_must_have_one_matching_entry(self) -> None:
        digest = "a" * 64
        self.assertEqual(
            updater._checksum_from_manifest(  # noqa: SLF001
                f"{digest}  update.deb\n",
                "update.deb",
            ),
            digest,
        )
        with self.assertRaises(updater.UpdateError):
            updater._checksum_from_manifest(  # noqa: SLF001
                f"{digest}  update.deb\n{digest}  update.deb\n",
                "update.deb",
            )

    def test_privileged_copy_rechecks_size_and_digest(self) -> None:
        payload = b"release package bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "update.deb"
            source.write_bytes(payload)
            copied = helper.copy_verified(source, digest, len(payload))
            try:
                self.assertEqual(copied.read_bytes(), payload)
                self.assertEqual(copied.stat().st_mode & 0o777, 0o600)
            finally:
                copied.unlink(missing_ok=True)

    def test_privileged_copy_rejects_wrong_size(self) -> None:
        payload = b"release package bytes"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "update.deb"
            source.write_bytes(payload)
            with self.assertRaisesRegex(updater.UpdateError, "size"):
                helper.copy_verified(
                    source,
                    hashlib.sha256(payload).hexdigest(),
                    len(payload) + 1,
                )

    def test_privileged_copy_does_not_follow_symlinks(self) -> None:
        payload = b"release package bytes"
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real.deb"
            source = Path(directory) / "update.deb"
            real.write_bytes(payload)
            source.symlink_to(real)
            with self.assertRaises(OSError):
                helper.copy_verified(
                    source,
                    hashlib.sha256(payload).hexdigest(),
                    len(payload),
                )


if __name__ == "__main__":
    unittest.main()
