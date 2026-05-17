import { useRef, useState, useEffect, useCallback } from 'react';
import { Camera, X, RefreshCw, Check } from 'lucide-react';

interface CameraCaptureProps {
  onCapture: (file: File) => void;
  onCancel: () => void;
}

// Cap capture width — anything bigger just inflates upload size and
// OCR tensor memory without improving precision on a KTP photo.
const CAPTURE_MAX_WIDTH = 1600;

// KTP physical aspect ratio (85.6 mm × 53.98 mm).
const KTP_ASPECT = 8.56 / 5.398;

// Real-time alignment analysis runs at this cadence (ms). 150ms = ~6 Hz,
// which is fast enough to feel live without burning CPU on every frame.
const ANALYSIS_INTERVAL_MS = 150;

// Hold "aligned" for this long before we auto-capture.
const AUTO_CAPTURE_HOLD_MS = 1200;

type Alignment = 'dark' | 'empty' | 'misaligned' | 'aligned';

const STATUS_COPY: Record<Alignment, { text: string; tone: 'neutral' | 'warn' | 'ok' }> = {
  dark:        { text: 'Cahaya kurang — coba dekati sumber cahaya',  tone: 'warn'    },
  empty:       { text: 'Letakkan KTP di dalam bingkai',              tone: 'neutral' },
  misaligned:  { text: 'Geser KTP — tepi belum lurus di bingkai',    tone: 'warn'    },
  aligned:     { text: 'Siap — menahan posisi…',                     tone: 'ok'      },
};

