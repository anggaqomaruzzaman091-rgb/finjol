import { useState } from 'react';
import { Shield, CheckCircle2, Circle, AlertTriangle, ExternalLink, Lock, Phone, UserCheck, FileText, Users } from 'lucide-react';

const STEPS = [
  {
    icon: Phone,
    text: 'Blokir Rekening Bank',
    detail: 'Segera hubungi bank dan instruksikan untuk memblokir transfer masuk atau auto-debit terkait pemberi pinjaman palsu.',
    color: '#22d3ee',
  },
  {
    icon: Lock,
    text: 'Ganti Semua Password Utama',
    detail: 'Ganti password email dan akun media sosial yang terhubung ke nomor handphone yang dikompromikan.',
    color: '#a78bfa',
  },
  {
    icon: UserCheck,
    text: 'Hubungi Dukcapil',
    detail: 'Laporkan bahwa NIK-mu telah dikompromikan agar mereka memiliki catatan potensi penipuan atas identitasmu.',
    color: '#4ade80',
  },
  {
    icon: FileText,
    text: 'Lapor ke Kominfo / Polisi Siber',
    detail: 'Buat laporan resmi di portal Kominfo (AduanKonten) dan unit Cybercrime setempat untuk menghapus aplikasi ilegal.',
    color: '#fbbf24',
  },
  {
    icon: Users,
    text: 'Beritahu Kontak Darurat',
    detail: 'Pinjol ilegal sering mengganggu kontakmu. Peringatkan mereka agar tidak merespons pesan yang mengklaim kamu berutang.',
    color: '#f87171',
  },
];

export default function TakedownGuide() {
  const [done, setDone] = useState<Record<number, boolean>>({});

  const toggle = (i: number) => setDone(prev => ({ ...prev, [i]: !prev[i] }));

  const completedCount = Object.values(done).filter(Boolean).length;
  const progress = Math.round((completedCount / STEPS.length) * 100);

  return (
    <section className="section wizard-section" style={{ background: 'oklch(0.09 0.04 220)' }}>
      <div className="container" style={{ maxWidth: '760px', margin: '0 auto' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '50%',
            background: 'rgba(34,211,238,0.12)', border: '2px solid rgba(34,211,238,0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem',
          }}>
            <Shield size={26} color="#22d3ee" />
          </div>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.02em', margin: '0 0 0.5rem', color: 'var(--text-main)' }}>
            Panduan <span style={{ color: 'var(--accent-cyan)' }}>Pemulihan Identitas</span>
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', maxWidth: '520px', margin: '0 auto', lineHeight: 1.6 }}>
            Kit pertolongan pertama. Ikuti langkah kritis ini untuk mengamankan identitas dan mencegah eksploitasi lebih lanjut.
          </p>
        </div>

        {/* Progress panel */}
        <div className="glass-panel" style={{ padding: '1.5rem 2rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)' }}>
              Progres Keamanan
            </span>
            <span style={{
              fontSize: '0.95rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums',
              color: progress === 100 ? '#4ade80' : 'var(--accent-cyan)',
            }}>
              {completedCount}/{STEPS.length} selesai
            </span>
          </div>

          {/* Track */}
          <div style={{ position: 'relative', height: '8px', borderRadius: '999px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${progress}%`,
              borderRadius: '999px',
              background: progress === 100
                ? 'linear-gradient(90deg, #4ade80, #22d3ee)'
                : 'linear-gradient(90deg, #22d3ee, #818cf8)',
              transition: 'width 0.5s cubic-bezier(0.16,1,0.3,1)',
            }} />
          </div>

          {progress === 100 && (
            <p style={{ textAlign: 'center', color: '#4ade80', fontSize: '0.83rem', fontWeight: 600, marginTop: '0.75rem' }}>
              Semua langkah selesai. Identitasmu terlindungi.
            </p>
          )}
        </div>

        {/* Warning — full border, no side-stripe */}
        <div style={{
          background: 'rgba(248,113,113,0.07)',
          border: '1px solid rgba(248,113,113,0.3)',
          borderRadius: '10px',
          padding: '1.25rem 1.5rem',
          marginBottom: '1.75rem',
          display: 'flex',
          gap: '1rem',
          alignItems: 'flex-start',
        }}>
          <AlertTriangle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h4 style={{ color: '#f87171', marginBottom: '0.4rem', fontSize: '0.95rem', fontWeight: 700 }}>
              Jangan Bayar Uang Pemerasan
            </h4>
            <p style={{ fontSize: '0.87rem', color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Membayar pinjol ilegal tidak menghentikan pelecehan. Ini hanya menandai profilmu sebagai "target yang membayar" dan akan memicu lebih banyak penagihan. Blokir nomor mereka segera setelah mengamankan datamu.
            </p>
          </div>
        </div>

        {/* Checklist */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {STEPS.map((step, i) => {
            const isDone = !!done[i];
            const Icon = step.icon;
            return (
              <div
                key={i}
                onClick={() => toggle(i)}
                style={{
                  display: 'flex',
                  gap: '1rem',
                  alignItems: 'flex-start',
                  padding: '1.25rem 1.5rem',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  background: isDone
                    ? `oklch(0.12 0.04 220)`
                    : 'var(--glass-bg)',
                  border: `1px solid ${isDone ? `${step.color}35` : 'var(--glass-border)'}`,
                  backdropFilter: 'blur(12px)',
                  transition: 'all 0.2s cubic-bezier(0.16,1,0.3,1)',
                  opacity: isDone ? 0.75 : 1,
                }}
              >
                {/* Step number / icon */}
                <div style={{
                  width: '40px', height: '40px', borderRadius: '10px', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isDone ? 'rgba(74,222,128,0.12)' : `${step.color}14`,
                  border: `1px solid ${isDone ? 'rgba(74,222,128,0.3)' : `${step.color}30`}`,
                  transition: 'all 0.2s ease',
                }}>
                  {isDone
                    ? <CheckCircle2 size={20} color="#4ade80" />
                    : <Icon size={18} style={{ color: step.color }} />}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <h4 style={{
                    fontSize: '0.95rem', fontWeight: 600, margin: '0 0 0.3rem',
                    textDecoration: isDone ? 'line-through' : 'none',
                    color: isDone ? 'var(--text-muted)' : 'var(--text-main)',
                  }}>
                    {step.text}
                  </h4>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', lineHeight: 1.55, margin: 0 }}>
                    {step.detail}
                  </p>
                </div>

                <div style={{ flexShrink: 0, marginTop: '2px' }}>
                  {isDone
                    ? <CheckCircle2 size={20} color="#4ade80" />
                    : <Circle size={20} color="var(--text-muted)" style={{ opacity: 0.4 }} />}
                </div>
              </div>
            );
          })}
        </div>

        {/* External links */}
        <div style={{ marginTop: '2.5rem', paddingTop: '2rem', borderTop: '1px solid var(--glass-border)', textAlign: 'center' }}>
          <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', marginBottom: '1.25rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Portal Laporan Resmi
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <a
              href="https://aduankonten.id/"
              target="_blank" rel="noreferrer"
              className="btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem' }}
            >
              AduanKonten Kominfo <ExternalLink size={14} />
            </a>
            <a
              href="https://patrolisiber.id/"
              target="_blank" rel="noreferrer"
              className="btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem' }}
            >
              Polisi Siber <ExternalLink size={14} />
            </a>
            <a
              href="https://konsumen.ojk.go.id/"
              target="_blank" rel="noreferrer"
              className="btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem' }}
            >
              Portal OJK <ExternalLink size={14} />
            </a>
          </div>
        </div>

      </div>
    </section>
  );
}
