// aiService.js — panggil dari MonitoringScreen atau komponen lain.
// Sesuai schema response yang sudah dirapikan di main.py (langkah 6).

const API_BASE = "https://api.domainanda.com"; // ganti sesuai VPS Anda (langkah 11)

export async function sendReading(deviceId, fhrBpm, mhrBpm, ucPer10min) {
  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_id: deviceId,
      fhr_bpm: fhrBpm,
      mhr_bpm: mhrBpm,
      uc_per_10min: ucPer10min,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json(); // { status, device_id, timestamp, buffer_count?, prediction? }
}

export async function getBufferStatus(deviceId) {
  const res = await fetch(`${API_BASE}/api/buffer-status/${deviceId}`);
  return res.json();
}

// Contoh pemakaian di MonitoringScreen (polling tiap ada data baru dari
// backend Anda sendiri, ATAU langsung dari sini kalau ESP32 kirim ke sini juga):
//
//   const result = await sendReading("esp32-ctg-01", 135, 88, 3.5);
//   if (result.status === "predicted") {
//     setFetalStatus(result.prediction.overall.status);       // "Normal" | "Abnormal"
//     setFhrValue(result.prediction.fhr.status);               // "Normal"/"Bradycardia"/"Tachycardia"
//     setConfidence(result.prediction.overall.confidence);     // 0-1
//   } else {
//     setBufferInfo(`${result.buffer_count}/${result.buffer_needed}`);
//   }

// --- Ditambahkan: polling hasil terbaru (dipakai kalau ESP32 kirim
// langsung ke backend, bukan lewat website Anda) ---
export async function getLatest(deviceId) {
  const res = await fetch(`${API_BASE}/api/latest/${deviceId}`);
  if (res.status === 404) return null; // belum ada data masuk
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Contoh dipakai di useEffect MonitoringScreen:
//   useEffect(() => {
//     const interval = setInterval(async () => {
//       const data = await getLatest("esp32-ctg-01");
//       if (data?.status === "predicted") {
//         setFhrStatus(data.prediction.fhr.status);
//         setOverallStatus(data.prediction.overall.status);
//       }
//     }, 2000);
//     return () => clearInterval(interval);
//   }, []);
