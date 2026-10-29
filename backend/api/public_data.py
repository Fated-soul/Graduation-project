from __future__ import annotations

from math import isfinite

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse

from backend.api.errors import raise_database_http_exception
from backend.repositories import public_data_repository
from backend.schemas.common import APIResponse
from backend.schemas.public_data import SessionAnalysisRequest, SessionAnnotationCreate
from backend.services import dandi_service, nwb_import_service, video_service


router = APIRouter(prefix="/api/public-data", tags=["public data"])


@router.get("/source", response_model=APIResponse)
def get_source() -> APIResponse:
    try:
        source = public_data_repository.get_source()
    except Exception as exc:
        raise_database_http_exception(exc)
    if source is None:
        return APIResponse(
            message="catalog has not been synchronized",
            data=None,
        )
    return APIResponse(data=source)


@router.get("/stats", response_model=APIResponse)
def get_stats() -> APIResponse:
    try:
        return APIResponse(data=public_data_repository.get_stats())
    except Exception as exc:
        raise_database_http_exception(exc)


@router.post("/sync", response_model=APIResponse)
def sync_catalog(
    limit: int = Query(default=20, ge=1, le=100),
) -> APIResponse:
    try:
        result = dandi_service.sync_catalog(limit)
    except dandi_service.DandiServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="DANDI catalog synchronized", data=result)


@router.get("/subjects", response_model=APIResponse)
def get_subjects() -> APIResponse:
    try:
        return APIResponse(data=public_data_repository.get_subjects())
    except Exception as exc:
        raise_database_http_exception(exc)


@router.get("/subjects/{subject_id}/aligned-timeline", response_model=APIResponse)
def get_aligned_subject_timeline(subject_id: str) -> APIResponse:
    try:
        timeline = public_data_repository.get_aligned_subject_timeline(subject_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if timeline is None:
        raise HTTPException(status_code=404, detail="subject not found")
    return APIResponse(
        message="subject sessions aligned by absolute acquisition time",
        data=timeline,
    )


@router.get("/sessions", response_model=APIResponse)
def get_sessions(
    subject_id: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
) -> APIResponse:
    try:
        sessions = public_data_repository.get_sessions(subject_id, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=sessions)


@router.get("/sessions/{session_id}", response_model=APIResponse)
def get_session(session_id: int) -> APIResponse:
    try:
        session = public_data_repository.get_session(session_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return APIResponse(data=session)


@router.get("/sessions/{session_id}/timeline", response_model=APIResponse)
def get_session_timeline(session_id: int) -> APIResponse:
    try:
        session = public_data_repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        timeline = public_data_repository.get_timeline(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=timeline)


@router.post("/sessions/{session_id}/import", response_model=APIResponse)
def import_session_content(session_id: int) -> APIResponse:
    try:
        result = nwb_import_service.import_session_content(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except nwb_import_service.NWBImportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="session content imported", data=result)


@router.get("/sessions/{session_id}/video")
def open_session_video(session_id: int) -> FileResponse:
    try:
        path = video_service.get_browser_video(session_id)
    except (LookupError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except video_service.VideoConversionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    return FileResponse(path, media_type="video/mp4")


@router.get("/sessions/{session_id}/video/original")
def open_original_session_video(session_id: int) -> RedirectResponse:
    try:
        session = public_data_repository.get_session(session_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not session.get("video_url"):
        raise HTTPException(status_code=404, detail="video is not available for this session")
    return RedirectResponse(str(session["video_url"]), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post(
    "/sessions/{session_id}/annotations",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    session_id: int,
    request: SessionAnnotationCreate,
) -> APIResponse:
    try:
        session = public_data_repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        if request.timestamp_seconds is not None:
            duration = session.get("duration_seconds")
            if duration is None or not isfinite(float(duration)) or float(duration) < 0:
                raise HTTPException(
                    status_code=422,
                    detail="会话时长尚未确定，请先载入会话内容，或保存不指定时间的复核记录。",
                )
            if request.timestamp_seconds > float(duration):
                raise HTTPException(status_code=422, detail="复核时间不能超过会话时长。")
        annotation = public_data_repository.create_annotation(
            session_id, request.model_dump()
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="annotation stored", data=annotation)


@router.delete(
    "/sessions/{session_id}/annotations/{annotation_id}",
    response_model=APIResponse,
)
def delete_annotation(session_id: int, annotation_id: int) -> APIResponse:
    try:
        annotation = public_data_repository.delete_annotation(
            session_id,
            annotation_id,
        )
    except Exception as exc:
        raise_database_http_exception(exc)
    if annotation is None:
        raise HTTPException(status_code=404, detail="annotation not found")
    return APIResponse(message="annotation deleted", data=annotation)


@router.post("/sessions/{session_id}/analysis", response_model=APIResponse)
def analyze_session(
    session_id: int,
    request: SessionAnalysisRequest,
) -> APIResponse:
    try:
        analysis = dandi_service.build_session_analysis(
            session_id,
            request.question,
            use_llm=request.use_llm,
            model=request.model,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="session evidence analyzed", data=analysis)


@router.get("/sessions/{session_id}/analyses", response_model=APIResponse)
def get_session_analyses(
    session_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
) -> APIResponse:
    try:
        analyses = public_data_repository.get_analyses(session_id, limit, before_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=analyses)


@router.post(
    "/sessions/{session_id}/analyses/{analysis_id}/follow-up",
    response_model=APIResponse,
)
def follow_up_session_analysis(
    session_id: int,
    analysis_id: int,
    request: SessionAnalysisRequest,
) -> APIResponse:
    try:
        analysis = dandi_service.build_session_analysis(
            session_id,
            request.question,
            use_llm=request.use_llm,
            model=request.model,
            parent_analysis_id=analysis_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="follow-up analysis completed", data=analysis)

