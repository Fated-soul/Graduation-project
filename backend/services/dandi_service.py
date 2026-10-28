from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.config import (
    DANDI_API_URL,
    DANDI_DANDISET_ID,
    DANDI_REQUEST_TIMEOUT_SECONDS,
    DANDI_SOURCE_KEY,
    DANDI_VERSION,
)
from backend.repositories import public_data_repository


class DandiServiceError(RuntimeError):
    pass


SESSION_PROFILES: dict[str, tuple[str, str, str]] = {
    "NeutralExposure": ("neutral_exposure", "基线适应", "中性环境基线暴露"),
    "FC": ("fear_conditioning", "恐惧条件化造模", "足底电击条件化造模"),
    "Recall1": ("recall_assessment", "记忆回忆评估", "造模后第 1 次回忆评估"),
    "Recall2": ("recall_assessment", "记忆回忆评估", "造模后第 2 次回忆评估"),
    "Recall3": ("recall_assessment", "记忆回忆评估", "造模后第 3 次回忆评估"),
    "Week": ("longitudinal_followup", "跨周随访", "跨周神经活动与睡眠随访"),
}


def sync_catalog(limit: int = 20) -> dict[str, Any]:
    source = public_data_repository.upsert_source(_source_payload(status="syncing"))
    try:
        assets = _list_assets("*.nwb", limit)
        imported: list[dict[str, Any]] = []
        for asset in assets:
            detail = _asset_detail(_asset_identifier(asset))
            session_data = _parse_nwb_asset(detail)
            video = _find_video(str(detail.get("path") or ""))
            if video:
                session_data.update(
                    {
                        "has_video": True,
                        "video_asset_id": _asset_identifier(video),
                        "video_path": video.get("path"),
                        "video_url": _content_url(video),
                        "video_size_bytes": video.get("contentSize") or video.get("size"),
                    }
                )

            subject_data = session_data.pop("subject")
            subject = public_data_repository.upsert_subject(
                int(source["id"]), subject_data
            )
            stored = public_data_repository.upsert_session(
                int(source["id"]), int(subject["id"]), session_data
            )
            public_data_repository.upsert_session_asset(
                int(stored["id"]),
                {
                    "asset_id": session_data["nwb_asset_id"],
                    "asset_role": "nwb",
                    "path": session_data["nwb_path"],
                    "content_url": session_data["nwb_url"],
                    "size_bytes": session_data.get("nwb_size_bytes"),
                    "media_type": "application/x-nwb",
                    "metadata": {"variables": session_data["metadata"].get("variables", [])},
                },
            )
            if video:
                public_data_repository.upsert_session_asset(
                    int(stored["id"]),
                    {
                        "asset_id": session_data["video_asset_id"],
                        "asset_role": "behavior_video",
                        "path": session_data["video_path"],
                        "content_url": session_data["video_url"],
                        "size_bytes": session_data.get("video_size_bytes"),
                        "media_type": "video/x-ms-wmv",
                        "metadata": {},
                    },
                )
            imported.append(stored)

        source = public_data_repository.upsert_source(_source_payload(status="available"))
        return {
            "source": source,
            "synced_sessions": len(imported),
            "sessions": imported,
        }
    except Exception as exc:
        public_data_repository.set_source_status(DANDI_SOURCE_KEY, "error", str(exc))
        if isinstance(exc, DandiServiceError):
            raise
        raise DandiServiceError(str(exc)) from exc


def _source_payload(status: str) -> dict[str, Any]:
    return {
        "source_key": DANDI_SOURCE_KEY,
        "provider": "DANDI Archive",
        "external_id": DANDI_DANDISET_ID,
        "version": DANDI_VERSION,
        "title": "Offline ensemble co-reactivation links memories across days",
        "description": (
            "小鼠恐惧条件化与记忆连接研究，包含行为视频、冻结行为、足底电击、"
            "单光子钙成像、细胞分割、睡眠状态、EEG 和 EMG。"
        ),
        "license": "CC-BY-4.0",
        "landing_url": f"https://dandiarchive.org/dandiset/{DANDI_DANDISET_ID}/{DANDI_VERSION}",
        "api_url": (
            f"{DANDI_API_URL}/api/dandisets/{DANDI_DANDISET_ID}/versions/{DANDI_VERSION}/"
        ),
        "asset_count": 20,
        "total_size_bytes": 40_600_000_000,
        "status": status,
        "metadata": {
            "access": "open",
            "subject_count": 2,
            "paper_doi": "10.1038/s41586-024-08168-4",
            "tutorial_url": (
                "https://docs.dandiarchive.org/example-notebooks/000718/"
                "CaiLab/zaki_2024/000718_demo/"
            ),
            "modalities": [
                "behavior_video", "freezing", "electric_shock", "calcium_imaging",
                "cell_segmentation", "sleep_state", "eeg", "emg",
            ],
            "catalog_strategy": "metadata_first",
        },
    }


