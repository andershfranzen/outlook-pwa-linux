"""Secure GitHub release checks and downloads for Outlook PWA Linux."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from outlook_pwa_common import VERSION


REPOSITORY = "andershfranzen/outlook-pwa-linux"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
API_VERSION = "2022-11-28"
USER_AGENT = f"outlook-pwa-linux/{VERSION}"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
MAX_API_BYTES = 2 * 1024 * 1024
MAX_CHECKSUM_BYTES = 1024 * 1024
MAX_PACKAGE_BYTES = 250 * 1024 * 1024
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class UpdateError(RuntimeError):
    """An update could not be checked, verified, or installed."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    package: ReleaseAsset
    checksums: ReleaseAsset
    published_at: str

    @property
    def available(self) -> bool:
        return version_tuple(self.version) > version_tuple(VERSION)

    def public_status(self) -> dict[str, object]:
        return {
            "ok": True,
            "currentVersion": VERSION,
            "latestVersion": self.version,
            "updateAvailable": self.available,
            "publishedAt": self.published_at,
        }


class HttpsOnlyRedirectHandler(HTTPRedirectHandler):
    """Reject any HTTPS download that attempts to redirect to another scheme."""

    def redirect_request(self, request, file_pointer, code, message, headers, url):
        if urlparse(url).scheme != "https":
            raise UpdateError("refusing a release redirect that is not HTTPS")
        return super().redirect_request(
            request, file_pointer, code, message, headers, url
        )


HTTPS_OPENER = build_opener(HttpsOnlyRedirectHandler())


def version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        raise UpdateError(f"invalid release version: {version!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _asset_url(version: str, filename: str) -> str:
    return (
        f"https://github.com/{REPOSITORY}/releases/download/"
        f"v{version}/{filename}"
    )


def _parse_digest(value: object, filename: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise UpdateError(f"GitHub did not provide a SHA-256 digest for {filename}")
    digest = value.removeprefix("sha256:").lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise UpdateError(f"GitHub provided an invalid digest for {filename}")
    return digest


def _parse_asset(
    assets: list[object],
    *,
    filename: str,
    version: str,
    maximum_size: int,
) -> ReleaseAsset:
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == filename
    ]
    if len(matches) != 1:
        raise UpdateError(f"release must contain exactly one {filename} asset")
    asset = matches[0]
    if asset.get("state") != "uploaded":
        raise UpdateError(f"release asset is not ready: {filename}")
    url = asset.get("browser_download_url")
    if url != _asset_url(version, filename):
        raise UpdateError(f"release asset has an unexpected URL: {filename}")
    size = asset.get("size")
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 < size <= maximum_size
    ):
        raise UpdateError(f"release asset has an invalid size: {filename}")
    return ReleaseAsset(
        name=filename,
        url=url,
        sha256=_parse_digest(asset.get("digest"), filename),
        size=size,
    )


def parse_release(data: object) -> Release:
    if not isinstance(data, dict):
        raise UpdateError("GitHub returned an invalid release document")
    if data.get("draft") is not False or data.get("prerelease") is not False:
        raise UpdateError("GitHub returned a draft or prerelease")
    if data.get("immutable") is not True:
        raise UpdateError("the latest GitHub release is not immutable")
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise UpdateError("GitHub returned an invalid release tag")
    version = tag[1:]
    version_tuple(version)
    package_name = f"outlook-pwa-linux_{version}_amd64.deb"
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("GitHub returned an invalid release asset list")
    package = _parse_asset(
        assets,
        filename=package_name,
        version=version,
        maximum_size=MAX_PACKAGE_BYTES,
    )
    checksums = _parse_asset(
        assets,
        filename="SHA256SUMS",
        version=version,
        maximum_size=MAX_CHECKSUM_BYTES,
    )
    published_at = data.get("published_at")
    if not isinstance(published_at, str):
        published_at = ""
    return Release(
        version=version,
        tag=tag,
        package=package,
        checksums=checksums,
        published_at=published_at,
    )


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        },
    )


def _read_response(response, maximum_size: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > maximum_size:
                raise UpdateError("GitHub response is larger than allowed")
        except ValueError as error:
            raise UpdateError("GitHub returned an invalid response size") from error
    payload = response.read(maximum_size + 1)
    if len(payload) > maximum_size:
        raise UpdateError("GitHub response is larger than allowed")
    return payload


def fetch_latest_release(
    *,
    api_url: str = RELEASE_API_URL,
    opener=HTTPS_OPENER,
) -> Release:
    if urlparse(api_url).scheme != "https":
        raise UpdateError("release checks require HTTPS")
    try:
        with opener.open(_request(api_url), timeout=15) as response:
            payload = _read_response(response, MAX_API_BYTES)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise UpdateError(f"could not contact GitHub: {error}") from error
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError("GitHub returned invalid release metadata") from error
    return parse_release(data)


def cache_home() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    return base / "outlook-pwa-linux"


def status_cache_path() -> Path:
    return cache_home() / "update-status.json"


def _release_from_cache(data: object) -> Release:
    if not isinstance(data, dict):
        raise UpdateError("invalid update cache")
    package = data.get("package")
    checksums = data.get("checksums")
    if not isinstance(package, dict) or not isinstance(checksums, dict):
        raise UpdateError("invalid update cache")
    return Release(
        version=str(data["version"]),
        tag=str(data["tag"]),
        package=ReleaseAsset(**package),
        checksums=ReleaseAsset(**checksums),
        published_at=str(data.get("published_at", "")),
    )


def _read_cached_release(maximum_age: int) -> Release | None:
    path = status_cache_path()
    try:
        stat = path.stat()
        if time.time() - stat.st_mtime > maximum_age:
            return None
        release = _release_from_cache(json.loads(path.read_text(encoding="utf-8")))
        # Revalidate the cached values through the same strict release parser.
        return parse_release(
            {
                "draft": False,
                "prerelease": False,
                "immutable": True,
                "tag_name": release.tag,
                "published_at": release.published_at,
                "assets": [
                    {
                        "name": asset.name,
                        "browser_download_url": asset.url,
                        "digest": f"sha256:{asset.sha256}",
                        "size": asset.size,
                        "state": "uploaded",
                    }
                    for asset in (release.package, release.checksums)
                ],
            }
        )
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        UpdateError,
    ):
        return None