export default function CameraCapture({ onCapture, onCancel }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement>(null);
  // Separate offscreen canvas for the alignment analyzer so we don't fight
  // for the same drawing context as the capture path.
  const analysisCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Mutable refs for the analysis loop — kept as refs so we don't rebuild
  // intervals on every state update.
  const alignedSinceRef = useRef<number | null>(null);
  const capturedRef = useRef(false);

  const [error, setError] = useState<string>('');
  const [alignment, setAlignment] = useState<Alignment>('empty');
  const [alignmentScore, setAlignmentScore] = useState<number>(0);
  const [autoCaptureEnabled, setAutoCaptureEnabled] = useState<boolean>(true);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    stopCamera();
    capturedRef.current = false;
    alignedSinceRef.current = null;
    setAlignment('empty');
    setAlignmentScore(0);
    try {
      setError('');
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1600 },
          height: { ideal: 1200 },
        },
      });
      streamRef.current = mediaStream;
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch {
      setError('Camera access denied or unavailable. Please ensure permissions are granted.');
    }
  }, [stopCamera]);

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, [startCamera, stopCamera]);

  const performCapture = useCallback(() => {
    if (capturedRef.current) return;
    if (!videoRef.current || !captureCanvasRef.current) return;
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;

    const sw = video.videoWidth;
    const sh = video.videoHeight;
    if (!sw || !sh) return;

    const scale = sw > CAPTURE_MAX_WIDTH ? CAPTURE_MAX_WIDTH / sw : 1;
    canvas.width = Math.round(sw * scale);
    canvas.height = Math.round(sh * scale);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        capturedRef.current = true;
        stopCamera();
        const file = new File([blob], 'id_scan_capture.jpg', { type: 'image/jpeg' });
        onCapture(file);
      },
      'image/jpeg',
      0.9,
    );
  }, [onCapture, stopCamera]);

  // ───────────────────────────────────────────────────────────────
  // Real-time alignment analyzer
  //
  // Approach (pure canvas, no ML lib needed):
  //   1. Downsample current video frame to a small analysis buffer.
  //   2. Compute mean luminance + std-dev *inside* the reticle area
  //      (a KTP has high variance — photo + text + colored bands).
  //   3. Estimate edge response along each of the 4 reticle borders
  //      by comparing pixels just inside vs just outside the border.
  //      A correctly-framed card produces strong edges on ≥3 sides.
  //   4. Classify: dark → empty → misaligned → aligned.
  // ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (error) return;
    let cancelled = false;

    const analyze = () => {
      if (cancelled || capturedRef.current) return;
      const video = videoRef.current;
      const canvas = analysisCanvasRef.current;
      if (!video || !canvas || video.readyState < 2 || !video.videoWidth) return;

      // Downsample to ~320 wide for cheap analysis (~6 Hz on commodity CPUs)
      const W = 320;
      const H = Math.round((video.videoHeight / video.videoWidth) * W);
      if (canvas.width !== W) canvas.width = W;
      if (canvas.height !== H) canvas.height = H;

      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, W, H);

      const frame = ctx.getImageData(0, 0, W, H).data;
      const lum = (x: number, y: number) => {
        const i = (y * W + x) * 4;
        return 0.299 * frame[i] + 0.587 * frame[i + 1] + 0.114 * frame[i + 2];
      };

      // Reticle geometry — matches the CSS in App.css
      let rw = W * 0.86;
      let rh = rw / KTP_ASPECT;
      if (rh > H * 0.7) {
        rh = H * 0.7;
        rw = rh * KTP_ASPECT;
      }
      const rx = Math.floor((W - rw) / 2);
      const ry = Math.floor((H - rh) / 2);
      const x2 = Math.floor(rx + rw);
      const y2 = Math.floor(ry + rh);

      // Luminance stats inside the reticle (subsample every ~6 px)
      let sum = 0, sumSq = 0, count = 0;
      const step = 6;
      for (let y = ry; y < y2; y += step) {
        for (let x = rx; x < x2; x += step) {
          const v = lum(x, y);
          sum += v;
          sumSq += v * v;
          count++;
        }
      }
      const mean = count ? sum / count : 0;
      const variance = count ? Math.max(0, sumSq / count - mean * mean) : 0;
      const stdev = Math.sqrt(variance);

      // Edge response along each reticle border. We average |Δluminance|
      // between pixels 5 px inside vs 5 px outside the border line.
      const NORMAL = 5;
      const stride = 8;
      const edge = (ax: (t: number) => number, ay: (t: number) => number,
                    nx: number, ny: number, len: number) => {
        let total = 0, n = 0;
        for (let t = 0; t < len; t += stride) {
          const cx = Math.round(ax(t));
          const cy = Math.round(ay(t));
          const ix = cx - nx * NORMAL;
          const iy = cy - ny * NORMAL;
          const ox = cx + nx * NORMAL;
          const oy = cy + ny * NORMAL;
          if (ix < 0 || iy < 0 || ox >= W || oy >= H || ix >= W || iy >= H || ox < 0 || oy < 0) continue;
          total += Math.abs(lum(ix, iy) - lum(ox, oy));
          n++;
        }
        return n ? total / n : 0;
      };

      const topE    = edge((t) => rx + t, () => ry,  0, -1, rw);  // normal points up = outside
      const bottomE = edge((t) => rx + t, () => y2,  0,  1, rw);  // normal points down = outside
      const leftE   = edge(() => rx, (t) => ry + t, -1, 0, rh);
      const rightE  = edge(() => x2, (t) => ry + t,  1, 0, rh);

      const EDGE_THRESH = 18;
      const strongEdges = [topE, bottomE, leftE, rightE]
        .filter((e) => e > EDGE_THRESH).length;

      // Heuristic score for display: combines content richness + edges.
      const contentScore   = Math.min(1, stdev / 55);
      const alignmentScore = Math.min(1, strongEdges / 4);
      const overall        = Math.round(contentScore * alignmentScore * 100);

      let next: Alignment;
      if (mean < 40) next = 'dark';
      else if (stdev < 14) next = 'empty';
      else if (strongEdges >= 3) next = 'aligned';
      else next = 'misaligned';

      setAlignment(next);
      setAlignmentScore(overall);

      // Auto-capture: must hold "aligned" continuously for the threshold.
      if (next === 'aligned') {
        if (alignedSinceRef.current === null) {
          alignedSinceRef.current = performance.now();
        } else if (
          autoCaptureEnabled &&
          performance.now() - alignedSinceRef.current >= AUTO_CAPTURE_HOLD_MS
        ) {
          performCapture();
        }
      } else {
        alignedSinceRef.current = null;
      }
    };

    const id = window.setInterval(analyze, ANALYSIS_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [error, autoCaptureEnabled, performCapture]);

  const status = STATUS_COPY[alignment];
  // Auto-capture countdown progress (0..1) once "aligned" begins
  const holdProgress = alignment === 'aligned' && alignedSinceRef.current !== null
    ? Math.min(1, (performance.now() - alignedSinceRef.current) / AUTO_CAPTURE_HOLD_MS)
    : 0;

  return (
    <div className="camera-shell">
      {error ? (
        <div className="camera-error">
          <p>{error}</p>
          <button className="btn-secondary" onClick={onCancel} style={{ marginTop: '1rem' }}>
            Cancel
          </button>
        </div>
      ) : (
        <>
          <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
          <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
          <canvas ref={analysisCanvasRef} style={{ display: 'none' }} />

          <div className="camera-overlay" aria-hidden="true">
            <div className={`camera-reticle reticle-${alignment}`}>
              <span className="corner tl" />
              <span className="corner tr" />
              <span className="corner bl" />
              <span className="corner br" />
              {alignment === 'aligned' && (
                <div
                  className="reticle-progress"
                  style={{ transform: `scaleX(${holdProgress})` }}
                  aria-hidden="true"
                />
              )}
            </div>
            <p className={`camera-hint hint-${status.tone}`}>
              {alignment === 'aligned' ? (
                <><Check size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />{status.text}</>
              ) : (
                status.text
              )}
              <small>
                Presisi {alignmentScore}% · Ukuran fisik 85.6 × 53.98 mm
              </small>
            </p>
          </div>

          <div className="camera-controls">
            <button onClick={onCancel} className="camera-iconbtn" title="Cancel">
              <X size={22} />
            </button>
            <button
              onClick={performCapture}
              className="btn-primary camera-capture-btn"
              disabled={alignment === 'dark'}
              aria-label="Ambil foto KTP"
            >
              <Camera size={18} /> Capture
            </button>
            <button onClick={startCamera} className="camera-iconbtn" title="Restart Camera">
              <RefreshCw size={22} />
            </button>
          </div>

          <label className="camera-autoswitch" title="Otomatis menangkap saat KTP lurus & jelas">
            <input
              type="checkbox"
              checked={autoCaptureEnabled}
              onChange={(e) => setAutoCaptureEnabled(e.target.checked)}
            />
            <span>Auto-capture</span>
          </label>
        </>
      )}
    </div>
  );
}
