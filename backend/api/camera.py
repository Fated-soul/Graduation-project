from __future__ import annotations

from collections.abc import Iterator
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import CAMERA_STREAM_URL

router = APIRouter(prefix="/api/camera", tags=["camera"])


def _camera_chunks() -> Iterator[bytes]:
    request = Request(
        CAMERA_STREAM_URL,
        headers={
            "User-Agent": "MingchaCameraProxy/0.1",
            "ngrok-skip-browser-warning": "true",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                yield chunk
    except (OSError, URLError) as exc:
        print("camera stream error:", exc)


@router.get("/info")
def get_camera_info() -> dict[str, str]:
    return {
        "status": "configured",
        "stream_path": "/api/camera/stream",
        "source_url": CAMERA_STREAM_URL,
    }


@router.get("/stream")
def stream_camera() -> StreamingResponse:
    if not CAMERA_STREAM_URL:
        raise HTTPException(status_code=503, detail="camera stream url not configured")

    return StreamingResponse(
        _camera_chunks(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
