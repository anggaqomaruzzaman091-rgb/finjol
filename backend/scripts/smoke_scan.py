"""End-to-end smoke test for the scan pipeline.

Loads a real KTP image, runs `process_document_image` directly (no HTTP,
no MongoDB, no auth), and prints the auto-fill payload plus which
engines participated and per-field bbox coordinates.
"""

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import ocr_service  # noqa: E402
import yolo_engine  # noqa: E402
import tesseract_engine  # noqa: E402

# DEBUG: log every YOLO detection call


def banner(s: str) -> None:
    print()
    print("-" * 60)
    print(s)
    print("-" * 60)


async def main(img_path: str) -> int:
    banner("Engine availability")
    print(f"YOLO available:      {yolo_engine.is_available()}")
    print(f"YOLO model path:     {yolo_engine._resolve_model_path()}")
    print(f"Tesseract available: {tesseract_engine.is_available()}")

    banner(f"Scanning: {img_path}")
    with open(img_path, "rb") as f:
        data = f.read()
    print(f"Image size: {len(data) / 1024:.1f} KB")

    result = await ocr_service.process_document_image(data, Path(img_path).name)

    banner("Auto-fill payload")
    for k in [
        "document_type", "nik", "full_name", "tempat_lahir", "date_of_birth",
        "jenis_kelamin", "gol_darah", "alamat", "rt_rw", "kelurahan",
        "kecamatan", "agama", "status_perkawinan", "pekerjaan",
        "kewarganegaraan", "berlaku_hingga",
    ]:
        v = result.get(k) or ""
        print(f"  {k:<22} {v}")

    banner(f"Precision (aggregate {result['precision_score']:.3f})")
    for k, v in sorted(result["field_precision"].items()):
        if v > 0:
            print(f"  {k:<22} {v:.3f}")

    banner("Engines used")
    print(", ".join(result["engines_used"]))

    banner("YOLO detections (specific coordinates)")
    if result["yolo_detections"]:
        for d in result["yolo_detections"]:
            print(f"  class={d['class']:<22} → field={d['field']:<22} "
                  f"conf={d['confidence']:.3f}  bbox={d['bbox']}")
    else:
        print("(no YOLO detections — model unavailable or no boxes above threshold)")

    banner("Per-field bbox (winning engine's coordinates)")
    if result["field_bbox"]:
        for k, b in result["field_bbox"].items():
            print(f"  {k:<22} {b}")
    else:
        print("(empty — YOLO path did not contribute any field)")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: smoke_scan.py <path-to-ktp.jpg>")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