def _write_cached_release(release: Release) -> None:
    directory = cache_home()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".update-status-", dir=directory
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(asdict(release), stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, status_cache_path())
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def check_for_update(*, force: bool = False) -> Release:
    if not force:
        cached = _read_cached_release(CHECK_INTERVAL_SECONDS)
        if cached:
            return cached
    release = fetch_latest_release()
    _write_cached_release(release)
    return release


def check_status(*, force: bool = False) -> dict[str, object]:
    try:
        return check_for_update(force=force).public_status()
    except UpdateError as error:
        return {
            "ok": False,
            "currentVersion": VERSION,
            "error": str(error),
        }


def _download(asset: ReleaseAsset, destination: Path, *, opener=HTTPS_OPENER) -> None:
    parsed = urlparse(asset.url)
    prefix = f"/{REPOSITORY}/releases/download/v"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.params
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(prefix)
    ):
        raise UpdateError("refusing an unexpected release download URL")
    release_path = parsed.path.removeprefix(prefix)
    try:
        version, filename = release_path.split("/", 1)
    except ValueError as error:
        raise UpdateError("refusing an unexpected release download URL") from error
    version_tuple(version)
    if filename != asset.name or asset.url != _asset_url(version, filename):
        raise UpdateError("refusing an unexpected release download URL")
    if asset.name.startswith("outlook-pwa-linux_") and asset.name != (
        f"outlook-pwa-linux_{version}_amd64.deb"
    ):
        raise UpdateError("release package name does not match its version")
    temporary = destination.with_name(f".{destination.name}.part")
    try:
        digest = hashlib.sha256()
        received = 0
        with opener.open(_request(asset.url), timeout=30) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > asset.size:
                        raise UpdateError(
                            f"download is larger than GitHub reported: {asset.name}"
                        )
                except ValueError as error:
                    raise UpdateError(
                        "GitHub returned an invalid download size"
                    ) from error
            with temporary.open("wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > asset.size:
                        raise UpdateError(
                            f"download is larger than GitHub reported: {asset.name}"
                        )
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        if received != asset.size:
            raise UpdateError(f"download size does not match GitHub: {asset.name}")
        if digest.hexdigest() != asset.sha256:
            raise UpdateError(f"GitHub digest verification failed: {asset.name}")
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise UpdateError(f"could not download {asset.name}: {error}") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _checksum_from_manifest(manifest: str, filename: str) -> str:
    matches: list[str] = []
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].removeprefix("*") == filename:
            matches.append(parts[0].lower())
    if len(matches) != 1 or not SHA256_PATTERN.fullmatch(matches[0]):
        raise UpdateError(f"SHA256SUMS must contain one valid entry for {filename}")
    return matches[0]


def validate_package_fields(package_path: Path, version: str) -> None:
    expected = {
        "Package": "outlook-pwa-linux",
        "Version": version,
        "Architecture": "amd64",
    }
    for field, value in expected.items():
        try:
            result = subprocess.run(
                ("/usr/bin/dpkg-deb", "--field", str(package_path), field),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise UpdateError(
                f"could not inspect the downloaded package: {error}"
            ) from error
        if result.stdout.strip() != value:
            raise UpdateError(f"downloaded package has an unexpected {field.lower()}")


def download_update(release: Release) -> Path:
    if not release.available:
        raise UpdateError("no newer Outlook release is available")
    directory = cache_home() / "updates" / f"v{release.version}"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    package_path = directory / release.package.name
    checksums_path = directory / release.checksums.name
    _download(release.checksums, checksums_path)
    try:
        manifest = checksums_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise UpdateError(f"could not read SHA256SUMS: {error}") from error
    if (
        _checksum_from_manifest(manifest, release.package.name)
        != release.package.sha256
    ):
        raise UpdateError("SHA256SUMS does not match GitHub’s package digest")
    _download(release.package, package_path)
    validate_package_fields(package_path, release.version)
    return package_path


def install_update(release: Release, package_path: Path) -> None:
    helper = Path("/usr/lib/outlook-pwa-linux/outlook-update-helper")
    if not helper.is_file():
        local = Path(__file__).with_name("outlook-update-helper")
        helper = local if local.is_file() else helper
    if not helper.is_file():
        raise UpdateError("the Outlook update helper is not installed")
    try:
        result = subprocess.run(
            (
                "/usr/bin/pkexec",
                str(helper),
                str(package_path),
                release.version,
                release.package.sha256,
            ),
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise UpdateError(f"could not request administrator access: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if result.returncode in {126, 127} or not detail:
            detail = "administrator authentication was cancelled"
        raise UpdateError(detail)


def format_checked_time() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M")
