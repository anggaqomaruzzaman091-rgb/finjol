const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// Use sessionStorage instead of localStorage — cleared when tab closes,
// not accessible by scripts in other tabs (reduced XSS attack surface)
const TOKEN_KEY = 'fj_session';

function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function silentLogin(): Promise<void> {
  if (getToken()) return;

  // Generate guest credentials — prefix makes them identifiable for cleanup
  const suffix = crypto.randomUUID().replace(/-/g, '').slice(0, 12);
  const username = `guest_${suffix}`;
  // Password meets minimum 8-char requirement
  const password = `fp_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;

  // Create account; ignore 400 (username already taken — shouldn't happen with UUID)
  await fetch(`${API_BASE}/api/v1/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const tokenRes = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });

  if (tokenRes.ok) {
    const data = await tokenRes.json();
    setToken(data.access_token);
  }
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  let token = getToken();
  if (!token) {
    await silentLogin();
    token = getToken();
  }

  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let res = await fetch(url, { ...options, headers });

  // Token expired — re-authenticate once
  if (res.status === 401) {
    clearToken();
    await silentLogin();
    token = getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      res = await fetch(url, { ...options, headers });
    }
  }

  return res;
}

export interface YoloDetection {
  class: string;
  field: string;
  bbox: [number, number, number, number];
  confidence: number;
}

export interface ScanResponse {
  document_type: string;
  nik?: string;
  full_name?: string;
  tempat_lahir?: string;
  date_of_birth?: string;
  jenis_kelamin?: string;
  gol_darah?: string;
  alamat?: string;
  rt_rw?: string;
  kelurahan?: string;
  kecamatan?: string;
  agama?: string;
  status_perkawinan?: string;
  pekerjaan?: string;
  kewarganegaraan?: string;
  berlaku_hingga?: string;
  /** Aggregate scanning precision in [0, 1] */
  precision_score?: number;
  /** Per-field precision in [0, 1] */
  field_precision?: Record<string, number>;
  /** Which engines participated (yolo+region_ocr, easyocr, tesseract) */
  engines_used?: string[];
  /** Per-field winning engine */
  field_source?: Record<string, string>;
  /** xyxy bbox per field, in preprocessed-image coordinates */
  field_bbox?: Record<string, [number, number, number, number]>;
  /** Raw YOLO detections for UI overlay */
  yolo_detections?: YoloDetection[];
}

export async function scanIdentityDocument(file: File): Promise<ScanResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetchWithAuth(`${API_BASE}/api/v1/identity/scan`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Scanning gagal. Coba lagi.');
  }
  return res.json();
}

export interface KTPPayload {
  document_type: string;
  nik: string;
  full_name: string;
  date_of_birth?: string;
  tempat_lahir?: string;
  jenis_kelamin?: string;
  gol_darah?: string;
  alamat?: string;
  rt_rw?: string;
  kelurahan?: string;
  kecamatan?: string;
  agama?: string;
  status_perkawinan?: string;
  pekerjaan?: string;
  kewarganegaraan?: string;
  berlaku_hingga?: string;
}

export async function verifyAndSaveIdentity(payload: KTPPayload): Promise<Record<string, unknown>> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/identity/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Verifikasi gagal. Periksa data Anda.');
  }
  return res.json();
}
