from __future__ import annotations

from datetime import datetime, timezone

import h5py
import numpy as np

from backend.services.dandi_service import _analysis_question_with_context, _parse_nwb_asset
from backend.services.nwb_import_service import (
    _attach_absolute_times,
    _read_modeling_events,
    _read_signal_evidence,
)


def _asset(path: str, variables: list[str]) -> dict:
    return {
        "id": "dandiasset:test-asset",
        "identifier": "test-asset",
        "path": path,
        "contentSize": 123,
        "contentUrl": ["https://example.test/file.nwb"],
        "variableMeasured": [{"value": value} for value in variables],
        "wasGeneratedBy": [{"schemaKey": "Session", "startDate": "2023-01-16T18:47:57-05:00"}],
        "wasAttributedTo": [
            {
                "schemaKey": "Participant", "identifier": "Ca-EEG3-4",
                "sex": {"name": "Male"}, "species": {"name": "Mus musculus"},
            }
        ],
    }


def test_parse_fear_conditioning_asset() -> None:
    parsed = _parse_nwb_asset(
        _asset(
            "sub-Ca-EEG3-4/sub-Ca-EEG3-4_ses-FC_image+ophys.nwb",
            ["OnePhotonSeries", "PlaneSegmentation", "RoiResponseSeries"],
        )
    )
    assert parsed["subject"]["subject_id"] == "Ca-EEG3-4"
    assert parsed["session_id"] == "Ca-EEG3-4-FC"
    assert parsed["session_type"] == "fear_conditioning"
    assert parsed["has_shock"] is True
    assert parsed["has_freezing"] is True
    assert parsed["has_calcium"] is True


def test_parse_offline_asset_marks_sleep_and_ephys() -> None:
    parsed = _parse_nwb_asset(
        _asset(
            "sub-Ca-EEG3-4/sub-Ca-EEG3-4_ses-OfflineDay1Session1_image+ophys.nwb",
            ["OnePhotonSeries", "ElectricalSeries"],
        )
    )
    assert parsed["session_type"] == "offline_consolidation"
    assert parsed["has_eeg"] is True
    assert parsed["has_emg"] is True
    assert parsed["has_sleep_states"] is True


def test_follow_up_question_keeps_previous_decision_context() -> None:
    prompt = _analysis_question_with_context(
        "哪些行为片段仍需人工复核？",
        {
            "question": "本次造模反应是否充分？",
            "summary": "刺激后冻结行为增加。",
            "evidence": ["记录到三次足底电击。"],
            "recommendation": "复核刺激后的行为视频。",
        },
    )

    assert "上一条问题：本次造模反应是否充分？" in prompt
    assert "上一条结论：刺激后冻结行为增加。" in prompt
    assert "本次追问：哪些行为片段仍需人工复核？" in prompt


def test_nwb_events_and_processed_signals_are_imported(tmp_path) -> None:
    path = tmp_path / "multimodal.nwb"
    with h5py.File(path, "w") as nwb:
        intervals = nwb.create_group("intervals")
        shocks = intervals.create_group("ShockStimuli")
        shocks.create_dataset("start_time", data=np.array([120.0, 180.0]))
        shocks.create_dataset("stop_time", data=np.array([122.0, 182.0]))
        shocks.create_dataset("shock_amplitude", data=np.array([0.25, 0.25]))
        freezing = intervals.create_group("FreezingIntervals")
        freezing.create_dataset("start_time", data=np.array([130.0, 190.0]))
        freezing.create_dataset("stop_time", data=np.array([135.0, 196.0]))

        processing = nwb.create_group("processing")
        ophys = processing.create_group("ophys")
        fluorescence = ophys.create_group("Fluorescence")
        calcium = fluorescence.create_group("Deconvolved")
        calcium.create_dataset("data", data=np.arange(120, dtype=float).reshape(30, 4))
        calcium.create_dataset("timestamps", data=np.linspace(0, 29, 30))
        behavior = processing.create_group("behavior")
        motion = behavior.create_group("MotionSeries")
        motion.create_dataset("data", data=np.linspace(0, 1, 30))
        motion.create_dataset("timestamps", data=np.linspace(0, 29, 30))

    with h5py.File(path, "r") as nwb:
        events = _read_modeling_events(nwb, 100)
        windows, roi_metrics = _read_signal_evidence(nwb, max_windows=10, max_rois=4)

    assert [item["event_type"] for item in events].count("electric_shock") == 2
    assert [item["event_type"] for item in events].count("freezing") == 2
    assert {item["modality"] for item in windows} == {"calcium", "motion"}
    assert len(roi_metrics) == 4
    assert all(item["sample_count"] > 0 for item in windows)


def test_offline_signals_sleep_labels_and_absolute_times(tmp_path) -> None:
    path = tmp_path / "offline.nwb"
    with h5py.File(path, "w") as nwb:
        acquisition = nwb.create_group("acquisition")
        for name in ("EEGSignal", "EMGSignal", "ActivitySignal"):
            signal = acquisition.create_group(name)
            data = signal.create_dataset("data", data=np.linspace(0, 1, 1000))
            data.attrs["unit"] = "volts" if name != "ActivitySignal" else "n.a."
            starting_time = signal.create_dataset("starting_time", data=0.0)
            starting_time.attrs["rate"] = 500.0

        processing = nwb.create_group("processing")
        sleep = processing.create_group("sleep")
        intervals = sleep.create_group("SleepIntervals")
        intervals.create_dataset("start_time", data=np.array([0.0, 1.0]))
        intervals.create_dataset("stop_time", data=np.array([1.0, 2.0]))
        intervals.create_dataset("sleep_state", data=np.array([b"quiet wake", b"rem"]))
        ophys = processing.create_group("ophys")
        fluorescence = ophys.create_group("Fluorescence")
        calcium = fluorescence.create_group("Deconvolved")
        calcium.create_dataset("data", data=np.arange(80, dtype=float).reshape(20, 4))
        calcium.create_dataset("timestamps", data=np.linspace(0, 1.9, 20))

    with h5py.File(path, "r") as nwb:
        events = _read_modeling_events(
            nwb,
            100,
            session_type="offline_consolidation",
        )
        followup_events = _read_modeling_events(
            nwb,
            100,
            session_type="longitudinal_followup",
        )
        windows, _ = _read_signal_evidence(
            nwb,
            max_windows=10,
            max_rois=4,
            session_type="offline_consolidation",
        )
        assert followup_events == events

    reference = datetime(2022, 9, 19, 13, 30, tzinfo=timezone.utc)
    _attach_absolute_times(events, windows, timestamps_reference_at=reference)

    assert {item["event_label"] for item in events} == {"安静清醒", "快速眼动睡眠"}
    assert {item["modality"] for item in windows} == {"calcium", "motion", "eeg", "emg"}
    assert next(item for item in windows if item["modality"] == "eeg")["unit"] == "volts"
    assert events[1]["event_started_at"] == reference.replace(minute=30, second=1)
    assert min(item["window_started_at"] for item in windows) == reference
