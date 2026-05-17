"""
Train the KTP YOLOv8 field-detector and install the result so the
backend auto-loads it on the next restart.

Ported from `yolov8_train_ktp_roboflow.ipynb` with two differences:

* It runs locally (no Colab / Google Drive).
* It looks for the dataset in a configurable location instead of a
  hard-coded Drive path.

Usage
-----
    # 1. Point at a YOLOv8-format dataset (folder containing data.yaml)
    set KTP_DATASET=C:\\path\\to\\ktp-dataset    (Windows cmd)
    $env:KTP_DATASET = "C:\\path\\to\\ktp-dataset"   (PowerShell)
    export KTP_DATASET=/path/to/ktp-dataset       (bash)

    # 2. Run
    backend\\venv\\Scripts\\python.exe backend\\scripts\\train_ktp_yolo.py

The script will:
  1. Validate that `<KTP_DATASET>/data.yaml` exists.
  2. Run `YOLO('yolov8n.pt').train(data=..., epochs=EPOCHS, imgsz=640)`.
     yolov8n.pt is the COCO-pretrained nano weights (~6 MB) used for
     transfer learning. It auto-downloads on the first run (one-time),
     then training is fully offline.
  3. Copy `runs/detect/<latest>/weights/best.pt` to
     `backend/models/ktp_yolo.pt` so the FastAPI server picks it up
     without any configuration.

Dataset layout (YOLOv8 / Roboflow export)
-----------------------------------------
    ktp-dataset/
        data.yaml                # paths + class names
        train/images/*.jpg
        train/labels/*.txt       # YOLO format: <cls> <cx> <cy> <w> <h>
        valid/images/*.jpg
        valid/labels/*.txt

Where to get a dataset
----------------------
* Roboflow Universe → search "KTP Indonesia" (multiple public CC-BY
  datasets, ~1k–3k labeled samples). "Export → YOLOv8" gives this
  exact layout.
* Or label your own with LabelImg / Roboflow Annotate (recommended
  classes: nik, nama, tempat_tgl_lahir, jenis_kelamin, gol_darah,
  alamat, rt_rw, kel_desa, kecamatan, agama, status_perkawinan,
  pekerjaan, kewarganegaraan, berlaku_hingga, foto, ttd).

The list of accepted class label aliases is in
`backend/yolo_engine.py:CLASS_ALIASES` — you can use any of them.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
MODELS_DIR = BACKEND_DIR / "models"
DEFAULT_TARGET_NAME = "ktp_yolo.pt"

DEFAULT_EPOCHS = 50
DEFAULT_IMGSZ = 640
DEFAULT_BATCH = 16


def _print_instructions(reason: str) -> None:
    print(f"\n[train_ktp_yolo] {reason}\n", file=sys.stderr)
    print(
        "Provide a YOLOv8-format KTP dataset and re-run, e.g.:\n"
        "    set KTP_DATASET=C:\\path\\to\\ktp-dataset\n"
        "    backend\\venv\\Scripts\\python.exe backend\\scripts\\train_ktp_yolo.py\n"
        "\n"
        "Expected layout:\n"
        "    <KTP_DATASET>/data.yaml\n"
        "    <KTP_DATASET>/train/images/*.jpg\n"
        "    <KTP_DATASET>/train/labels/*.txt\n"
        "    <KTP_DATASET>/valid/images/*.jpg\n"
        "    <KTP_DATASET>/valid/labels/*.txt\n"
        "\n"
        "Easiest source: Roboflow Universe → search 'KTP Indonesia',\n"
        "click Export, choose 'YOLOv8' format, and unzip locally.\n",
        file=sys.stderr,
    )


def _find_data_yaml(root: Path, max_depth: int = 3) -> Path | None:
    """Walk `root` up to `max_depth` levels looking for data.yaml.
    Handles common Roboflow extraction layouts where the zip unpacks
    into a versioned subfolder like 'Deteksi-KTP-Indonesia.v1i.yolov8/'."""
    if not root.exists():
        return None
    if (root / "data.yaml").exists():
        return root
    if max_depth <= 0:
        return None
    for child in sorted(root.iterdir()):
        if child.is_dir():
            found = _find_data_yaml(child, max_depth - 1)
            if found:
                return found
    return None


def resolve_dataset(arg_path: str | None) -> Path | None:
    """Resolve the dataset root. Precedence: CLI arg > env var > common defaults.
    For each candidate, also walks one level down to find a nested
    `data.yaml` (the layout Roboflow zips produce)."""
    candidates: list[Path] = []
    if arg_path:
        candidates.append(Path(arg_path))
    env = os.getenv("KTP_DATASET")
    if env:
        candidates.append(Path(env))
    # Common conventional locations
    candidates.append(BACKEND_DIR / "datasets" / "ktp")
    candidates.append(BACKEND_DIR / "datasets" / "roboflow")

    for c in candidates:
        found = _find_data_yaml(c)
        if found:
            return found
    return None


def download_from_roboflow(
    api_key: str,
    workspace: str,
    project: str,
    version: int,
    dest: Path,
) -> Path:
    """Download a Roboflow Universe dataset in YOLOv8 format to `dest`.
    Returns the dataset root (the folder that contains data.yaml)."""
    try:
        from roboflow import Roboflow
    except ImportError:
        print("[train_ktp_yolo] Installing the `roboflow` package…", flush=True)
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "roboflow"],
        )
        from roboflow import Roboflow  # type: ignore

    dest.mkdir(parents=True, exist_ok=True)
    # Roboflow downloads into the current working directory by default;
    # chdir into dest so the dataset folder lands where we want it.
    prev_cwd = os.getcwd()
    try:
        os.chdir(dest)
        rf = Roboflow(api_key=api_key)
        rf_project = rf.workspace(workspace).project(project)
        ds = rf_project.version(version).download("yolov8")
    finally:
        os.chdir(prev_cwd)
    dataset_root = Path(ds.location) if hasattr(ds, "location") else dest
    if not (dataset_root / "data.yaml").exists():
        # Search one level deep for the actual data.yaml
        for child in dataset_root.iterdir() if dataset_root.exists() else []:
            if child.is_dir() and (child / "data.yaml").exists():
                dataset_root = child
                break
    return dataset_root


def install_best_weights(run_dir: Path, target_name: str = DEFAULT_TARGET_NAME) -> Path:
    """Find the most recently trained best.pt and copy it to the
    location the backend auto-loads. `target_name` lets callers install
    parallel models (e.g. ktp_yolo.pt vs ktp_card.pt) side-by-side."""
    weights = run_dir / "weights" / "best.pt"
    if not weights.exists():
        raise FileNotFoundError(f"Expected weights at {weights} — did training fail?")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = MODELS_DIR / target_name
    shutil.copy2(weights, target_path)
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the KTP YOLOv8 detector.")
    parser.add_argument("--data", help="Path to dataset root (containing data.yaml).")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    # Augmentation knobs — defaults match Ultralytics' (i.e. no-op when omitted).
    parser.add_argument("--mixup", type=float, default=0.0,
                        help="Mixup augmentation strength (0.10-0.20 helps on tiny datasets).")
    parser.add_argument("--degrees", type=float, default=0.0,
                        help="Random rotation range in degrees (e.g. 10 = ±10°).")
    parser.add_argument("--translate", type=float, default=0.1,
                        help="Random translation as fraction of image (default 0.1).")
    parser.add_argument("--scale", type=float, default=0.5,
                        help="Random scale range (default 0.5).")
    parser.add_argument("--shear", type=float, default=0.0,
                        help="Random shear in degrees.")
    parser.add_argument("--perspective", type=float, default=0.0,
                        help="Random perspective (0.0-0.001).")
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME,
                        help="Filename under backend/models/ to install best.pt as.")
    parser.add_argument("--base-weights", default="yolov8n.pt",
                        help="Starting weights (default yolov8n.pt — COCO pretrained nano).")
    parser.add_argument("--project", default=str(BACKEND_DIR / "runs"),
                        help="Where ultralytics will write training artifacts.")
    parser.add_argument("--name", default="ktp_train",
                        help="Run name inside --project.")
    # Roboflow download options
    parser.add_argument("--roboflow-key", default=os.getenv("ROBOFLOW_API_KEY"),
                        help="Roboflow API key (or set ROBOFLOW_API_KEY env var).")
    parser.add_argument("--roboflow-workspace", default="ocr-ktp-indoneisa",
                        help="Roboflow workspace slug.")
    parser.add_argument("--roboflow-project", default="deteksi-ktp-indonesia",
                        help="Roboflow project slug.")
    parser.add_argument("--roboflow-version", type=int, default=1,
                        help="Roboflow dataset version number.")
    args = parser.parse_args()

    dataset = resolve_dataset(args.data)
    if dataset is None and args.roboflow_key:
        target = BACKEND_DIR / "datasets" / "roboflow"
        print(
            f"[train_ktp_yolo] Downloading Roboflow dataset "
            f"{args.roboflow_workspace}/{args.roboflow_project} v{args.roboflow_version} → {target}"
        )
        dataset = download_from_roboflow(
            api_key=args.roboflow_key,
            workspace=args.roboflow_workspace,
            project=args.roboflow_project,
            version=args.roboflow_version,
            dest=target,
        )
    if dataset is None:
        _print_instructions(
            "No KTP_DATASET found and no --roboflow-key / ROBOFLOW_API_KEY provided."
        )
        return 1

    data_yaml = dataset / "data.yaml"
    print(f"[train_ktp_yolo] Using dataset: {dataset}")
    print(f"[train_ktp_yolo] data.yaml:    {data_yaml}")

    try:
        from ultralytics import YOLO
    except ImportError:
        _print_instructions(
            "ultralytics not installed. Run:\n"
            "    backend\\venv\\Scripts\\python.exe -m pip install ultralytics"
        )
        return 2

    model = YOLO(args.base_weights)
    print(f"[train_ktp_yolo] Training: {args.epochs} epochs, imgsz={args.imgsz}, batch={args.batch}")
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
        exist_ok=True,
        verbose=True,
        mixup=args.mixup,
        degrees=args.degrees,
        translate=args.translate,
        scale=args.scale,
        shear=args.shear,
        perspective=args.perspective,
    )

    # results.save_dir points at runs/<name>/
    run_dir = Path(getattr(results, "save_dir", "") or
                   Path(args.project) / args.name)
    target = install_best_weights(run_dir, target_name=args.target_name)
    print(f"\n[train_ktp_yolo] ✓ Installed: {target}")
    print("[train_ktp_yolo] Restart the FastAPI server to pick up the new model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
