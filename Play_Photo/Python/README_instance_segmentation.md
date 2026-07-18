# Magic Photo instance segmentation implementation

## File relationship

- `demo_magic_photo_complete.py`, `ml_detector_complete.py`, and
  `semantic_segmentation_multi.py` are the currently working implementation.
  They are imported and reused, but are not modified by this implementation.
- `demo_magic_photo_complete_original.py`,
  `ml_detector_complete_original.py`, and
  `semantic_segmentation_multi_original.py` are snapshots made before this
  implementation.
- `demo_magic_photo_instance_segmentation.py` is the new GUI entry point.
- `ml_detector_instance_segmentation.py` is the new instance analysis, mask
  saving, JSON export, and click-selection pipeline.
- `object_segmentation.py` is the replaceable object-mask interface and the
  current DeepLabV3/VOC plus YOLO-box implementation.

No existing Python file is deleted, moved, or overwritten.

## Data flow

1. The original image is loaded with the existing Unicode/EXIF-aware loader.
2. YOLO-World detects per-object names, confidence values, and rough boxes.
3. DeepLabV3 creates one semantic map at the original image resolution.
4. `segment_object(...)` intersects the applicable semantic class with each
   YOLO box and selects the component nearest that detection.
5. Unsupported classes, or supported classes without usable semantic pixels,
   receive a full-resolution rectangular `box_fallback` mask.
6. Masks, contours, boxes, and compatibility fields are written to JSON.

Mode statistics include the detector counts plus the number of near-identical
instances consolidated, the number of true semantic masks, the number of box
fallbacks, and the semantic-mask support ratio.

Duplicate consolidation uses semantic-group matching for ordinary overlaps.
Different class names are consolidated only for near-identical boxes
(`IoU >= 0.85`, containment `>= 0.98`, normalized center distance `<= 0.06`).
Same-name non-vehicle detections also allow containment `>= 0.98` with center
distance `<= 0.22`; vehicle thresholds stay conservative to preserve adjacent
cars and trucks.

After segmentation, two true semantic masks with the same canonical class are
consolidated when their intersection covers at least 80% of the smaller mask.
This does not apply to rectangular fallbacks.

DeepLabV3 is semantic segmentation, not true instance segmentation. The
YOLO-box intersection separates many same-class objects, but it cannot recover
an exact instance boundary when the VOC model has no class for the object or
when multiple instances are represented as one semantic component.

Each object records `fallback_reason`, `box_delta`, `mask_area_ratio`,
`box_fill_ratio`, `detection_mask_iou`, `connected_component_count`, and the
DeepLab candidate component count. GUI labels show `[FALLBACK]` for rectangular
fallback masks; those contours must not be interpreted as measured boundaries.

## Coordinate convention

- Recognition and saved masks always use original-image coordinates.
- New `detection_box`, `mask_box`, and `corners` use inclusive `x1,y1,x2,y2`
  pixel indices.
- Legacy `box_original`, `four_corners_original`, and `center_original` remain
  in the JSON for Unity compatibility.
- GUI display coordinates are scaled only for rendering. Mouse coordinates
  are converted back with the inverse display scale before hit testing.

## Run

```powershell
.\.venv\Scripts\python.exe .\demo_magic_photo_instance_segmentation.py
```

Environment variables remain available:

```powershell
$env:MAGIC_PHOTO_DETECTION_MODE = "auto"
$env:MAGIC_PHOTO_IMAGE_PATH = "C:\path\to\image.jpg"
.\.venv\Scripts\python.exe .\demo_magic_photo_instance_segmentation.py
```

The GUI keys are:

- `1`: boxes, contours, and object IDs
- `2`: glow
- `3`: spotlight
- `4`: binary mask and simplified contour
- `5`: detection box and mask box comparison
- `n` / `p`: next / previous object
- `M`: standard / accuracy / auto and re-analyze
- `s`: save the current GUI image
- `q`: quit

`analysis_result.json` is the Unity-facing output. Per-object white/black PNG
masks are saved below `masks/<image-name>_<mode>/`.
When a repeated analysis produces fewer objects, stale `object_*.png` files in
that same image/mode folder are removed so the folder matches the JSON.
