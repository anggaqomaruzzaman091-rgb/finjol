import { useParams, useLocation, Link } from 'react-router-dom';
import { ExternalLink, Printer, ShieldCheck, CheckCircle2 } from 'lucide-react';

export default function Certificate() {
  const { id } = useParams();
  const location = useLocation();
  const formData = location.state?.formData || {};

  const today = new Date().toLocaleDateString('id-ID', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <section className="section wizard-section" style={{ background: 'oklch(0.085 0.035 220)' }}>
      <style>{`
        @media print {
          body { background: #fff !important; color: #000 !important; }
          .no-print { display: none !important; }
          .header, .footer { display: none !important; }
          .section { padding: 0 !important; display: block !important; }
          .print-document { box-shadow: none !important; margin: 0 !important; border-radius: 0 !important; }
          @page { margin: 1.5cm; }
        }
      `}</style>

      {/* ── Action header ─────────────────────────────────────────── */}
      <div className="container no-print" style={{ maxWidth: '800px', margin: '0 auto 2.5rem' }}>

        {/* Status badge */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: 'rgba(74,222,128,0.12)',
            border: '2px solid rgba(74,222,128,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <CheckCircle2 size={32} color="#4ade80" />
          </div>
          <div style={{ textAlign: 'center' }}>
            <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '2rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, letterSpacing: '-0.02em' }}>
              Surat <span style={{ color: 'var(--accent-cyan)' }}>Pengaduan OJK</span>
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.4rem' }}>
              ID Laporan: <span style={{ fontFamily: 'monospace', color: 'var(--accent-cyan)', fontWeight: 600 }}>{id || 'CERT-DEMO'}</span>
            </p>
          </div>
        </div>

        {/* Trust strip */}
        <div style={{
          display: 'flex', justifyContent: 'center', gap: '2rem', flexWrap: 'wrap',
          padding: '1rem 1.5rem', borderRadius: '10px',
          background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)',
          marginBottom: '2rem',
        }}>
          {[
            { icon: ShieldCheck, label: 'Terenkripsi AES-256', color: '#4ade80' },
            { icon: CheckCircle2, label: 'Format OJK Resmi', color: '#22d3ee' },
            { icon: ShieldCheck, label: 'Siap Dicetak / PDF', color: '#a78bfa' },
          ].map(({ icon: Icon, label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              <Icon size={14} color={color} />
              <span>{label}</span>
            </div>
          ))}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            onClick={() => window.print()}
          >
            <Printer size={18} /> Cetak / Simpan PDF
          </button>
          <Link
            to="/guide"
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}
          >
            Langkah Selanjutnya <ExternalLink size={16} />
          </Link>
          <Link
            to="/dispute"
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}
          >
            Buat Surat Baru
          </Link>
        </div>
      </div>

      {/* ── Formal A4 document ────────────────────────────────────── */}
      <div
        className="print-document"
        style={{
          background: '#fefefe',
          color: '#1a1a1a',
          maxWidth: '800px',
          margin: '0 auto',
          padding: '3rem 3.5rem',
          borderRadius: '8px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
          fontFamily: '"Times New Roman", Times, serif',
          lineHeight: '1.6',
          fontSize: '11pt',
        }}
      >
        <div style={{ textAlign: 'right', marginBottom: '2rem', color: '#444' }}>
          Jakarta, {today}
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <p style={{ margin: 0, fontWeight: 'bold' }}>Kepada Yth:</p>
          <p style={{ margin: 0 }}>Anggota Dewan Komisioner Otoritas Jasa Keuangan</p>
          <p style={{ margin: 0 }}>Bidang Edukasi dan Perlindungan Konsumen</p>
        </div>

        <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid #ddd', paddingBottom: '1rem' }}>
          <p style={{ margin: 0, fontWeight: 'bold' }}>
            Perihal: Pengaduan Terhadap Aplikasi Pinjaman Online Ilegal ({formData.platformName || '__________'})
          </p>
        </div>

        <p style={{ margin: '0 0 0.5rem' }}>Dengan Hormat,</p>
        <p style={{ margin: '0 0 1rem' }}>Saya yang bertanda tangan di bawah ini:</p>

        <table style={{ width: '100%', marginBottom: '1.5rem', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['Nama', formData.fullname],
              ['No. KTP / NIK', formData.nik],
              ['Tanggal Lahir', formData.dob],
              ['Jenis Kelamin', formData.jenisKelamin],
              ['Alamat', formData.alamat],
              ['No. Handphone', formData.noHandphone],
              ['E-mail', formData.email],
            ].map(([label, value]) => (
              <tr key={label}>
                <td style={{ width: '170px', padding: '0.15rem 0', verticalAlign: 'top', color: '#555' }}>{label}</td>
                <td style={{ padding: '0.15rem 0', verticalAlign: 'top' }}>
                  : {value || <span style={{ color: '#aaa' }}>__________________</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p style={{ margin: '0 0 1rem', textAlign: 'justify' }}>
          Dalam hal ini mengadukan entitas peminjaman online{' '}
          <strong>{formData.platformName || '[Nama Platform]'}</strong> kepada Otoritas Jasa Keuangan dengan deskripsi sebagai berikut:
        </p>

        <p style={{
          margin: '0 0 1.5rem',
          textAlign: 'justify',
          fontStyle: 'italic',
          whiteSpace: 'pre-wrap',
          textIndent: '2rem',
          background: '#f8f8f8',
          padding: '1rem',
          borderRadius: '4px',
          border: '1px solid #eee',
        }}>
          {formData.chronologyText ||
            'Pada tanggal [XX/XX/XXXX] saya mendapati bahwa data pribadi saya digunakan tanpa persetujuan untuk pengajuan pinjaman pada aplikasi tersebut di atas. Saya mendapatkan ancaman dan penagihan tidak wajar padahal saya tidak pernah menerima maupun menyetujui perjanjian kredit tersebut.'}
        </p>

        <p style={{ margin: '0 0 1.5rem', textAlign: 'justify' }}>
          Berdasarkan kronologi di atas, saya memohon kepada OJK agar dapat menindaklanjuti pengaduan ini berdasarkan ketentuan peraturan tentang Perlindungan Konsumen, serta membersihkan nama baik / NIK saya dari daftar hitam (BI Checking/SLIK OJK) atas pinjaman yang tidak pernah saya lakukan.
        </p>

        <p style={{ margin: '0 0 0.5rem' }}>Terkait laporan ini, saya lampirkan:</p>
        <div style={{ marginLeft: '1.5rem', marginBottom: '2.5rem' }}>
          {[
            'Fotokopi KTP',
            'Tangkapan layar SMS/WA penagihan',
            'Tangkapan layar mutasi rekening (membuktikan tidak ada dana masuk)',
            'Surat Keterangan Lapor Kepolisian (jika ada)',
            `Lembar Tracking FindJol: ${id || 'CERT-DEMO'}`,
          ].map((item, i) => (
            <p key={i} style={{ margin: '0.2rem 0' }}>{i + 1}. {item}</p>
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <div style={{ textAlign: 'center', width: '260px' }}>
            <p style={{ margin: '0 0 5rem' }}>Hormat saya,</p>
            <div style={{ borderTop: '1px solid #333', paddingTop: '0.4rem' }}>
              <p style={{ margin: 0, fontWeight: 'bold' }}>{formData.fullname || '__________________'}</p>
              {formData.nik && (
                <p style={{ margin: 0, fontSize: '9pt', color: '#666' }}>NIK: {formData.nik}</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
