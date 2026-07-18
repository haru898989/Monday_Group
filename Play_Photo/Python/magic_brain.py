"""Magic Photo Museum の写真理解・Unity連携JSON生成モジュール。

演出はUnity側の責務とし、このモジュールは重要度、位置関係、場面スコアなど
写真から推定できる認識情報だけを生成する。
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from recognition_config import (
    CANONICAL_NAME_MAP,
    CATEGORY_IMPORTANCE,
    CATEGORY_MAP,
    IMPORTANCE_WEIGHTS,
    NAME_IMPORTANCE_OVERRIDES,
    RELATION_IMPORTANCE_SATURATION,
    RELATION_IMPORTANCE_WEIGHTS,
    RELATION_THRESHOLDS,
    SCENE_RULES,
)


SCENE_ORDER: tuple[str, ...] = (
    "indoor", "outdoor", "home", "office", "restaurant", "classroom",
    "park", "nature", "food_scene", "animal_scene", "transportation_scene",
    "entertainment_scene", "night_scene", "unknown",
)

HOLDABLE_NAMES = {
    "phone", "camera", "cup", "bottle", "book", "notebook", "paper",
    "ice cream", "cake", "apple", "banana", "pizza", "bread", "food", "drink",
    "toy", "ball", "balloon", "microphone", "musical instrument", "guitar",
}

HOLDING_EXCLUDED_CATEGORIES = {
    "human", "furniture", "nature", "water", "structure", "vehicle",
    "transportation_infrastructure", "indoor_fixture", "light",
}

USABLE_CATEGORIES = {"electronics", "entertainment", "education"}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def _read(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    text = re.sub(r"\s*-\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def _canonicalize(value: Any) -> str:
    name = _normalize_name(value)
    return CANONICAL_NAME_MAP.get(name, name or "unknown")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _normalize_name(value)
        if text and text not in result:
            result.append(text)
    return result


def _input_list(objects: Any) -> list[Any]:
    if objects is None:
        return []
    if isinstance(objects, (str, bytes, Mapping)):
        return [objects]
    try:
        return list(objects)
    except TypeError:
        return [objects]


def _box_values(obj: Any) -> tuple[float, float, float, float] | None:
    box = _read(obj, "box", None)
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    values = tuple(_finite_float(value, float("nan")) for value in box)
    if not all(math.isfinite(value) for value in values):
        return None
    return values  # type: ignore[return-value]


def _positive_dimension(value: Any) -> int:
    number = _finite_float(value, 0.0)
    return int(round(number)) if number > 0 else 0


def _valid_object_id(value: Any) -> int | None:
    """UnityのInt32へ安全に入る正の整数IDだけを受理する。"""
    if value is None or isinstance(value, bool):
        return None
    number = _finite_float(value, float("nan"))
    if not math.isfinite(number) or not number.is_integer():
        return None
    integer = int(number)
    return integer if 1 <= integer <= 2_147_483_647 else None


def _number(value: float, digits: int = 4) -> int | float:
    rounded = round(value, digits)
    return int(rounded) if rounded.is_integer() else rounded


def _intersection_area(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = first["box"]
    bx1, by1, bx2, by2 = second["box"]
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0.0, min(ay2, by2) - max(ay1, by1)
    )


def _iou(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    intersection = _intersection_area(first, second)
    union = first["width"] * first["height"] + second["width"] * second["height"] - intersection
    return 0.0 if union <= 0 else _clamp(intersection / union)


def _edge_gap(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = first["box"]
    bx1, by1, bx2, by2 = second["box"]
    horizontal = max(bx1 - ax2, ax1 - bx2, 0.0)
    vertical = max(by1 - ay2, ay1 - by2, 0.0)
    return math.hypot(horizontal, vertical)


def _json_safe(value: Any) -> Any:
    """任意のdebug入力もNaN/Infinityを含まないJSON標準型へ変換する。"""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


class MagicBrain:
    """検出物体からUnity向けの写真理解JSONを生成する。"""

    schema_version = "1.0"

    def analyze(
        self,
        objects: Any,
        image_width: int | None = None,
        image_height: int | None = None,
        image_path: str | Path | None = None,
        debug: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """検出結果を解析し、JSONシリアライズ可能な辞書を返す。

        Mapping、DetectedObject、文字列、空入力を受け付け、入力自体は変更しない。
        """
        source_objects = _input_list(objects)
        warnings: list[str] = []

        width = _positive_dimension(image_width)
        height = _positive_dimension(image_height)
        valid_source_boxes = [box for item in source_objects if (box := _box_values(item))]
        if width <= 0 and valid_source_boxes:
            width = max(1, int(math.ceil(max(max(box[0], box[2]) for box in valid_source_boxes))))
            warnings.append("image_widthが未指定のため、検出boxから推定しました。")
        if height <= 0 and valid_source_boxes:
            height = max(1, int(math.ceil(max(max(box[1], box[3]) for box in valid_source_boxes))))
            warnings.append("image_heightが未指定のため、検出boxから推定しました。")

        enriched: list[dict[str, Any]] = []
        used_ids: set[int] = set()
        next_id = 1
        for source in source_objects:
            raw_requested_id = _read(source, "object_id", None)
            requested_id = _valid_object_id(raw_requested_id)
            if raw_requested_id is not None and requested_id is None:
                warnings.append(f"不正なobject_id={raw_requested_id!r}を再採番しました。")
            if requested_id is None or requested_id in used_ids:
                if requested_id in used_ids:
                    warnings.append(f"重複したobject_id={requested_id}を再採番しました。")
                while next_id in used_ids:
                    next_id += 1
                object_id = next_id
            else:
                object_id = requested_id
            used_ids.add(object_id)
            while next_id in used_ids:
                next_id += 1
            enriched.append(
                self._enrich_object(source, object_id, width, height, warnings)
            )

        relations, relation_strengths = self._build_relations(enriched, width, height)

        for item in enriched:
            relation_strength = sum(relation_strengths[item["object_id"]].values())
            importance = self._importance(item, relation_strength)
            item["importance"] = importance
            item["importance_score"] = importance

        ranked = sorted(
            enriched,
            key=lambda item: (-item["importance"], -item["confidence"], item["object_id"]),
        )
        main_objects = [
            {
                "object_id": item["object_id"],
                "name": item["canonical_name"],
                "importance": item["importance"],
            }
            for item in ranked[:3]
        ]

        scene_scores = self._scene_scores(enriched)
        primary_scene = self._primary_scene(scene_scores)
        debug_result = self._debug_result(debug, warnings)
        categories = sorted({item["category"] for item in enriched if item["category"] != "unknown"})

        result = {
            "schema_version": self.schema_version,
            "image": {
                "path": str(image_path or ""),
                "width": width,
                "height": height,
                "coordinate_space": "analysis_image",
            },
            "scene": {"primary": primary_scene, "scores": scene_scores},
            "main_objects": main_objects,
            "objects": enriched,
            "relations": relations,
            "summary": {
                "object_count": len(enriched),
                "has_person": any(item["category"] == "human" for item in enriched),
                "categories": categories,
            },
            "debug": debug_result,
        }
        return _json_safe(result)

    def _enrich_object(
        self,
        source: Any,
        object_id: int,
        image_width: int,
        image_height: int,
        warnings: list[str],
    ) -> dict[str, Any]:
        raw_name = source if isinstance(source, str) else _read(source, "name", "")
        raw_canonical = _read(source, "canonical_name", "") or raw_name or _read(source, "original_name", "")
        canonical_name = _canonicalize(raw_canonical)
        original_name = str(
            _read(source, "original_name", "") or raw_name or canonical_name
        ).strip()
        raw_aliases = _read(source, "aliases", [])
        if not isinstance(raw_aliases, (list, tuple, set)):
            raw_aliases = [raw_aliases]
        aliases = _unique_strings([canonical_name, original_name, *raw_aliases])
        category = CATEGORY_MAP.get(canonical_name, "unknown")

        raw_confidence = _read(source, "confidence", None)
        confidence = _clamp(_finite_float(raw_confidence, 0.0))
        if raw_confidence is None or not math.isfinite(_finite_float(raw_confidence, float("nan"))):
            warnings.append(f"object_id={object_id}: confidence欠損または不正値を0.0にしました。")

        geometry = self._geometry(source, object_id, image_width, image_height, warnings)
        return {
            "object_id": object_id,
            "canonical_name": canonical_name,
            "original_name": original_name,
            "aliases": aliases,
            "category": category,
            "confidence": round(confidence, 6),
            **geometry,
            "importance": 0.0,
            "importance_score": 0.0,
        }

    def _geometry(
        self,
        source: Any,
        object_id: int,
        image_width: int,
        image_height: int,
        warnings: list[str],
    ) -> dict[str, Any]:
        values = _box_values(source)
        invalid = {
            "box": [], "center": [], "normalized_center": [], "normalized_box": [],
            "width": 0, "height": 0, "area_ratio": 0.0,
            "horizontal_position": "unknown", "vertical_position": "unknown",
            "geometry_valid": False,
        }
        if values is None:
            warnings.append(f"object_id={object_id}: box欠損または不正値のため位置関係から除外しました。")
            return invalid
        if image_width <= 0 or image_height <= 0:
            warnings.append(f"object_id={object_id}: 画像サイズ不明のためboxを正規化できません。")
            return invalid

        raw_x1, raw_y1, raw_x2, raw_y2 = values
        if raw_x1 > raw_x2 or raw_y1 > raw_y2:
            warnings.append(f"object_id={object_id}: 逆転したbox座標を並べ替えました。")
        x1, x2 = sorted((raw_x1, raw_x2))
        y1, y2 = sorted((raw_y1, raw_y2))
        clipped = (
            _clamp(x1, 0.0, float(image_width)),
            _clamp(y1, 0.0, float(image_height)),
            _clamp(x2, 0.0, float(image_width)),
            _clamp(y2, 0.0, float(image_height)),
        )
        if clipped != (x1, y1, x2, y2):
            warnings.append(f"object_id={object_id}: boxを画像範囲内へ補正しました。")
        x1, y1, x2, y2 = clipped
        object_width = x2 - x1
        object_height = y2 - y1
        if object_width <= 0 or object_height <= 0:
            warnings.append(f"object_id={object_id}: 面積0のboxを位置関係から除外しました。")
            return invalid

        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        normalized_x = _clamp(center_x / image_width)
        normalized_y = _clamp(center_y / image_height)
        area_ratio = _clamp((object_width * object_height) / (image_width * image_height))
        horizontal = "left" if normalized_x < 1 / 3 else ("center" if normalized_x < 2 / 3 else "right")
        vertical = "top" if normalized_y < 1 / 3 else ("middle" if normalized_y < 2 / 3 else "bottom")
        return {
            "box": [_number(x1), _number(y1), _number(x2), _number(y2)],
            "center": [_number(center_x), _number(center_y)],
            "normalized_center": [round(normalized_x, 6), round(normalized_y, 6)],
            "normalized_box": [
                round(x1 / image_width, 6), round(y1 / image_height, 6),
                round(x2 / image_width, 6), round(y2 / image_height, 6),
            ],
            "width": _number(object_width),
            "height": _number(object_height),
            "area_ratio": round(area_ratio, 8),
            "horizontal_position": horizontal,
            "vertical_position": vertical,
            "geometry_valid": True,
        }

    def _build_relations(
        self,
        objects: list[dict[str, Any]],
        image_width: int,
        image_height: int,
    ) -> tuple[list[dict[str, Any]], dict[int, dict[int, float]]]:
        if image_width <= 0 or image_height <= 0:
            return [], {item["object_id"]: {} for item in objects}
        valid = [item for item in objects if item["geometry_valid"]]
        relation_map: dict[tuple[int, int, str], float] = {}

        def add(subject_id: int, object_id: int, relation_type: str, score: float) -> None:
            if subject_id == object_id:
                return
            key = (subject_id, object_id, relation_type)
            relation_map[key] = max(relation_map.get(key, 0.0), _clamp(score))

        image_diagonal = max(1.0, math.hypot(image_width, image_height))
        near_threshold = float(RELATION_THRESHOLDS["near_distance_ratio"])
        far_threshold = float(RELATION_THRESHOLDS["far_distance_ratio"])
        direction_threshold = float(RELATION_THRESHOLDS["direction_offset_ratio"])
        overlap_threshold = float(RELATION_THRESHOLDS["overlap_iou"])
        overlap_smaller_threshold = float(RELATION_THRESHOLDS["overlap_smaller_area_ratio"])
        containment_threshold = float(RELATION_THRESHOLDS["containment_ratio"])
        direction_min_confidence = float(RELATION_THRESHOLDS["direction_min_confidence"])

        for first_index, first in enumerate(valid):
            for second in valid[first_index + 1:]:
                first_id, second_id = first["object_id"], second["object_id"]
                intersection = _intersection_area(first, second)
                iou = _iou(first, second)
                first_area = first["width"] * first["height"]
                second_area = second["width"] * second["height"]
                first_cover = intersection / first_area if first_area > 0 else 0.0
                second_cover = intersection / second_area if second_area > 0 else 0.0
                smaller_cover = intersection / min(first_area, second_area) if min(first_area, second_area) > 0 else 0.0
                confidence_signal = math.sqrt(first["confidence"] * second["confidence"])
                salient_pair = (
                    confidence_signal >= direction_min_confidence
                    or first["canonical_name"] == "person"
                    or second["canonical_name"] == "person"
                )

                contained = False
                if first_cover >= containment_threshold and first_area < second_area * 0.95:
                    score = 0.75 * first_cover + 0.25 * confidence_signal
                    add(first_id, second_id, "inside", score)
                    add(second_id, first_id, "contains", score)
                    contained = True
                elif second_cover >= containment_threshold and second_area < first_area * 0.95:
                    score = 0.75 * second_cover + 0.25 * confidence_signal
                    add(second_id, first_id, "inside", score)
                    add(first_id, second_id, "contains", score)
                    contained = True

                if iou >= overlap_threshold or smaller_cover >= overlap_smaller_threshold:
                    overlap_strength = max(min(1.0, iou / 0.35), smaller_cover)
                    overlap_score = 0.75 * overlap_strength + 0.25 * confidence_signal
                    add(first_id, second_id, "overlap", overlap_score)

                dx = second["center"][0] - first["center"][0]
                dy = second["center"][1] - first["center"][1]
                center_distance_ratio = math.hypot(dx, dy) / image_diagonal
                gap_ratio = _edge_gap(first, second) / image_diagonal
                gap_threshold = near_threshold * 0.25
                center_near_strength = 1.0 - min(center_distance_ratio, near_threshold) / max(near_threshold, 1e-9)
                gap_near_strength = 1.0 - min(gap_ratio, gap_threshold) / max(gap_threshold, 1e-9)
                if center_distance_ratio <= near_threshold or gap_ratio <= gap_threshold:
                    near_strength = max(center_near_strength, gap_near_strength)
                    subject, target = (first, second)
                    if second["canonical_name"] == "person" and first["canonical_name"] != "person":
                        subject, target = second, first
                    add(subject["object_id"], target["object_id"], "near", 0.75 * near_strength + 0.25 * confidence_signal)
                elif (
                    salient_pair and not contained and iou == 0.0
                    and center_distance_ratio >= far_threshold
                ):
                    far_strength = (center_distance_ratio - far_threshold) / max(1e-9, 1.0 - far_threshold)
                    add(first_id, second_id, "far", 0.75 * far_strength + 0.25 * confidence_signal)

                if not contained and salient_pair:
                    normalized_dx = abs(dx) / image_width
                    normalized_dy = abs(dy) / image_height
                    width_threshold = max(
                        direction_threshold,
                        0.25 * ((first["width"] + second["width"]) / image_width),
                    )
                    height_threshold = max(
                        direction_threshold,
                        0.25 * ((first["height"] + second["height"]) / image_height),
                    )
                    horizontal_strength = normalized_dx / max(width_threshold, 1e-9)
                    vertical_strength = normalized_dy / max(height_threshold, 1e-9)
                    # 対角配置でも、差がより明確な主軸方向だけを返してJSON肥大化を防ぐ。
                    if horizontal_strength >= 1.0 and horizontal_strength >= vertical_strength:
                        left, right = (first, second) if dx > 0 else (second, first)
                        score = 0.75 * min(1.0, normalized_dx / 0.5) + 0.25 * confidence_signal
                        add(left["object_id"], right["object_id"], "left_of", score)
                        add(right["object_id"], left["object_id"], "right_of", score)
                    elif vertical_strength >= 1.0:
                        above, below = (first, second) if dy > 0 else (second, first)
                        score = 0.75 * min(1.0, normalized_dy / 0.5) + 0.25 * confidence_signal
                        add(above["object_id"], below["object_id"], "above", score)
                        add(below["object_id"], above["object_id"], "below", score)

        self._add_person_object_relations(valid, image_diagonal, add)
        priority = {
            "holding_candidate": 0, "using_candidate": 1, "in_front_of": 2,
            "inside": 3, "contains": 4, "overlap": 5, "near": 6,
            "left_of": 7, "right_of": 8, "above": 9, "below": 10, "far": 11,
        }
        rows = [
            {"subject_id": key[0], "object_id": key[1], "type": key[2], "score": round(score, 4)}
            for key, score in relation_map.items()
        ]
        # importanceはJSON出力上限の影響を受けないよう、cap前の全関係から集計する。
        relation_strengths: dict[int, dict[int, float]] = {
            item["object_id"]: {} for item in objects
        }
        for row in rows:
            subject_id = row["subject_id"]
            object_id = row["object_id"]
            weight = RELATION_IMPORTANCE_WEIGHTS.get(row["type"], 0.0)
            strength = weight * row["score"]
            relation_strengths[subject_id][object_id] = max(
                relation_strengths[subject_id].get(object_id, 0.0), strength
            )
            relation_strengths[object_id][subject_id] = max(
                relation_strengths[object_id].get(subject_id, 0.0), strength
            )
        # 上限時も同一物体ペアの逆関係をできるだけまとめて残す。
        groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for row in rows:
            pair = tuple(sorted((row["subject_id"], row["object_id"])))
            groups.setdefault(pair, []).append(row)
        ordered_groups = sorted(
            groups.values(),
            key=lambda group: (
                min(priority.get(row["type"], 99) for row in group),
                -max(row["score"] for row in group),
                min(row["subject_id"] for row in group),
                min(row["object_id"] for row in group),
            ),
        )
        maximum = int(RELATION_THRESHOLDS["max_relations"])
        selected: list[dict[str, Any]] = []
        for group in ordered_groups:
            group.sort(key=lambda row: (priority.get(row["type"], 99), -row["score"], row["subject_id"], row["object_id"]))
            remaining = maximum - len(selected)
            if remaining <= 0:
                break
            if len(group) > remaining:
                continue
            selected.extend(group)
        selected.sort(key=lambda row: (priority.get(row["type"], 99), -row["score"], row["subject_id"], row["object_id"]))
        return selected, relation_strengths

    def _add_person_object_relations(
        self,
        objects: list[dict[str, Any]],
        image_diagonal: float,
        add: Any,
    ) -> None:
        persons = [item for item in objects if item["canonical_name"] == "person"]
        non_persons = [item for item in objects if item["canonical_name"] != "person"]
        holding_by_object: dict[int, list[tuple[float, int]]] = {}

        for person in persons:
            person_area = person["width"] * person["height"]
            person_diagonal = max(1.0, math.hypot(person["width"], person["height"]))
            px1, py1, _, _ = person["box"]
            for item in non_persons:
                item_area = item["width"] * item["height"]
                size_ratio = item_area / person_area if person_area > 0 else 1.0
                intersection = _intersection_area(person, item)
                inside_ratio = intersection / item_area if item_area > 0 else 0.0
                gap_ratio = _edge_gap(person, item) / person_diagonal
                rx = (item["center"][0] - px1) / max(1.0, person["width"])
                ry = (item["center"][1] - py1) / max(1.0, person["height"])
                zone_x = _clamp(1.0 - max(0.0, abs(rx - 0.5) - 0.5) / 0.25)
                zone_y = _clamp(1.0 - abs(ry - 0.60) / 0.50)
                zone = zone_x * zone_y
                proximity = max(inside_ratio, 1.0 - _clamp(gap_ratio / 0.20))
                confidence_signal = math.sqrt(person["confidence"] * item["confidence"])

                holdability = 1.0 if item["canonical_name"] in HOLDABLE_NAMES else 0.55
                holding_allowed = (
                    item["category"] not in HOLDING_EXCLUDED_CATEGORIES
                    and item["canonical_name"] not in {"display", "computer"}
                )
                if size_ratio < 0.002:
                    size_signal = math.sqrt(max(0.0, size_ratio) / 0.002)
                elif size_ratio <= 0.20:
                    size_signal = 1.0
                else:
                    size_signal = _clamp((0.40 - size_ratio) / 0.20)
                holding_score = (
                    0.25 * proximity + 0.20 * inside_ratio + 0.20 * zone
                    + 0.15 * size_signal + 0.10 * holdability + 0.10 * confidence_signal
                )
                if (
                    holding_allowed and 0.0005 <= size_ratio <= 0.40
                    and (inside_ratio >= 0.15 or gap_ratio <= 0.08)
                    and zone >= 0.35 and holding_score >= 0.60
                ):
                    holding_by_object.setdefault(item["object_id"], []).append(
                        (holding_score, person["object_id"])
                    )

                center_distance = math.dist(person["center"], item["center"]) / image_diagonal
                if item["category"] in USABLE_CATEGORIES and (center_distance <= 0.30 or inside_ratio > 0.0):
                    using_score = 0.55 * proximity + 0.25 * confidence_signal + 0.20 * min(1.0, inside_ratio)
                    if using_score >= 0.45:
                        add(person["object_id"], item["object_id"], "using_candidate", using_score)

                if inside_ratio > 0.15 and 0.0 < size_ratio < 0.80:
                    front_score = 0.65 * inside_ratio + 0.20 * zone + 0.15 * confidence_signal
                    add(item["object_id"], person["object_id"], "in_front_of", front_score)

        # 1つの物体を複数人が持つ判定になった場合は、最高scoreの人物だけへ割り当てる。
        for object_id, candidates in holding_by_object.items():
            score, person_id = max(candidates)
            add(person_id, object_id, "holding_candidate", score)

    def _importance(self, item: Mapping[str, Any], relation_strength: float) -> float:
        confidence_signal = _clamp(float(item["confidence"]))
        area_signal = min(1.0, math.sqrt(max(0.0, float(item["area_ratio"])) / 0.20))
        if item["normalized_center"]:
            nx, ny = item["normalized_center"]
            center_signal = 1.0 - _clamp(math.hypot(nx - 0.5, ny - 0.5) / math.sqrt(0.5))
        else:
            center_signal = 0.0
        category_signal = NAME_IMPORTANCE_OVERRIDES.get(
            str(item["canonical_name"]),
            CATEGORY_IMPORTANCE.get(str(item["category"]), CATEGORY_IMPORTANCE["unknown"]),
        )
        relation_signal = min(1.0, relation_strength / RELATION_IMPORTANCE_SATURATION)
        score = (
            IMPORTANCE_WEIGHTS["confidence"] * confidence_signal
            + IMPORTANCE_WEIGHTS["area"] * area_signal
            + IMPORTANCE_WEIGHTS["center"] * center_signal
            + IMPORTANCE_WEIGHTS["category"] * category_signal
            + IMPORTANCE_WEIGHTS["relations"] * relation_signal
        )
        return round(_clamp(score), 4)

    def _scene_scores(self, objects: list[dict[str, Any]]) -> dict[str, float]:
        evidence_by_name: dict[str, list[float]] = {}
        for item in objects:
            area_signal = min(1.0, math.sqrt(max(0.0, item["area_ratio"]) / 0.10))
            evidence = item["confidence"] * (0.65 + 0.35 * area_signal)
            evidence_by_name.setdefault(item["canonical_name"], []).append(evidence)

        grouped: dict[str, float] = {}
        for name, values in evidence_by_name.items():
            ordered = sorted(values, reverse=True)
            grouped[name] = min(0.98, ordered[0] + 0.15 * sum(ordered[1:]))

        raw_scores: dict[str, float] = {}
        for scene_name, rule in SCENE_RULES.items():
            remaining = 1.0
            category_weights = rule.get("categories", {})
            name_weights = rule.get("names", {})
            for canonical_name, evidence in grouped.items():
                category = CATEGORY_MAP.get(canonical_name, "unknown")
                weight = max(
                    float(category_weights.get(category, 0.0)),
                    float(name_weights.get(canonical_name, 0.0)),
                )
                if weight > 0.0:
                    remaining *= 1.0 - min(0.95, evidence * weight)
            raw_scores[scene_name] = _clamp(1.0 - remaining)

        def evidence(name: str) -> float:
            return grouped.get(name, 0.0)

        def any_evidence(*names: str) -> float:
            return max((evidence(name) for name in names), default=0.0)

        synergies = {
            "office": any_evidence("display", "computer", "laptop") * any_evidence("desk", "keyboard") * 0.25,
            "restaurant": any_evidence("food", "ice cream", "cake", "pizza") * any_evidence("table", "cup", "chair") * 0.25,
            "classroom": evidence("whiteboard") * any_evidence("desk", "chair", "book") * 0.30,
            "park": any_evidence("tree", "grass") * any_evidence("person", "dog", "ball") * 0.20,
            "transportation_scene": any_evidence("vehicle", "car", "bus", "train", "bicycle") * evidence("road") * 0.20,
            "home": any_evidence("bed", "sofa") * raw_scores.get("indoor", 0.0) * 0.20,
        }
        for scene_name, synergy in synergies.items():
            base = raw_scores.get(scene_name, 0.0)
            raw_scores[scene_name] = 1.0 - (1.0 - base) * (1.0 - _clamp(synergy))
        if evidence("sun") > 0.0:
            raw_scores["night_scene"] *= 1.0 - 0.8 * evidence("sun")

        max_known = max(raw_scores.values(), default=0.0)
        raw_scores["unknown"] = 1.0 if not objects or max_known == 0.0 else _clamp(1.0 - max_known / 0.45)
        return {scene: round(_clamp(raw_scores.get(scene, 0.0)), 4) for scene in SCENE_ORDER}

    @staticmethod
    def _primary_scene(scores: Mapping[str, float]) -> str:
        known = [(scene, scores.get(scene, 0.0)) for scene in SCENE_ORDER if scene != "unknown"]
        best_scene, best_score = max(known, key=lambda item: (item[1], -SCENE_ORDER.index(item[0])))
        return "unknown" if best_score < 0.25 else best_scene

    @staticmethod
    def _debug_result(debug: Mapping[str, Any] | None, warnings: list[str]) -> dict[str, Any]:
        source = debug if isinstance(debug, Mapping) else {}
        source_warnings = source.get("warnings", [])
        if not isinstance(source_warnings, list):
            source_warnings = [source_warnings]
        return {
            "removed_duplicates": _json_safe(source.get("removed_duplicates", [])),
            "removed_low_confidence": _json_safe(source.get("removed_low_confidence", [])),
            "removed_invalid": _json_safe(source.get("removed_invalid", [])),
            "warnings": _json_safe([*source_warnings, *warnings]),
        }

    @staticmethod
    def save_json(
        result: Mapping[str, Any],
        output_path: str | Path = "analysis_result.json",
        atomic: bool = True,
    ) -> Path:
        """UTF-8 JSONを保存する。atomic時はtmp完成後にWindows対応で置換する。"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_result = _json_safe(dict(result))
        if not atomic:
            with path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(safe_result, file, ensure_ascii=False, allow_nan=False, indent=2)
                file.write("\n")
            return path

        temporary_path = path.with_suffix(".tmp")
        if temporary_path == path:
            temporary_path = path.with_name(f"{path.name}.writing")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(safe_result, file, ensure_ascii=False, allow_nan=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            last_error: OSError | None = None
            for delay in (0.0, 0.05, 0.10):
                if delay:
                    time.sleep(delay)
                try:
                    os.replace(temporary_path, path)
                    return path
                except OSError as error:
                    last_error = error
            if last_error is not None:
                raise last_error
        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return path


def main() -> None:
    """YOLOを起動せず写真理解と安全なJSON保存を確認する。"""
    sample_objects = [
        {"name": "human", "confidence": 0.90, "box": [80, 60, 360, 700]},
        {"name": "ice cream", "confidence": 0.82, "box": [210, 360, 280, 500]},
        {"name": "monitor", "confidence": 0.76, "box": [500, 180, 850, 470]},
    ]
    brain = MagicBrain()
    result = brain.analyze(
        sample_objects,
        image_width=900,
        image_height=800,
        image_path="sample.jpg",
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    saved_path = brain.save_json(result, "analysis_result.json")
    print(f"保存先: {saved_path.resolve()}")


if __name__ == "__main__":
    main()
