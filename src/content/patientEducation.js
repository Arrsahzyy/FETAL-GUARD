const SOURCES = {
  kia2024: {
    organization: "Kementerian Kesehatan RI",
    title: "Buku Kesehatan Ibu dan Anak (KIA), Edisi 2024",
    url: "https://kesprimkom.kemkes.go.id/konten/145/143/0/buku-kesehatan-ibu-dan-anak-kia",
  },
  whoAnc: {
    organization: "World Health Organization",
    title: "Recommendations on antenatal care for a positive pregnancy experience",
    url: "https://www.who.int/publications/i/item/9789241549912",
  },
  acogExercise: {
    organization: "American College of Obstetricians and Gynecologists",
    title: "Exercise During Pregnancy",
    url: "https://www.acog.org/womens-health/faqs/exercise-during-pregnancy",
  },
};

const ARTICLES = [
  {
    id: "antenatal-care",
    icon: "calendar_month",
    tone: "blue",
    category: "care",
    weekFrom: 1,
    weekTo: 42,
    sourceIds: ["kia2024", "whoAnc"],
    content: {
      id: {
        title: "Jangan lewatkan pemeriksaan kehamilan",
        summary: "Catat jadwal berikutnya dan bawa Buku KIA.",
        action: "Simpan tanggal kontrol dan siapkan Buku KIA sebelum berangkat.",
        caution: "Aplikasi dan sabuk tidak menggantikan pemeriksaan dokter atau bidan.",
        urgent: "Keluhan berat atau berbeda? Hubungi fasilitas tanpa menunggu jadwal.",
      },
      en: {
        title: "Keep your antenatal appointments",
        summary: "Note your next visit and bring your maternal health book.",
        action: "Save the date and prepare your maternal health book.",
        caution: "The app and belt do not replace a doctor or midwife.",
        urgent: "A severe or unusual symptom appears. Contact your care facility.",
      },
    },
  },
  {
    id: "balanced-nutrition",
    icon: "nutrition",
    tone: "green",
    category: "nutrition",
    weekFrom: 1,
    weekTo: 42,
    sourceIds: ["kia2024", "whoAnc"],
    content: {
      id: {
        title: "Makan beragam setiap hari",
        summary: "Pilih makanan pokok, protein, sayur, dan buah.",
        action: "Susun menu beragam dan minum cukup sesuai arahan tenaga kesehatan.",
        caution: "Jangan menambah suplemen atau jamu tanpa berkonsultasi.",
        urgent: "Muntah membuat sulit makan atau minum. Hubungi tenaga kesehatan.",
      },
      en: {
        title: "Eat a variety of foods daily",
        summary: "Choose staple foods, protein, vegetables, and fruit.",
        action: "Vary your meals and drink enough, following care-team advice.",
        caution: "Do not add supplements or herbs without advice.",
        urgent: "Vomiting makes eating or drinking difficult. Contact your care team.",
      },
    },
  },
  {
    id: "safe-activity",
    icon: "directions_walk",
    tone: "amber",
    category: "activity",
    weekFrom: 1,
    weekTo: 42,
    sourceIds: ["whoAnc", "acogExercise"],
    content: {
      id: {
        title: "Bergerak aman sesuai kondisi",
        summary: "Pilih gerakan stabil dan mulai perlahan.",
        action: "Pilih aktivitas yang nyaman dan sesuai arahan tenaga kesehatan.",
        caution: "Hindari benturan perut, risiko jatuh, dan gerakan menghentak.",
        urgent: "Terjadi perdarahan, pusing, nyeri dada, kontraksi nyeri, atau keluar cairan.",
      },
      en: {
        title: "Move safely for your condition",
        summary: "Choose stable movements and start slowly.",
        action: "Choose comfortable activity that follows your care team's advice.",
        caution: "Avoid abdominal impact, fall risks, and jerky movement.",
        urgent: "Bleeding, dizziness, chest pain, painful contractions, or fluid leakage occurs.",
      },
    },
  },
  {
    id: "fetal-movement",
    icon: "child_friendly",
    tone: "pink",
    category: "monitoring",
    weekFrom: 20,
    weekTo: 42,
    sourceIds: ["kia2024"],
    content: {
      id: {
        title: "Kenali pola gerak bayi",
        summary: "Perhatikan perubahan dari pola yang biasanya Anda rasakan.",
        action: "Ikuti cara pemantauan yang diberikan dokter atau bidan.",
        caution: "Jangan menunda pemeriksaan karena angka sabuk terlihat baik.",
        urgent: "Gerak berkurang atau berubah dari biasanya. Hubungi tenaga kesehatan segera.",
      },
      en: {
        title: "Know your baby's movement pattern",
        summary: "Notice changes from the pattern you usually feel.",
        action: "Follow the monitoring method given by your doctor or midwife.",
        caution: "Do not delay care because a belt reading looks reassuring.",
        urgent: "Movement decreases or changes from usual. Contact your care team promptly.",
      },
    },
  },
  {
    id: "warning-signs",
    icon: "health_and_safety",
    tone: "red",
    category: "safety",
    weekFrom: 1,
    weekTo: 42,
    sourceIds: ["kia2024"],
    content: {
      id: {
        title: "Kenali tanda yang perlu pertolongan",
        summary: "Perdarahan, kejang, sesak, atau nyeri berat perlu dinilai langsung.",
        action: "Simpan nomor fasilitas dan beri tahu keluarga.",
        caution: "Jangan menunggu notifikasi saat keluhan mengkhawatirkan.",
        urgent: "Terjadi perdarahan, kejang, sesak, nyeri berat, keluar cairan, atau gerak bayi berkurang.",
      },
      en: {
        title: "Know the signs that need help",
        summary: "Bleeding, seizures, breathlessness, or severe pain need direct assessment.",
        action: "Save your care facility's number and tell your family.",
        caution: "Do not wait for a notification when a symptom worries you.",
        urgent: "Bleeding, seizures, breathlessness, severe pain, fluid leakage, or reduced movement occurs.",
      },
    },
  },
  {
    id: "medicines-herbs",
    icon: "medication",
    tone: "purple",
    category: "nutrition",
    weekFrom: 1,
    weekTo: 42,
    sourceIds: ["kia2024", "whoAnc"],
    content: {
      id: {
        title: "Periksa obat, jamu, dan suplemen",
        summary: "Tanyakan sebelum memulai atau mengubah penggunaannya.",
        action: "Catat semua produk dan tunjukkan saat kontrol.",
        caution: "Jangan mulai, berhenti, atau mengubah dosis obat sendiri.",
        urgent: "Muncul sesak, bengkak wajah, pingsan, atau reaksi berat.",
      },
      en: {
        title: "Check medicines, herbs, and supplements",
        summary: "Ask before starting or changing how you use them.",
        action: "List every product and show it at your appointment.",
        caution: "Do not start, stop, or change medicine doses yourself.",
        urgent: "Breathing difficulty, facial swelling, fainting, or a severe reaction occurs.",
      },
    },
  },
  {
    id: "birth-plan",
    icon: "event_available",
    tone: "teal",
    category: "care",
    weekFrom: 28,
    weekTo: 42,
    sourceIds: ["kia2024"],
    content: {
      id: {
        title: "Siapkan rencana persalinan",
        summary: "Tentukan fasilitas, transportasi, pendamping, dan nomor bantuan.",
        action: "Diskusikan rencana dan barang bawaan dengan keluarga.",
        caution: "Sesuaikan rencana dengan arahan fasilitas kesehatan.",
        urgent: "Tanda persalinan atau tanda bahaya muncul. Hubungi fasilitas.",
      },
      en: {
        title: "Prepare your birth plan",
        summary: "Choose a facility, transport, companion, and help number.",
        action: "Discuss the plan and what to bring with your family.",
        caution: "Align the plan with your care facility's advice.",
        urgent: "Labour or warning signs appear. Contact your care facility.",
      },
    },
  },
];

const normalizeLocale = (locale) => (locale === "en" ? "en" : "id");

export const getEducationArticles = (locale = "id") => {
  const normalizedLocale = normalizeLocale(locale);

  return ARTICLES.map(({ content, sourceIds, ...article }) => ({
    ...article,
    ...content[normalizedLocale],
    sources: sourceIds.map((sourceId) => SOURCES[sourceId]),
  }));
};

export const getWeeklyEducationArticle = (pregnancyWeek, locale = "id") => {
  const articles = getEducationArticles(locale);
  const parsedWeek = Number(pregnancyWeek);

  if (!Number.isFinite(parsedWeek) || parsedWeek < 1 || parsedWeek > 42) {
    return articles.find((article) => article.id === "antenatal-care");
  }

  const week = Math.round(parsedWeek);
  const eligible = articles.filter(
    (article) => week >= article.weekFrom && week <= article.weekTo,
  );

  return eligible[(week - 1) % eligible.length];
};

export const EDUCATION_REFERENCE_CHECKED_AT = "2026-08-09";
