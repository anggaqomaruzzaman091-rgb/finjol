# KTP YOLO model

Drop your trained YOLOv8 weights here as `ktp_yolo.pt`. The backend
auto-detects the file on startup; until it exists, the scan endpoint
falls back to the dual-engine (EasyOCR + Tesseract) full-page path.

## Training (one-time, offline once weights cached)

Follow `yolov8_train_ktp_roboflow.ipynb`:

```python
from ultralytics import YOLO

model = YOLO("yolov8n.yaml")          # or yolov8n.pt for transfer learning
model.train(data="data.yaml", epochs=50, imgsz=640)
```

Then copy `runs/detect/train/weights/best.pt` into this directory as
`ktp_yolo.pt`, or set the `KTP_YOLO_MODEL` environment variable to
point at any `.pt` path you prefer.

## Class labels accepted

The Roboflow KTP dataset uses a few different naming conventions across
versions (`ttl` / `tempat_tgl_lahir`, `rt_rw` / `rtrw`, etc.). All common
aliases are mapped in `yolo_engine.CLASS_ALIASES` — no change needed when
swapping model versions.
