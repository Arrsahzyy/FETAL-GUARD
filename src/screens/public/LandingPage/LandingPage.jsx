import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import beltConcept from "../../../assets/fetal-guard-belt-concept.jpg";
import fetalGuardLogo from "../../../PKM KC LOGO FETAL GUARD.png";
import "./LandingPage.css";

// ─── DATA ────────────────────────────────────────────────────────────────────

const STATS = [
  {
    numeric: 1900000,
    display: "1,9 juta",
    suffix: "",
    label: "Stillbirth per tahun secara global",
    note: "Data konteks kesehatan publik WHO/UNICEF 2023. Bukan klaim dampak FETAL-GUARD.",
    icon: "globe",
    color: "rose",
  },
  {
    numeric: 46,
    display: null,
    suffix: "%",
    label: "Kasus diperkirakan terjadi saat persalinan",
    note: "Menegaskan pentingnya pemantauan tepat waktu. Keputusan tetap di tangan nakes.",
    icon: "clock",
    color: "blue",
  },
  {
    numeric: 17,
    display: null,
    suffix: " dtk",
    label: "Estimasi satu stillbirth terjadi (global)",
    note: "Estimasi UNICEF. Konteks untuk memahami urgensi pemantauan sejak dini.",
    icon: "warning",
    color: "amber",
  },
  {
    numeric: 160,
    display: "110–160",
    suffix: " bpm",
    label: "Rentang rujukan tampilan DJJ/FHR",
    note: "FETAL-GUARD menampilkan indikasi skrining — interpretasi klinis tetap oleh nakes.",
    icon: "heart",
    color: "teal",
  },
];

const MONITORING_EDUCATION_CARDS = [
  {
    icon: "heart",
    title: "Mengapa perubahan kondisi perlu diperhatikan?",
    body: "Perubahan gerak, keluhan ibu, atau hasil pemeriksaan dapat memerlukan penilaian tenaga kesehatan. Aplikasi tidak menentukan kondisi klinis janin.",
    tag: "Definisi",
    color: "rose",
  },
  {
    icon: "pulse",
    title: "Tanda yang Perlu Diperhatikan",
    body: "Berkurangnya gerakan janin dari biasanya atau keluhan yang mengkhawatirkan perlu dikonsultasikan kepada tenaga kesehatan. Pembacaan sabuk di luar rentang tampilan perlu diulang sesuai panduan dan tidak boleh menjadi satu-satunya dasar mengambil keputusan.",
    tag: "Deteksi Dini",
    color: "amber",
  },
  {
    icon: "shield",
    title: "Peran FETAL-GUARD",
    body: "FETAL-GUARD dirancang untuk menerima sinyal getaran DJJ dan indikator tekanan rahim. Fitur ini masih memerlukan integrasi perangkat dan validasi lanjutan.",
    tag: "Skrining Awal",
    color: "blue",
  },
  {
    icon: "care",
    title: "Yang Tetap Tidak Bisa Digantikan",
    body: "CTG, Doppler, tocotransducer, USG, serta pemeriksaan langsung oleh dokter atau bidan tetap menjadi pemeriksaan rujukan klinis. FETAL-GUARD adalah alat bantu skrining awal, bukan pengganti.",
    tag: "Batas Sistem",
    color: "teal",
  },
];

const CONTRACTION_CARDS = [
  {
    title: "Braxton Hicks",
    subtitle: "Kontraksi latihan yang dapat terjadi",
    body: "Dapat terasa seperti perut mengencang tidak teratur dan dapat mereda setelah beristirahat atau berganti posisi. Hubungi tenaga kesehatan bila nyeri menetap, semakin sering, disertai perdarahan, cairan keluar, atau keluhan lain.",
    icon: "wave",
    dot: "green",
  },
  {
    title: "Kontraksi Persalinan",
    subtitle: "Pola teratur & semakin kuat",
    body: "Kontraksi sejati berpola, semakin kuat, semakin sering, dan tidak berhenti meski berpindah posisi. Durasi biasanya 30–70 detik dengan jeda semakin pendek.",
    icon: "pressure",
    dot: "amber",
  },
  {
    title: "Apa yang FSR Baca?",
    subtitle: "Indikator tekanan sabuk — bukan toco",
    body: "FSR408 di FETAL-GUARD membaca perubahan tekanan mekanis lokal, bukan tekanan intrauterin klinis. Nilainya dipakai sebagai proksi indikator, memerlukan validasi lanjutan sebelum dipakai secara klinis.",
    icon: "chip",
    dot: "blue",
  },
];

const HOW_TO_USE = [
  {
    step: "01",
    title: "Pasang Sabuk dengan Nyaman",
    body: "Kenakan sabuk FETAL-GUARD di area abdomen sesuai panduan. Pastikan modul sensor menempel rata dan tidak longgar agar kualitas sinyal optimal.",
    icon: "belt",
    color: "rose",
  },
  {
    step: "02",
    title: "Hubungkan ke Aplikasi",
    body: "Aktifkan Bluetooth, buka aplikasi pasien FETAL-GUARD, lalu pindai dan pilih perangkat. Status koneksi akan terlihat di layar beranda aplikasi.",
    icon: "phone",
    color: "blue",
  },
  {
    step: "03",
    title: "Mulai Sesi Pemantauan",
    body: 'Duduk atau berbaring dengan nyaman. Tekan "Mulai Pemantauan" dan biarkan sesi berjalan. Usahakan tidak banyak bergerak selama sesi berlangsung.',
    icon: "monitor",
    color: "teal",
  },
  {
    step: "04",
    title: "Tinjau & Tindak Lanjuti",
    body: 'Setelah sesi selesai, lihat ringkasan di riwayat. Jika ada indikasi "perlu pemantauan ulang" atau "segera konsultasi", hubungi bidan atau dokter Anda.',
    icon: "care",
    color: "amber",
  },
];