def _get_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MingchaShuhao/2.0 DANDI-000718-client",
        },
    )
    try:
        with urlopen(request, timeout=DANDI_REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise DandiServiceError(f"DANDI request failed: {exc}") from exc
    if not isinstance(data, dict):
        raise DandiServiceError("DANDI returned an unexpected response")
    return data


def _list_assets(glob: str, limit: int) -> list[dict[str, Any]]:
    params = urlencode({"glob": glob, "page_size": min(max(limit, 1), 100)})
    url = (
        f"{DANDI_API_URL}/api/dandisets/{DANDI_DANDISET_ID}/versions/"
        f"{DANDI_VERSION}/assets/?{params}"
    )
    results: list[dict[str, Any]] = []
    while url and len(results) < limit:
        payload = _get_json(url)
        results.extend(
            item for item in (payload.get("results") or []) if isinstance(item, dict)
        )
        url = str(payload.get("next") or "")
    return sorted(results[:limit], key=lambda item: str(item.get("path") or ""))


def _asset_identifier(asset: dict[str, Any]) -> str:
    value = asset.get("asset_id") or asset.get("identifier") or asset.get("id")
    if not value and isinstance(asset.get("metadata"), dict):
        value = asset["metadata"].get("identifier") or asset["metadata"].get("id")
    identifier = str(value or "").removeprefix("dandiasset:")
    if not identifier:
        raise DandiServiceError("DANDI asset has no identifier")
    return identifier


def _asset_detail(asset_id: str) -> dict[str, Any]:
    return _get_json(f"{DANDI_API_URL}/api/assets/{asset_id}/")


def _find_video(nwb_path: str) -> dict[str, Any] | None:
    if not nwb_path.endswith(".nwb") or "image+ophys" not in nwb_path:
        return None
    candidates = _list_assets(f"{nwb_path[:-4]}/*.wmv", 1)
    return _asset_detail(_asset_identifier(candidates[0])) if candidates else None


def _content_url(asset: dict[str, Any], *, prefer_download: bool = False) -> str:
    urls = asset.get("contentUrl") or []
    if isinstance(urls, str):
        urls = [urls]
    urls = [str(url) for url in urls if url]
    if not urls:
        return f"{DANDI_API_URL}/api/assets/{_asset_identifier(asset)}/download/"
    if prefer_download:
        return next((url for url in urls if "/download/" in url), urls[0])
    return next((url for url in urls if "s3.amazonaws.com" in url), urls[0])


def _parse_nwb_asset(asset: dict[str, Any]) -> dict[str, Any]:
    path = str(asset.get("path") or "")
    subject_match = re.search(r"(?:^|/)sub-([^/]+)", path)
    session_match = re.search(r"_ses-([^_/.]+)", path)
    subject_code = subject_match.group(1) if subject_match else "unknown"
    session_code = session_match.group(1) if session_match else _asset_identifier(asset)
    attributed = asset.get("wasAttributedTo") or []
    participant = next(
        (
            item for item in attributed
            if isinstance(item, dict) and item.get("schemaKey") == "Participant"
        ),
        {},
    )
    generated = asset.get("wasGeneratedBy") or []
    session_meta = next(
        (
            item for item in generated
            if isinstance(item, dict) and item.get("schemaKey") == "Session"
        ),
        {},
    )
    variables = [
        str(item.get("value"))
        for item in (asset.get("variableMeasured") or [])
        if isinstance(item, dict) and item.get("value")
    ]
    session_type, stage, fallback_description = _session_profile(session_code)
    is_offline = session_type in {"offline_consolidation", "longitudinal_followup"}
    has_calcium = "ophys" in path.lower() or any(
        value in {"OnePhotonSeries", "PlaneSegmentation", "RoiResponseSeries"}
        for value in variables
    )
    has_freezing = session_type in {
        "neutral_exposure", "fear_conditioning", "recall_assessment"
    }
    sex = participant.get("sex") or {}
    species = participant.get("species") or {}
    age = participant.get("age") or {}
    return {
        "subject": {
            "subject_id": subject_code,
            "species": species.get("name") if isinstance(species, dict) else species,
            "sex": sex.get("name") if isinstance(sex, dict) else sex,
            "age": age.get("value") if isinstance(age, dict) else age,
            "description": f"DANDI 000718 实验动物 {subject_code}，C57BL/6J 野生型小鼠",
            "metadata": {
                "participant": participant,
                "strain": "C57BL/6J",
                "genotype": "wild-type",
            },
        },
        "session_id": f"{subject_code}-{session_code}",
        "session_started_at": session_meta.get("startDate"),
        "timestamps_reference_at": session_meta.get("startDate"),
        "time_reference": "session_start",
        "description": session_meta.get("description") or fallback_description,
        "session_type": session_type,
        "modeling_stage": stage,
        "has_video": False,
        "has_behavior": has_freezing or session_type == "fear_conditioning" or is_offline,
        "has_neural": has_calcium or is_offline,
        "has_calcium": has_calcium,
        "has_freezing": has_freezing,
        "has_shock": session_type == "fear_conditioning",
        "has_eeg": is_offline,
        "has_emg": is_offline,
        "has_sleep_states": is_offline,
        "import_status": "catalogued",
        "nwb_asset_id": _asset_identifier(asset),
        "nwb_path": path,
        "nwb_url": _content_url(asset),
        "nwb_size_bytes": asset.get("contentSize") or asset.get("size"),
        "metadata": {
            "session_code": session_code,
            "variables": variables,
            "keywords": [str(item) for item in (asset.get("keywords") or [])],
            "encoding_format": asset.get("encodingFormat"),
            "published_at": asset.get("datePublished"),
        },
    }


def _session_profile(session_code: str) -> tuple[str, str, str]:
    if session_code.startswith("Offline"):
        return ("offline_consolidation", "离线记忆巩固", "造模后的睡眠与神经重激活记录")
    return SESSION_PROFILES.get(
        session_code,
        ("other", "其他研究阶段", f"实验会话 {session_code}"),
    )


def build_session_analysis(
    session_pk: int,
    question: str,
    *,
    use_llm: bool = True,
    model: str | None = None,
    parent_analysis_id: int | None = None,
) -> dict[str, Any]:
    session = public_data_repository.get_session(session_pk)
    if session is None:
        raise LookupError("session not found")
    parent_analysis = None
    if parent_analysis_id is not None:
        parent_analysis = public_data_repository.get_analysis(
            session_pk,
            parent_analysis_id,
        )
        if parent_analysis is None:
            raise LookupError("analysis record not found")
    timeline = public_data_repository.get_timeline(session_pk)
    events = timeline["modeling_events"]
    signals = timeline["signal_windows"]
    annotations = timeline["annotations"]
    roi_metrics = timeline["roi_metrics"]
    event_types = {str(item.get("event_type")) for item in events}
    modalities = {str(item.get("modality")) for item in signals}
    event_labels = {
        "electric_shock": "足底电击", "freezing": "冻结行为",
        "sleep_state": "睡眠状态", "behavior_state": "行为状态",
        "experiment_phase": "实验阶段",
    }
    modality_labels = {
        "calcium": "钙活动", "motion": "运动强度",
        "eeg": "EEG", "emg": "EMG",
    }
    evidence = [
        f"实验动物：{session['subject_code']}",
        f"造模阶段：{session.get('modeling_stage') or '未记录'}",
        f"采集开始：{session.get('timestamps_reference_at') or session.get('session_started_at') or '未记录'}",
        f"已载入造模与行为事件 {len(events)} 条，多模态信号窗 {len(signals)} 个",
        f"事件覆盖：{'、'.join(event_labels.get(item, item) for item in sorted(event_types)) if event_types else '无'}",
        f"信号覆盖：{'、'.join(modality_labels.get(item, item) for item in sorted(modalities)) if modalities else '无'}",
        f"钙成像 ROI 指标 {len(roi_metrics)} 个，人工复核 {len(annotations)} 条",
    ]
    session_type = str(session.get("session_type") or "")
    stage_descriptions = {
        "neutral_exposure": (
            "本次为基线适应会话。",
            "优先复核基线阶段的冻结行为、运动与钙活动，为后续造模和回忆评估提供参照；"
            "不要把基线观察直接解释为刺激后的造模效果。",
        ),
        "fear_conditioning": (
            "本次为恐惧条件化（FC）会话。",
            "在已记录足底电击的前提下，复核刺激前后冻结行为、运动与钙活动的变化；"
            "缺少电击记录时先核对原始数据，不推定刺激发生时间。",
        ),
        "recall_assessment": (
            "本次为记忆回忆评估会话。",
            "优先复核回忆阶段的冻结行为与钙活动，并与同一动物的基线及造模会话进行会话级比较；"
            "不把回忆阶段直接当成电击条件化阶段。",
        ),
        "offline_consolidation": (
            "本次为离线巩固会话。",
            "按本次会话实际包含的睡眠或清醒标签、脑电、肌电和钙活动开展复核；"
            "与 FC 比较时保留真实采集时刻与间隔，不将非同期的相同相对秒数直接对应。",
        ),
        "longitudinal_followup": (
            "本次为跨周随访会话。",
            "按实际可用模态检查跨周变化及记录完整性，保持真实采集时间；"
            "不将随访默认解释为 FC 刺激或完整睡眠记录。",
        ),
    }
    stage_intro, recommendation = stage_descriptions.get(
        session_type,
        ("本次为其他研究阶段会话。", "先核对研究阶段和实际证据覆盖，再进行会话内复核或会话级比较。"),
    )
    if events or signals:
        shock_count = sum(item.get("event_type") == "electric_shock" for item in events)
        freezing_seconds = sum(
            max(0.0, float(item.get("stop_time_seconds") or 0) - float(item.get("start_time_seconds") or 0))
            for item in events if item.get("event_type") == "freezing"
        )
        evidence.append(f"记录足底电击 {shock_count} 次，冻结行为累计 {freezing_seconds:.1f} 秒")
        if session_type == "offline_consolidation":
            sleep_events = [item for item in events if item.get("event_type") == "sleep_state"]
            sleep_seconds = sum(
                max(
                    0.0,
                    float(item.get("stop_time_seconds") or 0)
                    - float(item.get("start_time_seconds") or 0),
                )
                for item in sleep_events
            )
            evidence.append(f"睡眠与清醒状态共 {len(sleep_events)} 段，累计覆盖 {sleep_seconds / 60:.1f} 分钟")
        coverage = [event_labels.get(item, item) for item in sorted(event_types)]
        coverage += [modality_labels.get(item, item) for item in sorted(modalities)]
        expected = {
            "fear_conditioning": {"electric_shock", "freezing", "calcium"},
            "neutral_exposure": {"freezing", "calcium"},
            "recall_assessment": {"freezing", "calcium"},
            "offline_consolidation": {"sleep_state", "eeg", "emg", "calcium"},
        }.get(session_type, set())
        missing = expected - event_types - modalities
        missing_labels = [event_labels.get(item, modality_labels.get(item, item)) for item in sorted(missing)]
        summary = stage_intro + f"当前已载入{'、'.join(coverage)}，可在本次会话内复核已有证据。"
        if missing_labels:
            summary += f"当前尚未记录{'、'.join(missing_labels)}，不能当作相应证据已完整载入。"
        summary += "本地评估不代替造模效果的人工判断。"
        confidence = 0.6 if missing else 0.86
    else:
        summary = stage_intro + "当前尚无已载入的事件或信号，不能形成造模效果判断。"
        recommendation = "先核对并载入本阶段的实际会话内容，再开展多模态联合复核。"
        confidence = 0.52
    result = {
        "question": question,
        "parent_analysis_id": parent_analysis_id,
        "summary": summary,
        "evidence": evidence,
        "recommendation": recommendation,
        "confidence": confidence,
        "analysis_source": "multimodal_modeling_evidence",
        "model_name": None,
        "knowledge_sources": [],
        "retrieval_mode": "not_used",
    }
    if use_llm:
        try:
            from backend.services import agent_service

            agent_question = _analysis_question_with_context(
                question,
                parent_analysis,
            )
            upstream = agent_service.analyze_dataset_session(
                session_pk, question=agent_question, model=model
            )
            generated = upstream.get("data")
            if isinstance(generated, dict):
                result.update(
                    {
                        "summary": generated.get("summary") or summary,
                        "evidence": generated.get("evidence") or evidence,
                        "recommendation": generated.get("recommendation") or recommendation,
                        "confidence": generated.get("confidence", confidence),
                        "analysis_source": generated.get("analysis_source")
                        or "bailian_multimodal_modeling_agent",
                        "model_name": generated.get("model_name") or model,
                        "knowledge_sources": generated.get("knowledge_sources") or [],
                        "retrieval_mode": generated.get("retrieval_mode") or "disabled",
                    }
                )
        except Exception:
            pass
    return public_data_repository.create_analysis(session_pk, result)


def _analysis_question_with_context(
    question: str,
    parent_analysis: dict[str, Any] | None,
) -> str:
    if parent_analysis is None:
        return question
    evidence = parent_analysis.get("evidence") or []
    evidence_text = "\n".join(f"- {item}" for item in evidence)[:3000]
    return (
        "这是对上一条辅助决策的追问。请结合原决策上下文和当前会话数据，"
        "直接回答追问；如果追问超出当前证据范围，请明确说明。\n\n"
        f"上一条问题：{str(parent_analysis.get('question') or '综合评估')[:1500]}\n"
        f"上一条结论：{str(parent_analysis.get('summary') or '')[:2500]}\n"
        f"上一条判断依据：\n{evidence_text}\n"
        f"上一条建议：{str(parent_analysis.get('recommendation') or '')[:1800]}\n\n"
        f"本次追问：{question}"
    )
