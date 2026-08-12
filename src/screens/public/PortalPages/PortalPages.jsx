import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/useAuth';
import fetalGuardLogo from '../../../PKM KC LOGO FETAL GUARD.png';
import './PortalPages.css';

const PATIENT_FEATURES = [
  {
    title: 'Ringkasan kondisi pribadi',
    body: 'Status sesi, profil dasar kehamilan, dan informasi perangkat ditampilkan dengan bahasa sederhana.',
    icon: 'profile',
  },
  {
    title: 'Monitoring terbaru',
    body: 'Data pemantauan terakhir disajikan sebagai indikasi awal dan konteks tindak lanjut, bukan diagnosis.',
    icon: 'pulse',
  },
  {
    title: 'Riwayat sesi',
    body: 'Sesi pemantauan tersimpan dapat ditinjau kembali untuk melihat perubahan dan catatan dari waktu ke waktu.',
    icon: 'history',
  },
  {
    title: 'Edukasi risiko dini',
    body: 'Informasi tindak lanjut dibuat tidak alarmis dan tetap mendorong konsultasi tenaga kesehatan.',
    icon: 'care',
  },
];

const CLINICIAN_FEATURES = [
  {
    title: 'Daftar pasien',
    body: 'Nakes meninjau pasien aktif, status sesi, dan prioritas pemantauan dalam satu dashboard operasional.',
    icon: 'patients',
  },
  {
    title: 'Detail monitoring',
    body: 'Detail pemantauan tiap pasien difokuskan pada tren, kualitas data, dan status risiko skrining awal.',
    icon: 'monitor',
  },
  {
    title: 'Riwayat sensor & AI',
    body: 'Data sensor dan hasil analisis awal ditempatkan sebagai bahan tinjauan, bukan keputusan klinis otomatis.',
    icon: 'analysis',
  },
  {
    title: 'Tindak lanjut',
    body: 'Catatan, rekomendasi, dan eskalasi dibuat untuk membantu koordinasi pemantauan pasien.',
    icon: 'followup',
  },
];

function PortalIcon({ name }) {
  const commonProps = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.8',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
  };

  if (name === 'profile') {
    return (
      <svg {...commonProps}>
        <circle cx="12" cy="8" r="3.4" />
        <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      </svg>
    );
  }

  if (name === 'pulse') {
    return (
      <svg {...commonProps}>
        <path d="M3 12h3l1.8-4.5 3.4 9 2.6-7 1.7 2.5H21" />
      </svg>
    );
  }

  if (name === 'history') {
    return (
      <svg {...commonProps}>
        <path d="M5 6v5h5" />
        <path d="M5.8 11A6.8 6.8 0 1 0 8 6.1" />
        <path d="M12 8.5V12l2.4 1.5" />
      </svg>
    );
  }

  if (name === 'care') {
    return (
      <svg {...commonProps}>
        <path d="M12 21s-7-4.3-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.7-7 10-7 10Z" />
        <path d="M8 13h8" />
        <path d="M12 9v8" />
      </svg>
    );
  }

  if (name === 'patients') {
    return (
      <svg {...commonProps}>
        <circle cx="9" cy="8" r="3" />
        <path d="M3.8 19a5.2 5.2 0 0 1 10.4 0" />
        <path d="M16 10.5a2.5 2.5 0 1 0-1.2-4.7" />
        <path d="M17 19a4.4 4.4 0 0 0-2.2-3.8" />
      </svg>
    );
  }

  if (name === 'monitor') {
    return (
      <svg {...commonProps}>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8" />
        <path d="M12 16v4" />
        <path d="m7 11 2.1-2.4 2.1 3.8 2.1-5.2 2 3.8H17" />
      </svg>
    );
  }

  if (name === 'analysis') {
    return (
      <svg {...commonProps}>
        <path d="M4 18V7" />
        <path d="M9.5 18V4" />
        <path d="M15 18v-8" />
        <path d="M20 18v-5" />
        <path d="M3 18h18" />
      </svg>
    );
  }

  return (
    <svg {...commonProps}>
      <path d="m5 12 4 4 10-10" />
      <path d="M4 20h16" />
    </svg>
  );
}