const SENSOR_DETAILS = [
  {
    id: "piezo",
    label: "4× Piezo Array",
    short: "Vibrasi mekanik DJJ",
    title: "Array piezo pasif untuk membaca getaran DJJ",
    body: "Empat sensor piezo ditempatkan di panel abdomen untuk menangkap vibrasi mekanik sangat kecil yang berhubungan dengan detak jantung janin. Kanal dengan kualitas sinyal terbaik diprioritaskan sebelum estimasi diproses.",
    metric: "Akuisisi",
    value: "4 kanal",
    tone: "rose",
    icon: "wave",
    checklist: [
      "4 kanal independen",
      "Seleksi kanal terbaik",
      "Filter noise awal",
      "Estimasi kualitas sinyal",
    ],
  },
  {
    id: "fsr",
    label: "FSR408",
    short: "Indikator tekanan rahim",
    title: "FSR sebagai proksi indikator pola kontraksi",
    body: "FSR408 membaca perubahan tekanan lokal pada sabuk sebagai indikator mekanis pola kontraksi. Ini bukan pengganti tocotransducer klinis atau pengukuran tekanan intrauterin. Validasi lanjutan diperlukan.",
    metric: "Output",
    value: "Indikator",
    tone: "blue",
    icon: "pressure",
    checklist: [
      "Tekanan relatif sabuk",
      "Pola durasi kontraksi",
      "Memerlukan pembanding toco",
      "Bukan pengukur IUP",
    ],
  },
  {
    id: "max",
    label: "MAX30102",
    short: "Vital ibu — PPG",
    title: "PPG maternal untuk konteks denyut ibu",
    body: "MAX30102 membaca sinyal PPG (photoplethysmography) untuk membantu membedakan denyut ibu dari estimasi DJJ janin. Data vital ibu ini memperkaya konteks pemantauan feto-maternal secara non-invasif.",
    metric: "Metode",
    value: "PPG",
    tone: "teal",
    icon: "heart",
    checklist: [
      "HR maternal non-invasif",
      "SpO2 ibu",
      "Konteks pembeda sinyal",
      "Data pelengkap DJJ",
    ],
  },
];

const SYSTEM_FLOW = [
  {
    title: "Sabuk Wearable",
    label: "Akuisisi",
    detail:
      "Piezo, FSR408, dan MAX30102 membaca sinyal mekanik dan vital maternal secara non-invasif dan berkala selama sesi pemantauan.",
    icon: "belt",
  },
  {
    title: "ESP32",
    label: "Edge Processing",
    detail:
      "Akuisisi ADC/I2C, buffering data mentah, preprocessing ringan, dan pengiriman payload bertahap ke gateway atau cloud.",
    icon: "chip",
  },
  {
    title: "MQTT / Cloud",
    label: "Transmisi",
    detail:
      "Data sesi dikirim ke server untuk penyimpanan terstruktur, kontrol akses berbasis peran, dan integrasi dengan dashboard klinisi.",
    icon: "cloud",
  },
  {
    title: "Pipeline Analisis",
    label: "Rencana",
    detail:
      "Arsitektur model masih berupa baseline pengembangan dan belum aktif sebagai hasil analisis pasien atau acuan klinis.",
    icon: "brain",
  },
  {
    title: "App & Dashboard",
    label: "Tindak Lanjut",
    detail:
      "Ibu hamil melihat status dan riwayat pemantauan, sementara nakes meninjau pasien aktif, alert, dan konteks data sesi dari dashboard.",
    icon: "monitor",
  },
];

const PORTAL_CARDS = [
  {
    title: "Portal Ibu Hamil",
    eyebrow: "Untuk Pasien",
    body: "Akses pemantauan sesi, status perangkat, riwayat, dan notifikasi tindak lanjut dengan bahasa yang tenang dan tidak alarmis.",
    action: "Masuk Portal Pasien",
    route: "/login/ibu-hamil",
    icon: "user",
    color: "rose",
  },
  {
    title: "Portal Tenaga Kesehatan",
    eyebrow: "Untuk Nakes / Klinisi",
    body: "Dashboard operasional untuk meninjau pasien aktif, alert klinis, detail sesi, dan tindak lanjut pemantauan tanpa mencampur alur pasien.",
    action: "Masuk Portal Nakes",
    route: "/login/nakes",
    icon: "monitor",
    color: "blue",
  },
];

