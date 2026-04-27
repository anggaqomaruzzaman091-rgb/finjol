import { useState, useEffect } from 'react';
import { ShieldAlert, FileText, CheckCircle2, ChevronRight, ChevronLeft, Upload, ArrowRight, ScanLine, Loader2, Camera } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { silentLogin, scanIdentityDocument, verifyAndSaveIdentity } from '../api';
import CameraCapture from '../components/CameraCapture';

export default function DisputeGenerator() {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [scanError, setScanError] = useState('');
  const [validationError, setValidationError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  // Initializing secure session under the hood on mount
  useEffect(() => {
    silentLogin().catch(console.error);
  }, []);

  const [formData, setFormData] = useState({
    platformName: '',
    dateFraudKnown: '',
    nominalBilled: '',
    chronologyText: '',
    nik: '',
    fullname: '',
    documentType: '',
    dob: '',
    alamat: '',
    jenisKelamin: 'Laki-laki',
    noHandphone: '',
    email: '',
    evidenceFiles: [] as File[]
  });

  const handleNext = () => {
    // Perform Strict NIK step validation here if moving away from step 3 to step 4
    if (step === 3) {
      if (!/^\d{16}$/.test(formData.nik)) {
        setValidationError("NIK must be exactly 16 numeric digits as per backend requirements.");
        return;
      }
      if (!formData.fullname) {
        setValidationError("Full name string cannot be empty.");
        return;
      }
      setValidationError('');
    }
    setStep((s) => Math.min(s + 1, 4));
  };

  const handlePrev = () => setStep((s) => Math.max(s - 1, 1));
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    let finalValue = value;
    let errorMsg = '';

    if (name === 'nik') {
      if (/\D/.test(value)) errorMsg = 'NIK must contain numbers only.';
      else if (value.replace(/\D/g, '').length !== 16 && value.length > 0) errorMsg = 'NIK must be exactly 16 digits.';
      finalValue = value.replace(/\D/g, '').slice(0, 16);
    } else if (name === 'fullname') {
      if (/[^a-zA-Z\s.,'-]/.test(value)) errorMsg = 'Name strictly allows letters and standard characters.';
      else if (value.replace(/[^a-zA-Z\s.,'-]/g, '').length < 3 && value.length > 0) errorMsg = 'Name must be at least 3 characters.';
      finalValue = value.replace(/[^a-zA-Z\s.,'-]/g, '');
    } else if (name === 'nominalBilled') {
      if (/\D/.test(value)) errorMsg = 'Amount must be numeric only.';
      finalValue = value.replace(/\D/g, '');
      if (finalValue && parseInt(finalValue, 10) < 10000) errorMsg = 'Amount must be at least IDR 10,000.';
    } else if (name === 'platformName') {
      if (value.length > 0 && value.length < 3) errorMsg = 'Platform name must be at least 3 characters.';
    } else if (name === 'chronologyText') {
      if (value.length > 0 && value.length < 15) errorMsg = 'Chronology must be at least 15 characters.';
    } else if (name === 'dob') {
      // Auto-format: digits only → DD-MM-YYYY
      const digits = value.replace(/\D/g, '').slice(0, 8);
      if (digits.length <= 2) finalValue = digits;
      else if (digits.length <= 4) finalValue = `${digits.slice(0, 2)}-${digits.slice(2)}`;
      else finalValue = `${digits.slice(0, 2)}-${digits.slice(2, 4)}-${digits.slice(4, 8)}`;

      if (digits.length === 8) {
        const d = parseInt(digits.slice(0, 2), 10);
        const m = parseInt(digits.slice(2, 4), 10);
        const y = parseInt(digits.slice(4, 8), 10);
        const dateObj = new Date(y, m - 1, d);
        const isReal = dateObj.getFullYear() === y && dateObj.getMonth() === m - 1 && dateObj.getDate() === d;
        if (!isReal) errorMsg = 'Tanggal tidak valid.';
        else if (dateObj >= new Date()) errorMsg = 'Tanggal lahir harus di masa lalu.';
        else if (new Date().getFullYear() - y < 17) errorMsg = 'Usia minimal E-KTP adalah 17 tahun.';
      } else if (digits.length > 0 && digits.length < 8) {
        errorMsg = 'Format: DD-MM-YYYY';
      }
    }

    setFormData({ ...formData, [name]: finalValue });
    setFieldErrors({ ...fieldErrors, [name]: errorMsg });
    setValidationError(''); // Clear validation on type
  };

  const isStepValid = (currentStep: number) => {
    switch (currentStep) {
      case 1:
        return formData.platformName.trim().length >= 3 &&
          parseInt(formData.nominalBilled || '0', 10) >= 10000 &&
          formData.dateFraudKnown.trim() !== '';
      case 2:
        return formData.chronologyText.trim().length >= 15;
      case 3:
        return formData.nik.length === 16 &&
          formData.fullname.trim().length >= 3 &&
          /^\d{2}-\d{2}-\d{4}$/.test(formData.dob) &&
          !fieldErrors.dob;
      default:
        return true;
    }
  };

  const handleCameraCapture = async (file: File) => {
    setIsCameraOpen(false);
    setLoading(true);
    setScanError('');
    try {
      const result = await scanIdentityDocument(file);
      // Auto-fill from Secure Scanning Backend
      setFormData({
        ...formData,
        nik: result.nik || '',
        fullname: result.full_name || '',
        dob: result.date_of_birth || '',
        documentType: result.document_type || 'KTP',
        alamat: result.alamat || '',
        jenisKelamin: result.jenis_kelamin || 'Laki-laki'
      });
    } catch (err: any) {
      setScanError(err.message || 'Error occurred during secure scanning');
    } finally {
      setLoading(false);
    }
  };

  const submitDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.dob) {
      setScanError('Tanggal lahir wajib diisi sebelum submit.');
      return;
    }
    setLoading(true);
    setScanError('');
    try {
      const backendResponse = await verifyAndSaveIdentity({
        document_type: formData.documentType || 'KTP',
        nik: formData.nik,
        full_name: formData.fullname,
        date_of_birth: formData.dob,
        alamat: formData.alamat,
        jenis_kelamin: formData.jenisKelamin,
      });

      const certId = 'CERT-' + String(backendResponse.id).padStart(6, '0');
      navigate(`/certificate/${certId}`, { state: { formData } });
    } catch (err: any) {
      setScanError(err.message || 'Verifikasi gagal. Silakan coba lagi.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="section wizard-section">
      <div className="container" style={{ maxWidth: '760px', margin: '0 auto' }}>
        <h2 className="section-title" style={{ textAlign: 'center', marginBottom: '0.75rem' }}>
          Automated <span className="gradient-text">Dispute Generator</span>
        </h2>
        <p className="section-subtitle" style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          Generate a formal OJK rebuttal letter in under 3 minutes.
        </p>

        {/* Stepper */}
        <div className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', padding: '1.25rem 1.5rem', marginBottom: '1.75rem' }}>
          {[
            { id: 1, icon: ShieldAlert, label: 'Platform' },
            { id: 2, icon: FileText, label: 'Kronologi' },
            { id: 3, icon: Upload, label: 'Identitas' },
            { id: 4, icon: CheckCircle2, label: 'Surat' },
          ].map((s) => (
            <div key={s.id} className={`stepper-step ${step >= s.id ? 'active' : ''}`}>
              <div className={`stepper-dot ${step >= s.id ? 'done' : ''}`}>
                <s.icon size={18} />
              </div>
              <span className="stepper-label">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Wizard Form Content */}
        <div className="glass-panel" style={{ padding: '2rem 2.25rem' }}>

          {step === 1 && (
            <div className="animate-fade-in-up">
              <h3 style={{ marginBottom: '0.5rem', fontSize: '1.4rem' }}>Aktivitas penipuan terjadi di mana?</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Isi data platform pinjol yang mengklaim hutang atas namamu.</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="form-row">
                  <label className="form-label form-label-required">Nama Platform Pinjol</label>
                  <input type="text" name="platformName" value={formData.platformName} onChange={handleChange} className="form-input" style={{ borderColor: fieldErrors.platformName ? '#f87171' : 'var(--border-color)' }} placeholder="Contoh: PinjolKu, KreditCepat" maxLength={50} />
                  {fieldErrors.platformName && <span className="field-error">{fieldErrors.platformName}</span>}
                </div>
                <div className="form-row">
                  <label className="form-label form-label-required">Jumlah Tagihan (IDR)</label>
                  <input type="text" inputMode="numeric" name="nominalBilled" value={formData.nominalBilled} onChange={handleChange} className="form-input" style={{ borderColor: fieldErrors.nominalBilled ? '#f87171' : 'var(--border-color)' }} placeholder="1.500.000" maxLength={15} />
                  {fieldErrors.nominalBilled && <span className="field-error">{fieldErrors.nominalBilled}</span>}
                </div>
                <div className="form-row">
                  <label className="form-label form-label-required">Tanggal Penipuan Diketahui</label>
                  <input type="date" name="dateFraudKnown" value={formData.dateFraudKnown} onChange={handleChange} className="form-input" max={new Date().toISOString().split('T')[0]} />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-fade-in-up">
              <h3 style={{ marginBottom: '0.5rem', fontSize: '1.4rem' }}>Apa yang terjadi?</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                Deskripsikan kronologi bagaimana kamu mengetahui penipuan ini atau insiden pelecehan yang dialami.
              </p>
              <div className="form-row">
                <label className="form-label form-label-required">Kronologi Kejadian</label>
                <textarea name="chronologyText" value={formData.chronologyText} onChange={handleChange} rows={7} className="form-input" style={{ resize: 'vertical', borderColor: fieldErrors.chronologyText ? '#f87171' : 'var(--border-color)' }} placeholder="Contoh: Pada DD/MM saya menerima pesan WhatsApp yang menagih pinjaman..." minLength={15} maxLength={1000} />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem' }}>
                  {fieldErrors.chronologyText
                    ? <span className="field-error">{fieldErrors.chronologyText}</span>
                    : <span />}
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{formData.chronologyText.length}/1000</span>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-fade-in-up">
              <h3 style={{ marginBottom: '0.5rem', fontSize: '1.4rem' }}>Identitas &amp; Bukti</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                Data ini digunakan hanya untuk menyusun surat resmi dan disimpan terenkripsi.
              </p>

              {/* KTP scanner strip */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.3)', borderRadius: '10px', marginBottom: '1.25rem' }}>
                <div>
                  <h4 style={{ color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.95rem', marginBottom: '0.2rem' }}>
                    <ScanLine size={16} /> Scan KTP Otomatis
                  </h4>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>Isi data otomatis dari kamera, hindari typo.</p>
                </div>
                {!isCameraOpen && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setIsCameraOpen(true)}
                    style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', whiteSpace: 'nowrap' }}
                  >
                    {loading ? <Loader2 className="animate-spin" size={16} /> : <><Camera size={15} /> Buka Kamera</>}
                  </button>
                )}
              </div>

              {scanError && (
                <div style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.4)', borderRadius: '8px', padding: '0.75rem 1rem', marginBottom: '1.25rem', color: '#f87171', fontSize: '0.83rem' }}>
                  {scanError}
                </div>
              )}

              {isCameraOpen && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <CameraCapture onCapture={handleCameraCapture} onCancel={() => setIsCameraOpen(false)} />
                </div>
              )}

              {validationError && (
                <div style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.35)', borderRadius: '8px', padding: '0.75rem 1rem', marginBottom: '1.25rem', fontSize: '0.83rem', color: '#f87171' }}>
                  {validationError}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                {/* Full Name */}
                <div className="form-row">
                  <label className="form-label form-label-required">Nama Lengkap (Sesuai KTP)</label>
                  <input
                    type="text" name="fullname" value={formData.fullname}
                    onChange={handleChange} className="form-input"
                    style={{ borderColor: fieldErrors.fullname ? '#f87171' : 'var(--border-color)' }}
                    maxLength={100} placeholder="BUDI SANTOSO"
                  />
                  {fieldErrors.fullname && <span className="field-error">{fieldErrors.fullname}</span>}
                </div>

                {/* NIK + Tanggal Lahir — side by side on wider screens */}
                <div className="form-grid-2">
                  <div className="form-row">
                    <label className="form-label form-label-required">NIK</label>
                    <input
                      type="text" inputMode="numeric" name="nik" value={formData.nik}
                      onChange={handleChange} className="form-input"
                      style={{ borderColor: fieldErrors.nik ? '#f87171' : 'var(--border-color)', fontFamily: 'monospace', letterSpacing: '0.08em' }}
                      maxLength={16} placeholder="3271xxxxxxxxxxxxxxx"
                    />
                    {fieldErrors.nik
                      ? <span className="field-error">{fieldErrors.nik}</span>
                      : <span className="form-field-hint">16 digit tanpa spasi</span>}
                  </div>

                  <div className="form-row">
                    <label className="form-label form-label-required">Tanggal Lahir</label>
                    <div className="form-input-wrap">
                      <input
                        type="text" inputMode="numeric" name="dob" value={formData.dob}
                        onChange={handleChange} className="form-input"
                        style={{ borderColor: fieldErrors.dob ? '#f87171' : /^\d{2}-\d{2}-\d{4}$/.test(formData.dob) ? 'var(--accent-cyan)' : 'var(--border-color)', fontFamily: 'monospace', letterSpacing: '0.06em' }}
                        maxLength={10} placeholder="DD-MM-YYYY"
                      />
                      {/^\d{2}-\d{2}-\d{4}$/.test(formData.dob) && !fieldErrors.dob && (
                        <span className="input-valid-mark">✓</span>
                      )}
                    </div>
                    {fieldErrors.dob
                      ? <span className="field-error">{fieldErrors.dob}</span>
                      : <span className="form-field-hint">Contoh: 15-08-1995</span>}
                  </div>
                </div>

                {/* Jenis Kelamin */}
                <div className="form-row">
                  <label className="form-label">Jenis Kelamin</label>
                  <select name="jenisKelamin" value={formData.jenisKelamin} onChange={handleChange} className="form-input">
                    <option value="Laki-laki">Laki-laki</option>
                    <option value="Perempuan">Perempuan</option>
                  </select>
                </div>

                {/* Alamat */}
                <div className="form-row">
                  <label className="form-label">Alamat Lengkap</label>
                  <textarea
                    name="alamat" value={formData.alamat}
                    onChange={handleChange} className="form-input"
                    rows={2} placeholder="Sesuai KTP..."
                  />
                </div>

                {/* Phone + Email */}
                <div className="form-grid-2">
                  <div className="form-row">
                    <label className="form-label">No. Handphone</label>
                    <input type="text" inputMode="numeric" name="noHandphone" value={formData.noHandphone} onChange={handleChange} className="form-input" placeholder="08xx-xxxx-xxxx" />
                  </div>
                  <div className="form-row">
                    <label className="form-label">E-mail</label>
                    <input type="email" name="email" value={formData.email} onChange={handleChange} className="form-input" placeholder="anda@email.com" />
                  </div>
                </div>

                {/* Evidence upload */}
                <div style={{ marginTop: '0.5rem', border: '2px dashed var(--border-color)', padding: '1.5rem', textAlign: 'center', borderRadius: '10px', cursor: 'pointer', transition: 'border-color 0.2s' }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent-cyan)')}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-color)')}
                >
                  <Upload size={28} style={{ margin: '0 auto 0.75rem', color: 'var(--text-muted)', display: 'block' }} />
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', margin: 0 }}>Upload tangkapan layar sebagai bukti (chat, tagihan)</p>
                </div>

              </div>
            </div>
          )}

          {step === 4 && (
            <div className="animate-fade-in-up">
              <h3 style={{ marginBottom: '1.5rem', fontSize: '1.5rem' }}>Review Official Rebuttal</h3>
              <div style={{ background: '#f8fafc', color: '#0f172a', padding: '2rem', borderRadius: '8px', fontSize: '0.9rem', fontFamily: 'serif', lineHeight: 1.6 }}>
                <p style={{ textAlign: 'right', marginBottom: '2rem' }}>Date: {new Date().toLocaleDateString()}</p>
                <p><strong>To: Otoritas Jasa Keuangan (OJK) & Asosiasi Fintech Pendanaan Bersama Indonesia (AFPI)</strong></p>
                <p style={{ marginBottom: '2rem' }}>Subject: <strong>Formal Dispute & Denial of Loan Application at {formData.platformName || '[PLATFORM]'}</strong></p>

                <p>I, the undersigned, {formData.fullname || '[NAME]'} with NIK {formData.nik || '[NIK]'}, formally declare that I have NEVER applied for, authorized, nor received any funds from the lending platform named <strong>{formData.platformName || '[PLATFORM]'}</strong>.</p>

                <p style={{ marginTop: '1rem' }}>It has come to my attention on {formData.dateFraudKnown || '[DATE]'} that my identity has been maliciously utilized, resulting in an unauthorized billing of IDR {formData.nominalBilled || '[AMOUNT]'}.</p>

                <p style={{ marginTop: '1rem' }}><strong>Chronology of Events:</strong></p>
                <p style={{ background: '#e2e8f0', padding: '1rem', borderRadius: '4px', fontStyle: 'italic' }}>{formData.chronologyText || 'User chronology details...'}</p>

                <p style={{ marginTop: '1rem' }}>I request immediate investigation and takedown of my data from this platform to halt the associated defamation and harassment. Evidence is attached herein.</p>

                <p style={{ marginTop: '2rem' }}>Sincerely,</p>
                <p style={{ marginTop: '3rem' }}><strong>{formData.fullname || '[YOUR NAME]'}</strong></p>
              </div>

              {scanError && (
                <div style={{ background: 'rgba(255,77,79,0.1)', border: '1px solid #ff4d4f', borderRadius: '8px', padding: '1rem', marginTop: '1rem', color: '#ff4d4f', fontSize: '0.85rem' }}>
                  {scanError}
                </div>
              )}
              <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                <button className="btn-secondary" style={{ flex: 1 }} disabled={loading}>Download PDF</button>
              </div>
            </div>
          )}

          {/* Wizard Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handlePrev}
              disabled={step === 1 || loading}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.8rem 1.5rem', background: 'transparent', color: step === 1 ? 'var(--text-muted)' : 'var(--text-main)', border: 'none', cursor: step === 1 ? 'not-allowed' : 'pointer', fontWeight: 600 }}
            >
              <ChevronLeft size={20} /> Back
            </button>

            {step < 4 ? (
              <button
                onClick={handleNext}
                className="btn-primary"
                disabled={loading || !isStepValid(step)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: (loading || !isStepValid(step)) ? 0.5 : 1, cursor: (loading || !isStepValid(step)) ? 'not-allowed' : 'pointer' }}
              >
                Continue <ChevronRight size={20} />
              </button>
            ) : (
              <button
                onClick={submitDispute}
                className="btn-primary"
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--accent-green)', color: '#000' }}
              >
                {loading ? <Loader2 className="animate-spin" size={20} /> : 'Submit & Secure Entity'}
                {!loading && <ArrowRight size={20} />}
              </button>
            )}
          </div>

        </div>
      </div>
    </section>
  );
}
