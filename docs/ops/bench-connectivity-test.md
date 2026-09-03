# Uji Konektivitas Bench (Tanpa Sensor)

Panduan membuktikan jalur ESP32-S3 → BLE → aplikasi pasien → backend → dashboard
nakes bekerja, sebelum sensor fisik selesai dirancang.

**Yang diuji:** transport, penautan perangkat, ingestion, derivasi vital, alert,
dan tampilan di kedua sisi.

**Yang TIDAK diuji:** akuisisi sinyal. Gelombang yang dipakai sintetis. Angkanya
bukan pengukuran apa pun dan tidak boleh disajikan sebagai data klinis.

---

## Tahap 0 — Dashboard hidup tanpa ESP32

Jalankan ini lebih dulu. Kalau dashboard tetap kosong di tahap ini, masalahnya
bukan pada firmware, dan Anda menghemat berjam-jam debugging perangkat.

### 1. Jalankan stack lokal

```powershell
npm.cmd run local
```

Backend di `http://127.0.0.1:3020`, frontend di `http://127.0.0.1:5173`.

### 2. Siapkan akun

```powershell
npm.cmd run local:staff
```

Lalu daftarkan **pasien uji** lewat portal pasien di browser, dan lengkapi
profilnya. Gunakan akun terpisah dari akun demo mana pun.

### 3. Provision perangkat bench

```powershell
cd backend
.\venv\Scripts\python.exe provision_devices.py --count 1 --prefix FG-BENCH `
  --hardware bench-demo --firmware demo-0.1 --out batch-bench.csv
```

CSV berisi `claim_code` dan `packet_secret` dalam teks terang. Perlakukan sebagai
file kredensial: pakai, lalu hapus.

`hardware_revision = bench-demo` adalah penanda provenance-nya. Nanti, saat perlu
memisahkan data uji dari data nyata, filter pada kolom itu.

### 4. Tautkan perangkat dari aplikasi pasien

Buka aplikasi pasien → Beranda → Pindai perangkat. Karena belum ada perangkat
BLE menyala, gunakan jalur API langsung untuk tahap 0:

```powershell
$body = @{ device_uid = "FG-BENCH-001"; claim_code = "<claim_code dari CSV>" } | ConvertTo-Json
# Login dulu untuk mendapatkan access token, lalu:
# POST http://127.0.0.1:3020/devices/claim dengan header Authorization: Bearer <token>
```

Atau lebih mudah: biarkan script tahap 0 yang melakukannya dengan `--claim-code`.

### 5. Alirkan telemetry

```powershell
npm.cmd run simulate:belt -- --email pasien.uji@example.com --password "<password>" `
  --device-uid FG-BENCH-001 --claim-code "<claim_code>" `
  --packet-secret "<packet_secret>" --drift --contractions
```

Script akan login, menautkan perangkat bila perlu, membuka sesi, lalu mengirim
satu paket telemetry v2 per detik.

### 6. Yang harus terlihat

| Di mana | Yang diharapkan |
|---|---|
| Aplikasi pasien → Monitoring | Sesi aktif, paket masuk |
| Setelah ~10 detik | `fhr_estimate_bpm` terisi (~140 bpm), kualitas sinyal terisi |
| Setelah ~60 detik dengan `--drift` | DJJ turun di bawah 110 bpm |
| Dashboard nakes → Alerts | Muncul alert "Estimasi DJJ ... di bawah rentang rujukan" |
| Dashboard nakes | Hanya untuk pasien yang di-assign ke nakes tersebut |

Jika DJJ tetap "belum tersedia" setelah 15 detik, periksa `derivation_status`
pada ringkasan sesi:

- `unsupported_schema` → paket terkirim sebagai v1; derivasi butuh v2
- `insufficient_signal` → sinyal masuk tapi tidak cukup periodik
- `pending` → belum cukup data terkumpul

---

## Tahap 1 — ESP32-S3 lewat BLE

### 1. Siapkan sketch

Buka `fetalguard-demo/fetalguard-demo.ino`, isi dua konstanta dari CSV:

```cpp
const char *FG_DEVICE_UID = "FG-BENCH-001";
const char *FG_DEVICE_PACKET_SECRET = "<packet_secret dari CSV>";
```

### 2. Flash

Board: ESP32-S3 Dev Module. Tidak perlu sensor terpasang. Buka Serial Monitor
pada 115200 baud; perangkat akan mencetak boot ID dan mulai advertising.

### 3. Hubungkan dari aplikasi pasien

Aplikasi pasien → Beranda → Pindai perangkat → sabuk muncul → **Tautkan
perangkat** → masukkan claim code dari CSV → Hubungkan → Mulai sesi.

Setelah tertaut sekali, sesi berikutnya langsung connect tanpa kode.

### 4. Yang harus terlihat di Serial Monitor

```
[BLE] Gateway terhubung; menunggu sinkronisasi waktu.
[BLE] Waktu tersinkronisasi.
[BLE] Telemetry v2 aktif; fragment bytes: 180
[TX] seq 1  bytes 6842  fhr 140.0 bpm (sintetis)
```

Kalau berhenti di "menunggu sinkronisasi waktu", gateway belum menulis perintah
`T<epoch_ms>` — periksa izin Bluetooth di Android.

Kalau v2 tidak pernah aktif, negosiasi `V2:<bytes>` ditolak — biasanya karena
sinkronisasi waktu belum selesai.

---

## Yang perlu diukur selagi menguji

Ini metrik yang roadmap minta tapi sampai sekarang masih asumsi. Bench test
adalah kesempatan pertama mengukurnya:

- **Latency** sensor → dashboard: bandingkan `captured_at` paket dengan waktu
  kemunculannya di dashboard nakes
- **Packet loss**: `sequence_number` yang hilang di backend dibanding yang
  dicetak ESP32 di Serial Monitor
- **Jarak BLE**: jarak maksimum sebelum reconnect mulai sering
- **Perilaku reconnect**: matikan ESP32 di tengah sesi, hidupkan lagi
- **Drift sesi panjang**: jalankan 1–2 jam, periksa apakah `captured_at` melenceng
- **Stabilitas memori**: heap ESP32 setelah ribuan frame

Catat hasilnya. Tanpa angka, klaim latency dan packet loss tetap tidak boleh dibuat.

---

## Batasan yang harus tetap disebut

- Sketch demo tidak membaca sensor. Ia membuktikan transport, bukan akuisisi.
- Estimator FHR **belum tervalidasi** terhadap CTG, Doppler, atau sinyal referensi
  mana pun. Demo yang mulus bukan berarti sistem siap klinis.
- Kode klaim membuktikan penguasaan fisik perangkat, bukan identitas pemegangnya.
- Belum ada BLE bonding/pairing. Penandatanganan paket menutup spoofing di batas
  API, bukan di lapisan radio.
- Kode C++ penandatanganan di firmware belum pernah dikompilasi terhadap hardware
  nyata; kecocokannya dengan backend baru terbukti untuk implementasi Python dan
  Node, bukan C++.

---

## Setelah bench test lolos

1. Deploy backend ke Azure staging (CI sudah terpasang), ulangi tahap 1
   melawannya. Perbedaan TLS, `TRUSTED_HOSTS`, dan CORS adalah tempat kejutan
   biasanya muncul — jangan tunda sampai akhir.
2. Naikkan dari gelombang sintetis ke **input analog nyata** (function generator
   atau speaker kecil ke ADC). Effort-nya sama, tapi ikut menguji jalur akuisisi.
3. Baru setelah itu, tangga validasi di `FETAL_GUARD_ROADMAP.md` Milestone 9.