const ROADMAP_STEPS = [
  {
    step: 1,
    title: "PoC Sensor & Power",
    body: "Rangkaian piezo, FSR, MAX30102, baterai Li-Po, TP4056, dan pembacaan sinyal awal.",
    icon: "battery",
    done: false,
  },
  {
    step: 2,
    title: "Akuisisi Data",
    body: "Sampling ADC, buffering, format payload, dashboard dasar, dan penyimpanan sesi.",
    icon: "database",
    done: false,
  },
  {
    step: 3,
    title: "Preprocessing Sinyal",
    body: "Filtering, seleksi kanal piezo, estimasi FHR awal, dan indeks kualitas sinyal.",
    icon: "filter",
    done: false,
  },
  {
    step: 4,
    title: "Model AI Baseline",
    body: "CNN-LSTM awal untuk klasifikasi risiko skrining — bukan penilaian klinis.",
    icon: "brain",
    done: false,
  },
  {
    step: 5,
    title: "Validasi Referensi",
    body: "Bandingkan estimasi dengan Doppler, CTG, dan label dari tenaga kesehatan terlatih.",
    icon: "check",
    done: false,
  },
  {
    step: 6,
    title: "Integrasi Wearable",
    body: "Casing ergonomis, stabilitas koneksi, demo end-to-end, dan ethical clearance bertahap.",
    icon: "belt",
    done: false,
  },
];

const FAQ_ITEMS = [
  {
    q: "Apakah FETAL-GUARD bisa menggantikan CTG atau Doppler?",
    a: "Tidak. FETAL-GUARD adalah alat skrining awal wearable yang membantu pemantauan mandiri di rumah. CTG, Doppler, tocotransducer, USG, serta pemeriksaan langsung oleh dokter dan bidan tetap menjadi standar klinis yang tidak bisa digantikan. FETAL-GUARD membantu ibu hamil memantau tren dan mengetahui kapan harus berkonsultasi.",
  },
  {
    q: "Seberapa akurat pembacaan DJJ dari sensor piezo?",
    a: "Pada tahap ini, estimasi DJJ dari sensor piezo belum memiliki hasil validasi klinis. Integrasi perangkat, pemrosesan sinyal, dan perbandingan sistematis dengan alat referensi masih harus diselesaikan sebelum hasil dapat dinilai.",
  },
  {
    q: "Siapa yang bisa menggunakan FETAL-GUARD?",
    a: "Aplikasi pasien ditujukan untuk ibu hamil yang ingin memantau kondisi janin di rumah secara berkala. Dashboard klinisi ditujukan untuk bidan, dokter kandungan, dan tenaga kesehatan yang memantau pasien mereka. Akun nakes diprovisikan melalui sistem admin, bukan registrasi publik.",
  },
  {
    q: "Bagaimana keamanan dan privasi data saya?",
    a: "Backend menerapkan autentikasi dan pemisahan peran dasar. Kebijakan consent, retensi, penghapusan, audit akses, dan pengamanan infrastruktur production masih harus diselesaikan sebelum digunakan untuk data pasien nyata.",
  },
  {
    q: 'Apa yang harus saya lakukan jika muncul indikasi "Segera Konsultasi"?',
    a: "Segera hubungi bidan, dokter kandungan, atau fasilitas kesehatan terdekat. Indikasi ini adalah sinyal skrining awal — bukan kesimpulan medis. Tenaga kesehatan akan melakukan pemeriksaan klinis yang tepat untuk menilai kondisi ibu dan janin. Jangan menunggu atau mengabaikan indikasi ini.",
  },
  {
    q: "Apakah FETAL-GUARD butuh koneksi internet terus-menerus?",
    a: "Rancangan target memakai Bluetooth dari sabuk ke HP dan internet untuk penyimpanan server. Saat ini aplikasi hanya menahan antrean terbatas selama portal pasien aktif; belum ada penyimpanan offline tahan-restart, sehingga koneksi perlu dipulihkan sebelum sesi ditutup.",
  },
];

// ─── ICON COMPONENT ───────────────────────────────────────────────────────────

