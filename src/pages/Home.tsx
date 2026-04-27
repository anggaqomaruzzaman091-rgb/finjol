import { Fingerprint, LockKeyhole, Scan, Database, Smartphone, ShieldCheck, Contact, Shield, User, Key, Clock, GitBranch } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-content animate-fade-in-up">
            <h1>
              Cek Status Identitasmu <br />
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 800 }}>Sebelum Background Check.</span>
            </h1>
            <p>
              FindJol memindai data publik identitasmu untuk mendeteksi keterlibatan pinjol ilegal atau penipuan identitas, sebelum HR menemukannya lebih dulu.
            </p>
            <div className="hero-buttons">
              <Link to="/dispute" className="btn-primary" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                Buat Surat Sengketa
              </Link>
              <Link to="/guide" className="btn-secondary" style={{ textDecoration: 'none', display: 'inline-block' }}>
                Panduan Takedown
              </Link>
            </div>
          </div>

          <div className="hero-visual animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <div className="hero-visual-composition">
              <div className="central-device glass-panel">
                <Smartphone size={140} strokeWidth={1} color="var(--text-main)" />
                <div className="device-scan-line"></div>
              </div>
              <div className="floating-icon icon-1" style={{ borderColor: 'rgba(34,211,238,0.4)' }}>
                <ShieldCheck size={32} color="#22d3ee" />
              </div>
              <div className="floating-icon icon-2" style={{ borderColor: 'rgba(74,222,128,0.35)' }}>
                <Fingerprint size={32} color="#4ade80" />
              </div>
              <div className="floating-icon icon-3" style={{ borderColor: 'rgba(167,139,250,0.35)' }}>
                <Contact size={32} color="#a78bfa" />
              </div>
              <div className="floating-icon icon-4" style={{ borderColor: 'rgba(251,191,36,0.3)' }}>
                <Shield size={32} color="#fbbf24" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust bar (horizon divider) ───────────────────────────────── */}
      <div className="trust-bar">
        <div className="trust-item">
          <span className="trust-dot"></span>
          <span>Selesai dalam <strong>3 menit</strong></span>
        </div>
        <div className="trust-item">
          <span className="trust-dot" style={{ background: 'var(--accent-green)' }}></span>
          <span>Arsitektur <strong>Zero-Trust</strong></span>
        </div>
        <div className="trust-item">
          <span className="trust-dot" style={{ background: '#a78bfa' }}></span>
          <span><strong>Open Source</strong> &amp; Gratis</span>
        </div>
        <div className="trust-item">
          <span className="trust-dot" style={{ background: '#fbbf24' }}></span>
          <span>Enkripsi <strong>AES-256</strong></span>
        </div>
      </div>

      {/* ── Features ─────────────────────────────────────────────────── */}
      <section id="features" className="section section-alt">
        <div className="vector-bg">
          <div className="bg-pill pill-1"></div>
          <div className="bg-pill pill-2"></div>
          <div className="bg-pill bg-pill-filled pill-3"></div>
          <div className="bg-pill pill-4"></div>
        </div>
        <div className="container" style={{ position: 'relative', zIndex: 10 }}>
          <h2 className="section-title">
            Mengapa <span style={{ color: 'var(--accent-cyan)' }}>FindJol?</span>
          </h2>
          <div className="accent-divider"></div>
          <p className="section-subtitle">
            Pencurian identitas bisa diam-diam menghancurkan peluang kerjamu lewat background check HR tanpa kamu sadari. Temukan masalah lebih awal.
          </p>

          <div className="features-grid">
            <div className="feature-card glass-panel feat-scan">
              <div className="feature-icon">
                <Scan size={22} />
              </div>
              <h3 className="feature-title">Pemindaian Cepat &amp; Aman</h3>
              <p className="feature-desc">
                FindJol berjalan secara lokal, mencocokkan datamu secara aman dengan registri yang diketahui telah dikompromikan tanpa mengirim data ke server.
              </p>
            </div>

            <div className="feature-card glass-panel feat-detect" style={{ paddingTop: '3.5rem', paddingBottom: '3.5rem' }}>
              <div className="feature-icon">
                <Fingerprint size={22} />
              </div>
              <h3 className="feature-title">Deteksi Penipuan</h3>
              <p className="feature-desc">
                Deteksi dini apakah informasi pribadi atau NIK-mu sedang disalahgunakan untuk pengajuan pinjaman online ilegal.
              </p>
            </div>

            <div className="feature-card glass-panel feat-protect">
              <div className="feature-icon">
                <LockKeyhole size={22} />
              </div>
              <h3 className="feature-title">Perlindungan Karier</h3>
              <p className="feature-desc">
                Ketahui statusmu dan selesaikan masalah sebelum background check resmi HR mendiskualifikasi lamaranmu.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Architecture ──────────────────────────────────────────────── */}
      <section id="architecture" className="section">
        <div className="container">
          <h2 className="section-title">
            Arsitektur <span style={{ color: 'var(--accent-cyan)' }}>Sistem</span>
          </h2>
          <div className="accent-divider" style={{ background: 'linear-gradient(90deg, var(--accent-cyan), #6366f1)' }}></div>
          <p className="section-subtitle">
            Dibangun di atas transparansi. Tinjau alur data FindJol untuk memahami persis bagaimana data diproses dan dilindungi.
          </p>

          <div className="architecture-box glass-panel">
            <div className="erd-content">
              <h3 style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontSize: '1.1rem' }}>
                <Database size={18} style={{ color: 'var(--accent-green)' }} />
                Alur Data &amp; Model
              </h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0', maxWidth: '560px', margin: '0 auto 0' }}>
                FindJol mencocokkan hash identitas terhadap basis data pinjol ilegal yang dilaporkan tanpa mengirimkan PII teks biasa.
              </p>

              <div className="data-flow-container">
                <div className="data-node">
                  <User className="data-node-icon" size={28} />
                  <div className="data-node-title">Klien</div>
                  <div className="data-node-desc">Raw PII Data</div>
                </div>

                <div className="data-path">
                  <div className="data-packet"></div>
                </div>

                <div className="data-node" style={{ borderColor: 'rgba(34,211,238,0.5)', background: 'rgba(34,211,238,0.06)' }}>
                  <Key className="data-node-icon" size={28} style={{ color: 'var(--accent-cyan)' }} />
                  <div className="data-node-title">FindJol Vault</div>
                  <div className="data-node-desc">SHA-256 Hash</div>
                </div>

                <div className="data-path">
                  <div className="data-packet packet-green"></div>
                </div>

                <div className="data-node" style={{ borderColor: 'rgba(74,222,128,0.45)', background: 'rgba(74,222,128,0.06)' }}>
                  <ShieldCheck className="data-node-icon" size={28} style={{ color: 'var(--accent-green)' }} />
                  <div className="data-node-title">Pinjol Registry</div>
                  <div className="data-node-desc">Zero-Knowledge Match</div>
                </div>
              </div>

              {/* Process steps */}
              <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '2.5rem', flexWrap: 'wrap' }}>
                {[
                  { icon: Clock, label: 'Proses lokal', desc: '< 3 detik', color: '#22d3ee' },
                  { icon: Shield, label: 'Zero transmisi PII', desc: 'Enkripsi AES-256', color: '#4ade80' },
                  { icon: GitBranch, label: 'Open Source', desc: 'Dapat diaudit', color: '#a78bfa' },
                ].map(({ icon: Icon, label, desc, color }) => (
                  <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', minWidth: '120px' }}>
                    <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: `${color}18`, border: `1px solid ${color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon size={18} style={{ color }} />
                    </div>
                    <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-main)' }}>{label}</span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
