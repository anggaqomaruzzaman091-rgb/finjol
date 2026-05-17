# FindJol

> **Offline-first cybersecurity web platform that helps victims of illegal online loans (Pinjol Ilegal) reclaim their identity and clean their BI-Checking / SLIK OJK record — in under 3 minutes.**

FindJol turns a stressful, paperwork-heavy bureaucratic process into a guided 3-step wizard. It scans the victim's KTP locally (no cloud upload), extracts the NIK / Name / Address / Gender via on-device PyTorch OCR, and auto-generates a print-ready formal legal complaint that conforms to Otoritas Jasa Keuangan (OJK) submission standards.

---

## Table of Contents

1. [Why FindJol](#why-findjol)
2. [Core Features](#core-features)
3. [Tech Stack](#tech-stack)
4. [Repository Layout](#repository-layout)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
   - [1. Clone](#1-clone-the-repository)
   - [2. Backend (FastAPI + OCR)](#2-backend-setup-fastapi--ocr)
   - [3. Frontend (React + Vite)](#3-frontend-setup-react--vite)
   - [4. MongoDB](#4-mongodb)
   - [5. Optional: YOLOv8 KTP detector](#5-optional-yolov8-ktp-field-detector)
7. [Environment Variables](#environment-variables)
8. [Running the App](#running-the-app)
9. [Building for Production](#building-for-production)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)
12. [Screenshots](#screenshots)
13. [License](#license)

---

## Why FindJol

When citizens or job seekers have their KTP (Indonesian ID card) data stolen, predatory illegal lenders register loans under their name. The victims discover this only when:

- A job application is rejected due to a sudden negative **BI-Checking / SLIK OJK** record.
- Debt collectors begin harassing them for a loan they never took.

The official OJK takedown process requires rigid legal formatting most citizens don't know how to write. FindJol automates the whole pipeline: **scan → fill chronology → print-ready complaint.**

## Core Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Automated OJK Dispute Generator** | A 3-step wizard compiles raw user input into a print-ready formal legal complaint, following standard Indonesian bureaucratic formatting. |
| 2 | **Zero-Trust Local AI Identity Scanning** | KTP scanning runs entirely on-device using a PyTorch + OpenCV OCR pipeline (EasyOCR + Tesseract, with optional YOLOv8 field detector). No photos ever touch a cloud server. |
| 3 | **Cyber-Themed, Accessible UI** | Dual-tier light/dark interface tuned to reduce anxiety during fraud situations, with clear guidance and large readable typography. |
| 4 | **Security Hardening** | AES encryption at rest, JWT auth, rate limiting (slowapi), bcrypt password hashing, strict security headers (X-Frame-Options, CSP-friendly), and CORS allow-listing. |

## Tech Stack

**Frontend**
- React 18 + TypeScript
- Vite 5
- React Router v7
- Lucide icons, `qrcode.react`

**Backend**
- FastAPI + Uvicorn
- MongoDB (via Motor / PyMongo)
- Pydantic v2
- EasyOCR + Tesseract (dual-engine OCR)
- Ultralytics YOLOv8 (optional KTP field detector)
- OpenCV, Pillow, NumPy
- `python-jose` (JWT), `passlib[bcrypt]`, `cryptography`
- `slowapi` (rate limiting)

## Repository Layout

```
Prod-desc/
├── backend/                # FastAPI service + OCR engines
│   ├── main.py             # API entrypoint
│   ├── auth.py             # JWT + password hashing
│   ├── ocr_service.py      # EasyOCR + Tesseract dual engine
│   ├── yolo_engine.py      # Optional YOLOv8 KTP field detector
│   ├── tesseract_engine.py
│   ├── database.py         # MongoDB connection + index setup
│   ├── encryption.py       # AES-at-rest helpers
│   ├── models/             # YOLOv8 weights (.pt)
│   ├── datasets/           # Training data (optional)
│   └── requirements.txt
├── src/                    # React + Vite frontend
│   ├── pages/
│   ├── components/
│   ├── api.ts              # Backend client
│   └── main.tsx
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── README.md               # ← you are here
```

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Node.js** | ≥ 18.x | LTS recommended |
| **npm** | ≥ 9.x | Bundled with Node |
| **Python** | 3.10 – 3.12 | 3.11 recommended for EasyOCR + Ultralytics |
| **MongoDB** | ≥ 6.0 | Local instance or MongoDB Atlas URI |
| **Tesseract OCR** | ≥ 5.0 | System binary (see install steps) |
| **Git** | latest | |

> **Windows note:** Tesseract must be installed separately and its path made available to `pytesseract`. The default install path is `C:\Program Files\Tesseract-OCR\tesseract.exe`.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/findjol.git
cd findjol
```

### 2. Backend setup (FastAPI + OCR)

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

**Install Tesseract OCR (system-level):**

- **Windows:** Download the installer from the [UB-Mannheim Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki) and install to `C:\Program Files\Tesseract-OCR\`.
- **macOS:** `brew install tesseract`
- **Ubuntu / Debian:** `sudo apt install tesseract-ocr tesseract-ocr-ind`

> Install the **Indonesian** language pack (`tesseract-ocr-ind` / `ind.traineddata`) — required for KTP text recognition.

### 3. Frontend setup (React + Vite)

From the project root:

```bash
npm install
```

### 4. MongoDB

Start a local MongoDB instance, or use a MongoDB Atlas cluster. The backend expects the connection URI in `MONGODB_URI` (see below). On first startup, `database.create_indexes()` will set up the required collections and indexes automatically.

### 5. Optional: YOLOv8 KTP field detector

The OCR pipeline can boost accuracy by first running a YOLOv8 detector that locates KTP fields (NIK, Name, Address, etc.) before OCR.

If `backend/models/ktp_yolo.pt` exists, the backend uses it automatically. If not, it falls back to the dual-engine (EasyOCR + Tesseract) full-page path — no extra setup needed.

To train your own weights, see `backend/models/README.md`.

---

## Environment Variables

Create a `.env` file in the **project root** (frontend) and another in **`backend/`** (backend).

### Root `.env` (frontend)

```env
VITE_API_URL=http://127.0.0.1:8000
```

### `backend/.env`

```env
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=findjol

# JWT / auth
SECRET_KEY=replace-with-a-long-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Encryption-at-rest key (must be 32 url-safe base64 bytes for Fernet)
ENCRYPTION_KEY=replace-with-fernet-key

# CORS — comma-separated list of allowed frontend origins
ALLOWED_ORIGINS=http://localhost:5173

# Optional: explicit Tesseract path (Windows)
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Optional: custom YOLOv8 weights path
# KTP_YOLO_MODEL=backend/models/ktp_yolo.pt
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Running the App

Open two terminals.

**Terminal 1 — Backend (FastAPI):**

```bash
cd backend
# activate venv if not already
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The first request to `/scan` warms up the OCR model (~5–10 seconds). Subsequent requests are fast.

**Terminal 2 — Frontend (Vite):**

```bash
npm run dev
```

Open <http://localhost:5173> in your browser.

---

## Building for Production

### Frontend

```bash
npm run build
```

Static assets are emitted to `dist/`. Serve via any static host (Nginx, Cloudflare Pages, Netlify, Vercel) and point `VITE_API_URL` at your deployed backend.

### Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

For production, run behind a reverse proxy (Nginx / Caddy) with HTTPS, and set `ALLOWED_ORIGINS` to your real frontend URL. Swagger/Redoc are intentionally disabled in production.

---

## Testing

The backend ships with a suite of OCR and validation tests:

```bash
cd backend
pytest -v
```

Specific suites:

```bash
pytest test_dual_engine.py       # EasyOCR + Tesseract combined pipeline
pytest test_ocr_parsers.py       # NIK / address / DOB parsers
pytest test_ocr_precision.py     # Accuracy benchmarks
pytest test_yolo_engine.py       # YOLOv8 field detector
pytest test_validation.py        # Input validation rules
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pytesseract.TesseractNotFoundError` | Set `TESSERACT_CMD` env var to the absolute path of `tesseract.exe`. |
| `easyocr` first run is slow | Expected — it downloads model weights (~64 MB) on first launch, then caches them. |
| `ModuleNotFoundError: ultralytics` | YOLOv8 is optional. Either `pip install ultralytics` or remove `backend/models/ktp_yolo.pt`. |
| `CORS error` in browser console | Add the frontend origin to `ALLOWED_ORIGINS` in `backend/.env` and restart Uvicorn. |
| MongoDB connection refused | Confirm `mongod` is running and `MONGODB_URI` is reachable. |
| OCR returns empty for Indonesian text | Install Tesseract's Indonesian traineddata: `tesseract-ocr-ind`. |

---

## Screenshots

- `Screenshot_Home.png` — Landing & dashboard
- `Screenshot_Dispute.png` — Dispute generator flow

## License

Proprietary — all rights reserved. Contact the project owner for licensing inquiries.