function Icon({ name, size = 22 }) {
  const p = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    width: size,
    height: size,
  };

  const icons = {
    heart: (
      <svg {...p}>
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    ),
    globe: (
      <svg {...p}>
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
    clock: (
      <svg {...p}>
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    warning: (
      <svg {...p}>
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
    shield: (
      <svg {...p}>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    wave: (
      <svg {...p}>
        <path d="M2 12h3l1.5-4 3 8 2-6 2 4 1.5-2H22" />
      </svg>
    ),
    pulse: (
      <svg {...p}>
        <path d="M3 12h3l1.8-4.5 3.4 9 2.6-7 1.7 2.5H21" />
      </svg>
    ),
    care: (
      <svg {...p}>
        <path d="M12 21s-7-4.3-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.7-7 10-7 10Z" />
        <path d="M8 13h8" />
        <path d="M12 9v8" />
      </svg>
    ),
    user: (
      <svg {...p}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20a8 8 0 0 1 16 0" />
      </svg>
    ),
    monitor: (
      <svg {...p}>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
        <path d="m7 11 2.1-2.4 2.1 3.8 2.1-5.2 2 3.8H17" />
      </svg>
    ),
    belt: (
      <svg {...p}>
        <rect x="2" y="8" width="20" height="8" rx="3" />
        <circle cx="7" cy="12" r="2" />
        <circle cx="12" cy="12" r="2" />
        <circle cx="17" cy="12" r="2" />
      </svg>
    ),
    chip: (
      <svg {...p}>
        <rect x="7" y="7" width="10" height="10" rx="1" />
        <path d="M9 7V4M12 7V4M15 7V4M9 20v-3M12 20v-3M15 20v-3M4 9h3M4 12h3M4 15h3M17 9h3M17 12h3M17 15h3" />
      </svg>
    ),
    cloud: (
      <svg {...p}>
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
      </svg>
    ),
    brain: (
      <svg {...p}>
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
      </svg>
    ),
    arrow: (
      <svg {...p}>
        <path d="M5 12h14" />
        <path d="m12 5 7 7-7 7" />
      </svg>
    ),
    pressure: (
      <svg {...p}>
        <path d="M12 2v6" />
        <path d="m4.93 10.93 1.41 1.41" />
        <path d="M2 18h2" />
        <path d="M20 18h2" />
        <path d="m19.07 10.93-1.41 1.41" />
        <path d="M22 22H2" />
        <path d="M16 6a4 4 0 0 0-8 0 4 4 0 0 0 2 3.46V18h4v-8.54A4 4 0 0 0 16 6z" />
      </svg>
    ),
    phone: (
      <svg {...p}>
        <rect x="5" y="2" width="14" height="20" rx="2" />
        <path d="M12 18h.01" />
      </svg>
    ),
    battery: (
      <svg {...p}>
        <rect x="2" y="7" width="16" height="10" rx="2" />
        <path d="M22 11v2" />
        <path d="M6 11h8" />
      </svg>
    ),
    database: (
      <svg {...p}>
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
        <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
      </svg>
    ),
    filter: (
      <svg {...p}>
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </svg>
    ),
    check: (
      <svg {...p}>
        <path d="M20 6 9 17l-5-5" />
      </svg>
    ),
    question: (
      <svg {...p}>
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <path d="M12 17h.01" />
      </svg>
    ),
    chevron: (
      <svg {...p}>
        <path d="m6 9 6 6 6-6" />
      </svg>
    ),
    menu: (
      <svg {...p}>
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="18" x2="21" y2="18" />
      </svg>
    ),
    close: (
      <svg {...p}>
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    ),
    arrowUp: (
      <svg {...p}>
        <path d="m18 15-6-6-6 6" />
      </svg>
    ),
    info: (
      <svg {...p}>
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4M12 8h.01" />
      </svg>
    ),
  };

  return icons[name] ?? icons.info;
}

// ─── WAVE DECORATION ─────────────────────────────────────────────────────────

function WaveLine({ variant = "rose" }) {
  return (
    <svg
      className={`fg-wave fg-wave--${variant}`}
      viewBox="0 0 240 64"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <path
        className="fg-wave__grid"
        d="M0 16h240M0 32h240M0 48h240M40 0v64M80 0v64M120 0v64M160 0v64M200 0v64"
      />
      <polyline
        className="fg-wave__line"
        points="0,40 10,38 18,45 28,20 38,42 48,35 56,41 66,23 78,44 88,36 98,39 110,18 124,43 136,41 146,30 158,34 170,22 182,44 194,36 206,39 218,25 230,45 240,32"
      />
    </svg>
  );
}

// ─── ANIMATED COUNTER ─────────────────────────────────────────────────────────

function AnimatedCounter({
  end,
  suffix = "",
  display = null,
  duration = 1600,
}) {
  const [value, setValue] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || display) return; // skip animation when display is override string
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const startTime = performance.now();
          const tick = (now) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - (1 - progress) ** 3;
            setValue(Math.round(eased * end));
            if (progress < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          observer.disconnect();
        }
      },
      { threshold: 0.6 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [end, duration, display]);

  if (display)
    return (
      <span ref={ref}>
        {display}
        {suffix}
      </span>
    );
  return (
    <span ref={ref}>
      {value.toLocaleString("id-ID")}
      {suffix}
    </span>
  );
}

// ─── FAQ ACCORDION ITEM ───────────────────────────────────────────────────────

function FaqItem({ item, isOpen, onToggle, index }) {
  return (
    <div className={`fg-faq__item${isOpen ? " is-open" : ""}`}>
      <button
        className="fg-faq__q"
        type="button"
        aria-expanded={isOpen}
        aria-controls={`faq-body-${index}`}
        onClick={onToggle}
      >
        <span className="fg-faq__q-text">{item.q}</span>
        <span className="fg-faq__chevron" aria-hidden="true">
          <Icon name="chevron" size={18} />
        </span>
      </button>
      <div
        id={`faq-body-${index}`}
        className="fg-faq__body"
        aria-hidden={!isOpen}
      >
        <div className="fg-faq__body-inner">
          <p>{item.a}</p>
        </div>
      </div>
    </div>
  );
}

// ─── LANDING PAGE ─────────────────────────────────────────────────────────────

function LandingPage() {
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const scrollBarRef = useRef(null);

  const [selectedSensor, setSelectedSensor] = useState(SENSOR_DETAILS[0]);
  const [activeStage, setActiveStage] = useState(0);
  const [openFaq, setOpenFaq] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [heroImageReady, setHeroImageReady] = useState(false);
  const [activeSection, setActiveSection] = useState("beranda");

  // ── Scroll progress + scroll-to-top visibility ──
  useEffect(() => {
    const onScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      if (scrollBarRef.current)
        scrollBarRef.current.style.width = `${progress}%`;
      setShowScrollTop(scrollTop > 500);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // ── IntersectionObserver: reveal on scroll ──
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const items = root.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-visible"));
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    items.forEach((el) => observer.observe(el));
    const fallback = window.setTimeout(
      () => items.forEach((el) => el.classList.add("is-visible")),
      2000,
    );
    return () => {
      window.clearTimeout(fallback);
      observer.disconnect();
    };
  }, []);

  // ── IntersectionObserver: active nav section ──
  useEffect(() => {
    const sections = [
      "beranda",
      "urgensi",
      "edukasi",
      "teknologi",
      "alur",
      "cara-pakai",
      "portal",
      "validasi",
      "faq",
    ];
    const observers = sections
      .map((id) => {
        const el = document.getElementById(id);
        if (!el) return null;
        const obs = new IntersectionObserver(
          ([entry]) => {
            if (entry.isIntersecting) setActiveSection(id);
          },
          { threshold: 0.35 },
        );
        obs.observe(el);
        return obs;
      })
      .filter(Boolean);
    return () => observers.forEach((obs) => obs.disconnect());
  }, []);

  // ── Close mobile menu on scroll ──
  useEffect(() => {
    const close = () => setMenuOpen(false);
    window.addEventListener("scroll", close, { passive: true });
    return () => window.removeEventListener("scroll", close);
  }, []);

  const goTo = useCallback((route) => navigate(route), [navigate]);

  const scrollTo = useCallback((id) => {
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    setMenuOpen(false);
  }, []);

  const navLinks = [
    { href: "urgensi", label: "Urgensi" },
    { href: "edukasi", label: "Edukasi" },
    { href: "teknologi", label: "Teknologi" },
    { href: "alur", label: "Alur Sistem" },
    { href: "cara-pakai", label: "Cara Pakai" },
    { href: "validasi", label: "Roadmap" },
    { href: "faq", label: "FAQ" },
  ];

  return (
    <main className="fg-landing" ref={rootRef}>
      {/* ── Scroll progress bar ── */}
      <div className="fg-scroll-bar" aria-hidden="true">
        <div className="fg-scroll-bar__fill" ref={scrollBarRef} />
      </div>

      {/* ── Header ── */}
      <header className="fg-header">
        <a
          className="fg-brand"
          href="#beranda"
          onClick={(e) => {
            e.preventDefault();
            scrollTo("beranda");
          }}
          aria-label="FETAL-GUARD beranda"
        >
          <img
            className="fg-brand__logo"
            src={fetalGuardLogo}
            alt=""
            aria-hidden="true"
          />
          <span>
            <strong>FETAL-GUARD</strong>
            <small>PKM-KC Smart Maternity Belt</small>
          </span>
        </a>

        <nav
          className={`fg-nav${menuOpen ? " fg-nav--open" : ""}`}
          aria-label="Navigasi utama"
        >
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={`#${link.href}`}
              className={activeSection === link.href ? "is-active" : ""}
              onClick={(e) => {
                e.preventDefault();
                scrollTo(link.href);
              }}
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="fg-header__right">
          <button
            className="fg-header__cta"
            type="button"
            onClick={() => scrollTo("portal")}
          >
            Pilih Portal
          </button>
          <button
            className={`fg-menu-toggle${menuOpen ? " is-open" : ""}`}
            type="button"
            aria-label={menuOpen ? "Tutup menu" : "Buka menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            <Icon name={menuOpen ? "close" : "menu"} size={20} />
          </button>
        </div>
      </header>

      {/* Mobile nav drawer */}
      {menuOpen && (
        <div className="fg-nav-drawer" role="dialog" aria-label="Menu navigasi">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={`#${link.href}`}
              onClick={(e) => {
                e.preventDefault();
                scrollTo(link.href);
              }}
            >
              {link.label}
            </a>
          ))}
          <div className="fg-nav-drawer__actions">
            <button type="button" onClick={() => goTo("/login/ibu-hamil")}>
              Portal Pasien
            </button>
            <button type="button" onClick={() => goTo("/login/nakes")}>
              Portal Nakes
            </button>
          </div>
        </div>
      )}

      {/* ── HERO ── */}
      <section id="beranda" className="fg-hero">
        <div className="fg-shell fg-hero__grid">
          <div className="fg-hero__copy" data-reveal>
            <p className="fg-kicker">
              <span className="fg-kicker__dot" aria-hidden="true" />
              PKM Karsa Cipta 2026 · Institut Teknologi Sumatera
            </p>
            <h1>FETAL-GUARD</h1>
            <p className="fg-hero__tagline">
              Wearable untuk Skrining Awal Risiko Feto-Maternal
            </p>
            <p className="fg-hero__lead">
              Sabuk pintar berbasis sensor piezoelektrik, FSR, dan MAX30102
              untuk memantau DJJ/FHR, indikator kontraksi, dan vital ibu secara
              non-invasif langsung dari rumah.
            </p>
            <div className="fg-hero__actions">
              <button
                className="fg-button fg-button--primary"
                type="button"
                onClick={() => goTo("/login/ibu-hamil")}
              >
                <Icon name="user" size={18} />
                Portal Ibu Hamil
              </button>
              <button
                className="fg-button fg-button--secondary"
                type="button"
                onClick={() => goTo("/login/nakes")}
              >
                <Icon name="monitor" size={18} />
                Portal Nakes
              </button>
            </div>
            <div className="fg-safety-note">
              <Icon name="shield" size={18} />
              <span>
                Alat skrining awal — tidak menggantikan pemeriksaan dokter,
                bidan, CTG, Doppler, USG, atau fasilitas kesehatan.
              </span>
            </div>
          </div>

          <div
            className="fg-hero__visual"
            data-reveal
            data-active-sensor={selectedSensor.id}
          >
            <div className="fg-product-stage">
              <div
                className={
                  heroImageReady
                    ? "fg-belt-fallback"
                    : "fg-belt-fallback is-visible"
                }
                aria-hidden="true"
              >
                <span className="fg-belt-fallback__strap" />
                <span className="fg-belt-fallback__module fg-belt-fallback__module--one" />
                <span className="fg-belt-fallback__module fg-belt-fallback__module--two" />
                <span className="fg-belt-fallback__module fg-belt-fallback__module--three" />
              </div>
              <img
                className={heroImageReady ? "is-loaded" : ""}
                src={beltConcept}
                alt="Konsep sabuk pintar FETAL-GUARD"
                onLoad={() => setHeroImageReady(true)}
                onError={() => setHeroImageReady(false)}
              />
              {SENSOR_DETAILS.map((sensor) => (
                <button
                  key={sensor.id}
                  type="button"
                  className={`fg-sensor-pin fg-sensor-pin--${sensor.id}${selectedSensor.id === sensor.id ? " is-active" : ""}`}
                  onClick={() => setSelectedSensor(sensor)}
                  aria-label={`Sensor ${sensor.label}`}
                >
                  <span />
                </button>
              ))}
            </div>
            <div className="fg-live-panel">
              <div>
                <span className="fg-live-panel__label">Sinyal simulasi</span>
                <strong>{selectedSensor.label}</strong>
              </div>
              <WaveLine variant={selectedSensor.tone} />
            </div>
          </div>
        </div>
      </section>

      {/* ── URGENSI ── */}
      <section id="urgensi" className="fg-section fg-section--soft">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Mengapa Dibutuhkan</p>
          <h2>Dari masalah global ke kebutuhan pemantauan yang lebih dekat.</h2>
          <p>
            Stillbirth adalah konteks kesehatan publik yang serius. FETAL-GUARD
            mengambil posisi yang aman: membaca sinyal awal, menampilkan tren,
            lalu mendorong tindak lanjut tenaga kesehatan.
          </p>
        </div>

        <div className="fg-shell fg-stat-grid">
          {STATS.map((stat) => (
            <article
              className={`fg-stat-card fg-stat-card--${stat.color}`}
              key={stat.label}
              data-reveal
            >
              <div className="fg-stat-card__icon">
                <Icon name={stat.icon} size={24} />
              </div>
              <strong className="fg-stat-card__value">
                <AnimatedCounter
                  end={stat.numeric}
                  suffix={stat.suffix}
                  display={stat.display}
                />
              </strong>
              <h3>{stat.label}</h3>
              <p>{stat.note}</p>
            </article>
          ))}
        </div>

        <div className="fg-shell fg-storyline" data-reveal>
          <article className="fg-storyline__step">
            <span>1</span>
            <h3>Masalahnya bukan hanya angka</h3>
            <p>
              Penilaian feto-maternal perlu mempertimbangkan keluhan, pemeriksaan
              langsung, dan perubahan dari waktu ke waktu. Data wearable hanya
              menjadi informasi tambahan untuk skrining awal.
            </p>
          </article>
          <article className="fg-storyline__step">
            <span>2</span>
            <h3>Sinyal perlu dipisahkan</h3>
            <p>
              Denyut ibu, getaran DJJ janin, tekanan sabuk, dan noise gerakan
              harus dibedakan secara hati-hati oleh algoritma preprocessing.
            </p>
          </article>
          <article className="fg-storyline__step">
            <span>3</span>
            <h3>Output harus aman</h3>
            <p>
              Hasil sistem dibatasi sebagai status skrining awal: data tersedia,
              perlu pemantauan ulang, atau segera konsultasi.
            </p>
          </article>
        </div>

        <div className="fg-shell">
          <p className="fg-source" data-reveal>
            Sumber data statistik:{" "}
            <a
              href="https://data.unicef.org/topic/child-survival/stillbirths/"
              target="_blank"
              rel="noreferrer"
            >
              UNICEF — Stillbirth Estimates
            </a>
            . Angka digunakan sebagai konteks kesehatan publik, bukan klaim
            validasi FETAL-GUARD.
          </p>
        </div>
      </section>

      {/* ── EDUKASI: PEMANTAUAN JANIN & KONTRAKSI ── */}
      <section id="edukasi" className="fg-section">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Edukasi Kesehatan</p>
          <h2>Memahami perubahan kondisi dan kontraksi rahim.</h2>
          <p>
            Pengetahuan dasar tentang kondisi janin membantu ibu hamil mengenali
            kapan harus segera menghubungi tenaga kesehatan — bukan menunggu
            hingga terlambat.
          </p>
        </div>

        <div className="fg-shell fg-edu-grid">
          {MONITORING_EDUCATION_CARDS.map((card, i) => (
            <article
              className={`fg-edu-card fg-edu-card--${card.color}`}
              key={card.title}
              data-reveal
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="fg-edu-card__header">
                <span className="fg-edu-card__tag">{card.tag}</span>
                <div className="fg-edu-card__icon">
                  <Icon name={card.icon} size={20} />
                </div>
              </div>
              <h3>{card.title}</h3>
              <p>{card.body}</p>
            </article>
          ))}
        </div>

        <div className="fg-shell fg-edu-divider" data-reveal>
          <span>Memahami Kontraksi Rahim</span>
        </div>

        <div className="fg-shell fg-contraction-grid">
          {CONTRACTION_CARDS.map((card, i) => (
            <article
              className="fg-contraction-card"
              key={card.title}
              data-reveal
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div
                className={`fg-contraction-card__dot fg-contraction-card__dot--${card.dot}`}
                aria-hidden="true"
              />
              <div className="fg-contraction-card__icon">
                <Icon name={card.icon} size={18} />
              </div>
              <div className="fg-contraction-card__copy">
                <h3>{card.title}</h3>
                <small>{card.subtitle}</small>
                <p>{card.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* ── TEKNOLOGI SENSOR ── */}
      <section id="teknologi" className="fg-section fg-section--soft">
        <div className="fg-shell fg-sensor-layout">
          <div
            className="fg-section__intro fg-section__intro--left"
            data-reveal
          >
            <p className="fg-kicker">Teknologi Sensor</p>
            <h2>Tiga sumber sinyal, satu status skrining awal.</h2>
            <p>
              Setiap kanal punya peran dan batasan berbeda. Pilih sensor untuk
              melihat cara kerja dan keterbatasan interpretasinya.
            </p>
          </div>

          <div className="fg-sensor-tabs" data-reveal>
            {SENSOR_DETAILS.map((sensor) => (
              <button
                key={sensor.id}
                type="button"
                className={`fg-sensor-tab fg-sensor-tab--${sensor.tone}${selectedSensor.id === sensor.id ? " is-active" : ""}`}
                onClick={() => setSelectedSensor(sensor)}
              >
                <span>{sensor.label}</span>
                <small>{sensor.short}</small>
              </button>
            ))}
          </div>

          <article
            className={`fg-sensor-detail fg-sensor-detail--${selectedSensor.tone}`}
            aria-live="polite"
          >
            <div className="fg-sensor-detail__metric">
              <span>{selectedSensor.metric}</span>
              <strong>{selectedSensor.value}</strong>
            </div>
            <div className="fg-sensor-detail__icon">
              <Icon name={selectedSensor.icon} size={28} />
            </div>
            <h3>{selectedSensor.title}</h3>
            <p>{selectedSensor.body}</p>
            <ul className="fg-sensor-checklist">
              {selectedSensor.checklist.map((item) => (
                <li key={item}>
                  <Icon name="check" size={14} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <WaveLine variant={selectedSensor.tone} />
          </article>
        </div>
      </section>

      {/* ── ALUR SISTEM ── */}
      <section id="alur" className="fg-section">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Alur Sistem</p>
          <h2>Dari sabuk wearable ke aplikasi dan dashboard.</h2>
          <p>
            Arsitektur prototipe ditampilkan secara jujur: akuisisi sinyal,
            transmisi, analisis AI, lalu tampilan yang dipisahkan berdasarkan
            peran pengguna.
          </p>
        </div>

        <div className="fg-shell fg-flow" data-reveal>
          <div
            className="fg-flow__track"
            role="tablist"
            aria-label="Tahap alur sistem"
          >
            {SYSTEM_FLOW.map((stage, index) => (
              <div
                className="fg-flow__node"
                key={stage.title}
                style={{ "--flow-i": index }}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeStage === index}
                  className={`fg-flow-card${activeStage === index ? " is-active" : ""}`}
                  onClick={() => setActiveStage(index)}
                >
                  <span className="fg-flow-card__number">{index + 1}</span>
                  <span className="fg-flow-card__icon">
                    <Icon name={stage.icon} size={20} />
                  </span>
                  <small>{stage.label}</small>
                  <strong>{stage.title}</strong>
                </button>
                {index < SYSTEM_FLOW.length - 1 && (
                  <span className="fg-flow__arrow" aria-hidden="true">
                    <Icon name="arrow" size={16} />
                  </span>
                )}
              </div>
            ))}
          </div>
          <article
            className="fg-flow__detail"
            role="tabpanel"
            aria-live="polite"
          >
            <span className="fg-flow__detail-badge">
              Tahap {activeStage + 1} — {SYSTEM_FLOW[activeStage].label}
            </span>
            <h3>{SYSTEM_FLOW[activeStage].title}</h3>
            <p>{SYSTEM_FLOW[activeStage].detail}</p>
          </article>
        </div>
      </section>

      {/* ── CARA PAKAI ── */}
      <section id="cara-pakai" className="fg-section fg-section--soft">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Cara Penggunaan</p>
          <h2>Empat langkah untuk memulai sesi pemantauan.</h2>
          <p>
            Dirancang untuk ibu hamil yang ingin memantau kondisi janin secara
            mandiri di rumah antara kunjungan ANC rutin ke fasilitas kesehatan.
          </p>
        </div>
        <div className="fg-shell fg-howto-grid">
          {HOW_TO_USE.map((step, i) => (
            <article
              className={`fg-howto-card fg-howto-card--${step.color}`}
              key={step.step}
              data-reveal
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="fg-howto-card__step">{step.step}</div>
              <div className="fg-howto-card__icon">
                <Icon name={step.icon} size={22} />
              </div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
        <div className="fg-shell fg-howto-note" data-reveal>
          <Icon name="info" size={16} />
          <span>
            Sesi idealnya dilakukan dalam posisi duduk atau berbaring tenang.
            Hindari banyak bergerak selama pemantauan berlangsung untuk menjaga
            kualitas sinyal.
          </span>
        </div>
      </section>

      {/* ── PORTAL ── */}
      <section id="portal" className="fg-section">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Pilih Portal</p>
          <h2>Dua domain, dua pengalaman yang berbeda.</h2>
          <p>
            Pasien dan tenaga kesehatan memiliki alur, data, dan tampilan yang
            sepenuhnya terpisah.
          </p>
        </div>
        <div className="fg-shell fg-portal-grid">
          {PORTAL_CARDS.map((portal) => (
            <article
              className={`fg-portal-card fg-portal-card--${portal.color}`}
              key={portal.title}
              data-reveal
            >
              <p className="fg-portal-card__eyebrow">{portal.eyebrow}</p>
              <div className="fg-portal-card__icon">
                <Icon name={portal.icon} size={28} />
              </div>
              <h2>{portal.title}</h2>
              <p>{portal.body}</p>
              <button
                type="button"
                className={`fg-portal-card__btn fg-portal-card__btn--${portal.color}`}
                onClick={() => goTo(portal.route)}
              >
                {portal.action}
                <Icon name="arrow" size={16} />
              </button>
            </article>
          ))}
        </div>
      </section>

      {/* ── ROADMAP & VALIDASI ── */}
      <section id="validasi" className="fg-section fg-section--soft">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Roadmap & Validasi</p>
          <h2>
            Prototipe yang harus berkembang bertahap sebelum dipakai di
            lapangan.
          </h2>
          <p>
            Validasi klinis, kualitas sinyal, keselamatan wearable, dan keamanan
            data adalah bagian utama dari pengembangan berkelanjutan.
          </p>
        </div>
        <div className="fg-shell fg-roadmap">
          {ROADMAP_STEPS.map((step) => (
            <div
              className={`fg-roadmap__step${step.done ? " is-done" : ""}`}
              key={step.title}
              data-reveal
            >
              <div className="fg-roadmap__indicator">
                <span className="fg-roadmap__number">{step.step}</span>
                {step.done && (
                  <span className="fg-roadmap__done-badge" aria-label="Selesai">
                    <Icon name="check" size={10} />
                  </span>
                )}
              </div>
              <div className="fg-roadmap__icon">
                <Icon name={step.icon} size={18} />
              </div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="fg-section">
        <div className="fg-shell fg-section__intro" data-reveal>
          <p className="fg-kicker">Pertanyaan Umum</p>
          <h2>Hal-hal yang sering ditanyakan tentang FETAL-GUARD.</h2>
        </div>
        <div className="fg-shell fg-faq" data-reveal>
          {FAQ_ITEMS.map((item, index) => (
            <FaqItem
              key={item.q}
              item={item}
              index={index}
              isOpen={openFaq === index}
              onToggle={() => setOpenFaq(openFaq === index ? null : index)}
            />
          ))}
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="fg-footer">
        <div className="fg-shell fg-footer__grid">
          <div className="fg-footer__brand">
            <img src={fetalGuardLogo} alt="" aria-hidden="true" width="40" />
            <div>
              <strong>FETAL-GUARD</strong>
              <p>Prototype PKM-KC 2026 · Institut Teknologi Sumatera</p>
            </div>
          </div>
          <nav className="fg-footer__nav" aria-label="Navigasi footer">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={`#${link.href}`}
                onClick={(e) => {
                  e.preventDefault();
                  scrollTo(link.href);
                }}
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="fg-footer__disclaimer">
            <p>
              <strong>Disclaimer Medis:</strong> FETAL-GUARD bukan alat
              kesimpulan medis definitif dan tidak menggantikan CTG,
              tocotransducer, Doppler, USG, dokter, bidan, atau fasilitas rumah
              sakit. Setiap indikasi risiko yang muncul harus dikonfirmasi
              melalui pemeriksaan oleh tenaga kesehatan. Sistem ini dikembangkan
              sebagai prototype skrining awal dalam kerangka PKM Karsa Cipta.
            </p>
          </div>
        </div>
        <div className="fg-footer__bottom">
          <span>© 2026 FETAL-GUARD · PKM-KC · Institut Teknologi Sumatera</span>
          <div className="fg-footer__portal-links">
            <button type="button" onClick={() => goTo("/login/ibu-hamil")}>
              Portal Pasien
            </button>
            <span aria-hidden="true">·</span>
            <button type="button" onClick={() => goTo("/login/nakes")}>
              Portal Nakes
            </button>
          </div>
        </div>
      </footer>

      {/* ── Scroll to top ── */}
      {showScrollTop && (
        <button
          className="fg-scroll-top"
          type="button"
          aria-label="Kembali ke atas"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          <Icon name="arrowUp" size={20} />
        </button>
      )}
    </main>
  );
}

export default LandingPage;
