from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.database.init_db import init_database
from backend.repositories import vision_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "real_keypoints.csv"


def _find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    raise ValueError(f"CSV missing required column, expected one of: {', '.join(candidates)}")


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _normalize_keypoint_values(
    x: float | None,
    y: float | None,
    confidence: float | None,
) -> tuple[float | None, float | None, float | None]:
    if x == -1 and y == -1:
        x = None
        y = None
    if confidence is not None and not 0 <= confidence <= 1:
        confidence = None
    return x, y, confidence


def _to_int(value: str | None) -> int:
    if value is None or value == "":
        raise ValueError("frame value is empty")
    return int(float(value))


def _source_animal_to_mouse_id(source_animal_id: str) -> str:
    # 视觉端 animal0 对应实验鼠 mouse1，也就是数据库里的 MOUSE-001。
    animal_match = re.fullmatch(r"animal(\d+)", source_animal_id.strip(), flags=re.IGNORECASE)
    if animal_match:
        return f"MOUSE-{int(animal_match.group(1)) + 1:03d}"

    mouse_match = re.fullmatch(r"mouse[-_ ]?(\d+)", source_animal_id.strip(), flags=re.IGNORECASE)
    if mouse_match:
        return f"MOUSE-{int(mouse_match.group(1)):03d}"

    return source_animal_id.strip().upper()


def _recorded_at_from_frame(frame_index: int, fps: float, anchor: datetime) -> datetime:
    return anchor + timedelta(seconds=frame_index / fps)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _build_frame_features(
    grouped_keypoints: dict[tuple[str, str, int], list[dict[str, Any]]],
    source_file: str,
) -> list[tuple[Any, ...]]:
    features: list[tuple[Any, ...]] = []
    previous_centers: dict[tuple[str, str], tuple[float, float]] = {}

    for mouse_id, source_animal_id, frame_index in sorted(grouped_keypoints):
        keypoints = grouped_keypoints[(mouse_id, source_animal_id, frame_index)]
        confidences = [
            point["confidence"]
            for point in keypoints
            if point["confidence"] is not None
        ]
        center_point = next(
            (
                point
                for point in keypoints
                if point["keypoint_name"] == "mouse_center"
                and point["x"] is not None
                and point["y"] is not None
            ),
            None,
        )
        if center_point is None:
            xs = [point["x"] for point in keypoints if point["x"] is not None]
            ys = [point["y"] for point in keypoints if point["y"] is not None]
            center_x = _mean(xs)
            center_y = _mean(ys)
        else:
            center_x = center_point["x"]
            center_y = center_point["y"]

        previous_center = previous_centers.get((mouse_id, source_animal_id))
        movement_distance = None
        if previous_center is not None and center_x is not None and center_y is not None:
            movement_distance = math.dist(previous_center, (center_x, center_y))
        if center_x is not None and center_y is not None:
            previous_centers[(mouse_id, source_animal_id)] = (center_x, center_y)

        recorded_at = keypoints[0]["recorded_at"]
        features.append(
            (
                mouse_id,
                source_animal_id,
                frame_index,
                center_x,
                center_y,
                movement_distance,
                _mean(confidences),
                len(keypoints),
                source_file,
                recorded_at,
            )
        )

    return features


def load_keypoints_from_csv(csv_path: Path, fps: float) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[str]]:
    source_file = csv_path.name
    anchor = datetime.now(timezone.utc)
    keypoint_rows: list[tuple[Any, ...]] = []
    grouped_keypoints: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    mouse_ids: set[str] = set()

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        frame_col = _find_column(fieldnames, ("frame", "frame_index"))
        animal_col = _find_column(fieldnames, ("individual", "animal_id", "animal", "track_id"))
        keypoint_col = _find_column(fieldnames, ("bodypart", "keypoint", "keypoint_name"))
        x_col = _find_column(fieldnames, ("x", "x_coord"))
        y_col = _find_column(fieldnames, ("y", "y_coord"))
        confidence_col = _find_column(fieldnames, ("likelihood", "confidence", "score"))

        for row in reader:
            frame_index = _to_int(row.get(frame_col))
            source_animal_id = str(row.get(animal_col) or "").strip()
            keypoint_name = str(row.get(keypoint_col) or "").strip()
            if not source_animal_id or not keypoint_name:
                continue

            mouse_id = _source_animal_to_mouse_id(source_animal_id)
            mouse_ids.add(mouse_id)
            x = _to_float(row.get(x_col))
            y = _to_float(row.get(y_col))
            confidence = _to_float(row.get(confidence_col))
            x, y, confidence = _normalize_keypoint_values(x, y, confidence)
            recorded_at = _recorded_at_from_frame(frame_index, fps, anchor)

            keypoint_rows.append(
                (
                    mouse_id,
                    source_animal_id,
                    frame_index,
                    keypoint_name,
                    x,
                    y,
                    confidence,
                    source_file,
                    recorded_at,
                )
            )
            grouped_keypoints[(mouse_id, source_animal_id, frame_index)].append(
                {
                    "keypoint_name": keypoint_name,
                    "x": x,
                    "y": y,
                    "confidence": confidence,
                    "recorded_at": recorded_at,
                }
            )

    feature_rows = _build_frame_features(grouped_keypoints, source_file)
    return keypoint_rows, feature_rows, sorted(mouse_ids)


def import_vision_csv(csv_path: Path, fps: float) -> dict[str, Any]:
    if not csv_path.exists():
        raise FileNotFoundError(f"vision csv not found: {csv_path}")
    if fps <= 0:
        raise ValueError("fps must be greater than 0")

    if not init_database():
        raise RuntimeError("database initialization failed")

    keypoint_rows, feature_rows, mouse_ids = load_keypoints_from_csv(csv_path, fps)
    vision_repository.ensure_animals(mouse_ids)
    keypoint_count = vision_repository.bulk_upsert_keypoints(keypoint_rows)
    feature_count = vision_repository.bulk_upsert_frame_features(feature_rows)

    return {
        "source_file": csv_path.name,
        "keypoint_rows": keypoint_count,
        "feature_rows": feature_count,
        "mouse_ids": mouse_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import vision keypoint CSV into PostgreSQL.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to vision CSV file. Default: data/real_keypoints.csv",
    )
    parser.add_argument("--fps", type=float, default=30.0, help="Frame rate used to derive recorded_at.")
    args = parser.parse_args()

    try:
        result = import_vision_csv(args.csv.resolve(), args.fps)
    except Exception as exc:
        print("vision data import failed:", exc)
        return 1

    print("vision data imported successfully")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
