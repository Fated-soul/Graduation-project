from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import json
import re
import subprocess
from threading import Lock
from urllib.request import Request, urlopen

import imageio_ffmpeg

from backend.repositories import public_data_repository


VIDEO_CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "videos"
_LOCKS: dict[int, Lock] = {}
_LOCKS_GUARD = Lock()


class VideoConversionError(RuntimeError):
    pass


def get_browser_video(session_pk: int) -> Path:
    session = public_data_repository.get_session(session_pk)
    if session is None:
        raise LookupError("session not found")
    video_url = str(session.get("video_url") or "")
    if not video_url:
        raise FileNotFoundError("video is not available for this session")

    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = _safe_name(
        f"{session.get('session_id') or session_pk}-{session.get('video_asset_id') or 'video'}"
    )
    target = VIDEO_CACHE_DIR / f"{cache_key}.mp4"
    if target.is_file() and target.stat().st_size > 0:
        return target

    lock = _session_lock(session_pk)
    with lock:
        if target.is_file() and target.stat().st_size > 0:
            return target
        source = VIDEO_CACHE_DIR / f"{cache_key}.wmv.part"
        converted = VIDEO_CACHE_DIR / f"{cache_key}.mp4.part"
        try:
            _download(
                _direct_video_url(video_url, session.get("video_asset_id")),
                source,
                expected_size=session.get("video_size_bytes"),
            )
            _transcode(source, converted)
            os.replace(converted, target)
        except Exception as exc:
            source.unlink(missing_ok=True)
            converted.unlink(missing_ok=True)
            if isinstance(exc, VideoConversionError):
                raise
            raise VideoConversionError(f"video conversion failed: {exc}") from exc
        finally:
            source.unlink(missing_ok=True)
        return target


def _download(url: str, target: Path, *, expected_size: object = None) -> None:
    try:
        total_size = int(expected_size or 0)
    except (TypeError, ValueError):
        total_size = 0
    if total_size <= 0:
        request = Request(
            url,
            headers={"Range": "bytes=0-0", "User-Agent": "MingchaShuhao/3.0 video-cache"},
        )
        with urlopen(request, timeout=30) as response:
            content_range = str(response.headers.get("Content-Range") or "")
            total_size = int(content_range.rsplit("/", 1)[-1]) if "/" in content_range else 0
    if total_size <= 0:
        raise VideoConversionError("cannot determine source video size")

    # DANDI's public S3 endpoint is more reliable here with modest range reads.
    chunk_size = 1024 * 1024
    ranges = [
        (start, min(total_size - 1, start + chunk_size - 1))
        for start in range(0, total_size, chunk_size)
    ]
    with ThreadPoolExecutor(max_workers=4) as executor, target.open("wb") as output:
        for payload in executor.map(lambda bounds: _fetch_range(url, *bounds), ranges):
            output.write(payload)
    if target.stat().st_size == 0:
        raise VideoConversionError("downloaded video is empty")


def _fetch_range(url: str, start: int, end: int) -> bytes:
    last_error: Exception | None = None
    for _attempt in range(3):
        request = Request(
            url,
            headers={
                "Range": f"bytes={start}-{end}",
                "User-Agent": "MingchaShuhao/3.0 video-cache",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = response.read()
            expected = end - start + 1
            if len(payload) == expected:
                return payload
            last_error = VideoConversionError(
                f"incomplete range {start}-{end}: {len(payload)} of {expected} bytes"
            )
        except Exception as exc:
            last_error = exc
    raise VideoConversionError(f"cannot download video range {start}-{end}: {last_error}")


def _direct_video_url(stored_url: str, asset_id: object) -> str:
    """Prefer DANDI's S3 object URL; the API download redirect can stall media clients."""
    identifier = str(asset_id or "").strip()
    if not identifier:
        return stored_url
    detail_url = f"https://api.dandiarchive.org/api/assets/{identifier}/"
    request = Request(detail_url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            detail = json.loads(response.read().decode("utf-8"))
        urls = detail.get("contentUrl") or []
        direct = next((str(url) for url in urls if "s3.amazonaws.com" in str(url)), None)
        return direct or stored_url
    except Exception:
        return stored_url


def _transcode(source: Path, target: Path) -> None:
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "25",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(target),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "unknown ffmpeg error").strip()
        raise VideoConversionError(detail[-1200:])


def _session_lock(session_pk: int) -> Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(session_pk, Lock())


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-_") or "session-video"