function PortalPageShell({
  type,
  title,
  eyebrow,
  description,
  features,
  primaryLabel,
  protectedPath,
  loginPath,
  loginState,
  roleHint,
}) {
  const navigate = useNavigate();
  const { isAuthenticated, isAuthLoading, user } = useAuth();
  const canOpenProtected = isAuthenticated && user?.role === loginState.role;
  const toneClass = type === 'clinician' ? 'portal-entry--clinician' : 'portal-entry--patient';

  const handlePrimaryAction = () => {
    if (isAuthLoading) return;

    if (canOpenProtected) {
      navigate(protectedPath);
      return;
    }

    navigate(loginPath, { state: loginState });
  };

  return (
    <main className={`portal-entry ${toneClass}`}>
      <header className="portal-entry__nav">
        <Link to="/" className="portal-entry__brand" aria-label="Kembali ke beranda FETAL-GUARD">
          <img src={fetalGuardLogo} alt="" aria-hidden="true" />
          <span>
            <strong>FETAL-GUARD</strong>
            <small>Smart Maternity Belt</small>
          </span>
        </Link>
        <div className="portal-entry__nav-actions">
          <Link to="/" className="portal-entry__ghost">Beranda</Link>
          <button type="button" className="portal-entry__nav-button" onClick={handlePrimaryAction} disabled={isAuthLoading}>
            {isAuthLoading ? 'Memeriksa...' : canOpenProtected ? 'Buka Portal' : 'Masuk'}
          </button>
        </div>
      </header>

      <section className="portal-entry__hero">
        <div className="portal-entry__copy">
          <p className="portal-entry__eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
          <div className="portal-entry__actions">
            <button type="button" className="portal-entry__primary" onClick={handlePrimaryAction} disabled={isAuthLoading}>
              {isAuthLoading ? 'Memeriksa sesi...' : canOpenProtected ? 'Buka Portal Aktif' : primaryLabel}
            </button>
            <Link to={loginPath} state={loginState} className="portal-entry__secondary">
              Gunakan akun yang sudah ada
            </Link>
          </div>
          <p className="portal-entry__role-note">{roleHint}</p>
        </div>

        <div className="portal-entry__panel" aria-label={`Ringkasan fitur ${title}`}>
          {features.map((feature) => (
            <article className="portal-entry__feature" key={feature.title}>
              <span className="portal-entry__feature-icon">
                <PortalIcon name={feature.icon} />
              </span>
              <div>
                <h2>{feature.title}</h2>
                <p>{feature.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function PatientPortalPage() {
  return (
    <PortalPageShell
      type="patient"
      eyebrow="Portal Ibu Hamil"
      title="Ruang pemantauan yang mudah dibaca pasien."
      description="Portal ini memusatkan ringkasan pribadi, status monitoring, riwayat sesi, dan edukasi tindak lanjut dengan bahasa yang tenang dan bertanggung jawab."
      features={PATIENT_FEATURES}
      primaryLabel="Masuk atau daftar pasien"
      protectedPath="/patient/home"
      loginPath="/login/ibu-hamil"
      loginState={{ portal: 'patient', role: 'patient' }}
      roleHint="Pendaftaran publik hanya untuk pasien. Akun nakes dibuat melalui proses internal/admin."
    />
  );
}

export function ClinicianPortalPage() {
  return (
    <PortalPageShell
      type="clinician"
      eyebrow="Portal Nakes"
      title="Dashboard operasional untuk pemantauan pasien."
      description="Portal nakes disusun untuk meninjau pasien, sesi monitoring, status risiko skrining awal, dan catatan tindak lanjut tanpa mencampur alur pasien."
      features={CLINICIAN_FEATURES}
      primaryLabel="Masuk sebagai nakes"
      protectedPath="/clinician/dashboard"
      loginPath="/login/nakes"
      loginState={{ portal: 'clinician', role: 'clinician' }}
      roleHint="Akun nakes tidak dibuat dari registrasi publik. Gunakan akun yang sudah diprovisikan oleh sistem."
    />
  );
}
