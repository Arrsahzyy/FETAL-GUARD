# Konteks AI Proyek FETAL-GUARD

Dokumen ini adalah ringkasan terstruktur dari proposal PKM-KC **FETAL-GUARD**. Tujuannya bukan menyalin mentah seluruh proposal, tetapi mengubah isi dan ide proposal menjadi dokumen konteks yang mudah ditempelkan ke AI untuk brainstorming, penyusunan roadmap, revisi proposal, perancangan teknis, validasi, dan pengembangan prototipe.

> Catatan privasi: biodata personal seperti alamat, nomor HP, email, tanda tangan, dan detail administratif pribadi tidak dicantumkan karena tidak diperlukan sebagai konteks teknis AI. Nama tim dan pembagian tugas tetap diringkas karena relevan untuk manajemen proyek.

---

## 1. Identitas Singkat Proyek

**Nama alat:** FETAL-GUARD  
**Jenis program:** PKM-KC / Karsa Cipta  
**Bentuk inovasi:** Sabuk pintar / wearable maternity belt untuk pemantauan feto-maternal.  
**Target pengguna utama:** Ibu hamil dan tenaga kesehatan.  
**Fokus pemantauan:** Denyut jantung janin (DJJ/FHR), indikator kontraksi rahim, dan parameter vital ibu.  
**Konsep utama:** Early warning system portabel berbasis multisensor, IoT, dashboard, dan hybrid deep learning CNN-LSTM.  
**Tujuan penggunaan:** Deteksi risiko dini dan pemantauan awal, bukan menggantikan diagnosis dokter atau alat klinis rumah sakit.

FETAL-GUARD dirancang sebagai sistem wearable non-invasif untuk membantu pemantauan kondisi janin secara real-time dan berkelanjutan, terutama pada konteks keterbatasan akses alat klinis seperti CTG, Doppler, atau pemeriksaan rumah sakit yang periodik.

---

## 2. Latar Belakang Masalah

Proposal menempatkan masalah utama pada masih tingginya risiko komplikasi perinatal, stillbirth, intrauterine fetal death (IUFD), dan fetal distress. Fetal distress dipahami sebagai kondisi gangguan oksigenasi atau sirkulasi darah janin yang dapat ditandai dari perubahan pola denyut jantung janin. Oleh karena itu, DJJ/FHR menjadi parameter penting untuk pemantauan kesejahteraan janin.

Masalah yang diangkat:

1. **Stillbirth dan IUFD masih menjadi isu serius.** Proposal menyebut stillbirth sebagai masalah global dan komplikasi perinatal sebagai masalah yang perlu dideteksi lebih awal.
2. **Pemantauan klinis masih bersifat periodik.** USG, Doppler, dan CTG umumnya dilakukan di fasilitas kesehatan dan memerlukan tenaga profesional.
3. **CTG/Doppler memiliki keterbatasan untuk pemantauan mandiri.** CTG relatif akurat tetapi besar, kurang portabel, memerlukan interpretasi tenaga medis, dan tidak ideal untuk penggunaan mandiri jangka panjang. Doppler lebih portabel tetapi bergantung pada operator dan kualitas sinyal.
4. **Wearable yang sudah ada masih terbatas.** Beberapa wearable hanya fokus pada DJJ, belum menggabungkan kontraksi rahim, vital ibu, IoT, dashboard, dan AI dalam satu ekosistem.
5. **Sinyal biologis janin lemah dan rentan noise.** Getaran jantung janin yang ditangkap sensor pasif mudah terganggu oleh posisi janin, gerakan ibu, gesekan sabuk, bising tubuh, dan noise lingkungan.

---

## 3. Rumusan Masalah Proposal

Proposal merumuskan tiga masalah utama:

1. Bagaimana merancang sabuk pintar yang aman untuk memantau detak jantung janin dan indikator kontraksi secara real-time?
2. Bagaimana mengimplementasikan model kecerdasan buatan berbasis hybrid CNN-LSTM untuk mendeteksi dini gangguan kesehatan janin melalui parameter fisiologis ibu dan janin?
3. Bagaimana tingkat keandalan sistem dalam menghasilkan output yang akurat, informatif, serta terintegrasi dengan aplikasi mobile, dashboard website, dan kecerdasan buatan?

---

## 4. Tujuan Proyek

Tujuan utama proyek FETAL-GUARD:

1. Mengembangkan prototipe sabuk pintar untuk pemantauan detak jantung janin dan indikator kontraksi secara non-invasif.
2. Mengimplementasikan hybrid deep learning berbasis CNN-LSTM untuk mendeteksi pola parameter fisiologis ibu dan janin yang berpotensi abnormal.
3. Mengevaluasi keandalan sistem dalam menghasilkan output yang akurat, informatif, dan terintegrasi dengan aplikasi mobile serta dashboard website.

---

## 5. Manfaat yang Ditargetkan

Manfaat yang ingin dicapai:

1. Membantu ibu hamil memantau kondisi janin dan indikator kontraksi secara mandiri dan berkelanjutan.
2. Mendukung deteksi risiko dini sehingga penanganan oleh tenaga kesehatan dapat dilakukan lebih cepat.
3. Mendorong pengembangan teknologi kesehatan ibu dan anak berbasis wearable, kecerdasan buatan, dan sistem monitoring terintegrasi.

---

## 6. Luaran Proposal

Luaran yang ditargetkan:

1. Laporan kemajuan perancangan FETAL-GUARD.
2. Laporan akhir perancangan FETAL-GUARD.
3. Prototipe FETAL-GUARD yang berfungsi dan siap diuji coba.
4. Akun media sosial Instagram dan TikTok: `@pkmkc.fetalguard`.

---

## 7. Konteks Klinis yang Dipakai dalam Proposal

### 7.1 Fetal Distress

Fetal distress dijelaskan sebagai manifestasi klinis hipoksia akibat gangguan suplai oksigen melalui sirkulasi uteroplasenta selama kehamilan atau persalinan. Indikator yang ditekankan adalah perubahan denyut jantung janin di luar rentang normal, gangguan variabilitas, dan pola deselerasi.

### 7.2 Denyut Jantung Janin / FHR / DJJ

Parameter DJJ mencerminkan kondisi neurologis, otonom, dan kardiovaskular janin. Parameter yang relevan dalam pemantauan FHR antara lain:

- baseline heart rate,
- variabilitas,
- akselerasi,
- deselerasi,
- pola abnormal seperti bradikardia atau takikardia.

Rentang yang digunakan dalam proposal:

| Kategori | Denyut Jantung Ibu | Denyut Jantung Janin | Makna Umum |
|---|---:|---:|---|
| Bradikardia | < 60 bpm | < 110 bpm persisten | Di bawah rentang normal, dapat berkaitan dengan gangguan fisiologis atau patologis. |
| Normal | 60-100 bpm | 110-160 bpm | Kondisi fisiologis relatif stabil. |
| Takikardia | > 100 bpm | > 160 bpm | Peningkatan denyut jantung; bila berlangsung lama dapat menjadi indikasi risiko. |

### 7.3 Kontraksi Rahim

Kontraksi uterus dijelaskan sebagai parameter yang memengaruhi kondisi janin karena frekuensi, durasi, dan kekuatannya dapat memengaruhi aliran darah uteroplasenta. Kontraksi yang berlebihan atau tidak normal dapat menurunkan suplai oksigen dan meningkatkan risiko hipoksia.

### 7.4 Batas Klaim Medis yang Aman

Agar konteks pengembangan tetap aman, FETAL-GUARD sebaiknya diposisikan sebagai:

- alat skrining awal,
- alat pemantauan pendukung,
- alat pencatat sinyal dan pemberi peringatan risiko,
- bukan alat diagnosis definitif,
- bukan pengganti CTG, Doppler, USG, dokter, bidan, atau fasilitas kesehatan.

Output AI sebaiknya menggunakan istilah seperti **risiko rendah**, **perlu pemantauan**, **indikasi anomali**, atau **segera konsultasi tenaga kesehatan**, bukan diagnosis medis final.

---

## 8. Evolusi Teknologi dan Posisi Inovasi

Proposal membandingkan FETAL-GUARD dengan teknologi pemantauan janin yang sudah ada:

1. **Auskultasi manual**: historis, sederhana, bergantung pada operator.
2. **Doppler ultrasound janin**: lebih portabel tetapi tetap bergantung operator dan memberikan data sesaat.
3. **Cardiotocography / CTG**: standar klinis untuk DJJ dan kontraksi, tetapi besar, kurang portabel, dan umumnya digunakan di fasilitas kesehatan.
4. **Wearable belt eksisting**: mulai memungkinkan pemantauan mandiri, tetapi umumnya masih terbatas pada satu parameter seperti DJJ.
5. **FETAL-GUARD**: menggabungkan array sensor pasif, FSR, vital ibu, IoT, mobile app, dashboard nakes, dan AI hybrid CNN-LSTM.

### 8.1 State of the Art Menurut Proposal

| Parameter | CTG/Doppler Konvensional | Wearable Belt Eksisting | FETAL-GUARD |
|---|---|---|---|
| Metode dan keamanan | Ultrasound aktif | Piezo tunggal / EKG | Array 4 piezoelektrik pasif |
| Cakupan pemantauan | DJJ dan kontraksi; vital ibu terpisah | Umumnya hanya DJJ | DJJ, kontraksi, dan vital ibu |
| Reduksi noise dan AI | Filter standar / interpretasi manual | Filter linier / AI konvensional | Hybrid CNN-LSTM + referensi noise / ANC |
| Aksesibilitas IoT | Monitor lokal / cetak grafik | Terbatas aplikasi mobile | Mobile app ibu + dashboard website nakes |

---

## 9. Gambaran Sistem FETAL-GUARD

FETAL-GUARD dirancang sebagai sistem yang terdiri dari lima lapisan besar:

1. **Lapisan wearable/sabuk**  
   Sabuk maternity support belt yang menempatkan sensor pada area anatomi target.

2. **Lapisan akuisisi sinyal**  
   Sensor piezoelektrik, FSR408, MAX30102, dan pada proposal asli juga mikrofon MAX4466 sebagai referensi noise.

3. **Lapisan pemrosesan embedded**  
   ESP32 membaca sensor, melakukan akuisisi data, preprocessing awal, dan mengirim data melalui Wi-Fi/MQTT.

4. **Lapisan cloud/server/AI**  
   Data diproses oleh model hybrid CNN-LSTM untuk estimasi atau klasifikasi risiko.

5. **Lapisan antarmuka pengguna**  
   Aplikasi mobile untuk ibu hamil dan dashboard website untuk tenaga kesehatan.

### 9.1 Alur Kerja Umum

1. Ibu hamil memasang sabuk pada abdomen secara ergonomis.
2. Saat perangkat dinyalakan, sistem melakukan kalibrasi awal untuk meredam noise bawaan dan mencari sensor dengan kualitas sinyal terbaik.
3. ESP32 mengakuisisi data feto-maternal dari sensor.
4. Data dikirim melalui Wi-Fi menggunakan MQTT.
5. Server/cloud menjalankan model AI hybrid CNN-LSTM untuk pemrosesan sinyal dan klasifikasi kondisi.
6. Hasil ditampilkan pada aplikasi mobile ibu dan dashboard website tenaga kesehatan.
7. Jika terdeteksi risiko, sistem menampilkan alert pada aplikasi, dashboard, dan indikator status.

---

## 10. Arsitektur Hardware

### 10.1 Mikrokontroler

- **ESP32 DevKit V1** sebagai unit pemroses utama.
- Peran ESP32:
  - membaca sensor analog melalui ADC,
  - membaca sensor digital MAX30102 melalui I2C,
  - melakukan preprocessing awal,
  - mengirim data melalui Wi-Fi/MQTT,
  - mengontrol indikator LED,
  - berpotensi menggunakan Bluetooth/BLE karena ESP32 mendukung Wi-Fi dan Bluetooth.

### 10.2 Sensor Utama dan Pendukung

| Sensor / Modul | Jumlah pada desain utama | Fungsi |
|---|---:|---|
| Sensor piezoelektrik | 4 | Menangkap vibrasi mekanik katup jantung janin. |
| FSR408 | 1 strip | Mengukur intensitas kontraksi rahim secara mekanik. |
| MAX30102 | 1 | Mengukur denyut jantung ibu / parameter PPG maternal. |
| MAX4466 | 1 | Pada proposal asli digunakan sebagai mikrofon referensi noise untuk ANC. |
| LM324 | 2 IC | Penguat analog / pre-amplifier sinyal piezo. |
| LED merah | 1 | Indikator alarm/peringatan. |
| LED hijau | 1 | Indikator sistem aktif/normal. |

### 10.3 Catatan tentang Mikrofon MAX4466

Proposal asli masih mencantumkan **mikrofon kondenser MAX4466** sebagai referensi noise untuk Active Noise Cancellation. Jika implementasi terbaru tim memutuskan **tidak menggunakan mikrofon**, maka bagian arsitektur AI dan pengurangan noise perlu direvisi. Alternatif tanpa mikrofon:

- menggunakan multi-channel piezo untuk memilih channel dengan SNR terbaik,
- menggunakan adaptive filtering berbasis korelasi antar sensor,
- menggunakan bandpass filtering dan envelope detection,
- menggunakan quality index untuk menolak segmen sinyal buruk,
- menggunakan sensor IMU sebagai referensi artefak gerakan jika tersedia,
- melatih model dengan data noise nyata dari sensor tanpa referensi mikrofon.

### 10.4 Penempatan Sensor pada Sabuk

Desain mekanik sabuk mengikuti maternity support belt yang melingkari abdomen hingga punggung bawah.

Penempatan sensor:

1. **Area fundus uteri / tali penyangga atas**  
   Strip FSR408 untuk mendeteksi tekanan atau perubahan mekanik akibat kontraksi.

2. **Panel tengah abdomen**  
   Array empat piezoelektrik dalam konfigurasi terdistribusi untuk menangkap vibrasi mekanik DJJ.

3. **Dekat panel piezo**  
   Pada proposal asli, mikrofon MAX4466 untuk merekam noise lingkungan/tubuh sebagai referensi ANC.

4. **Sayap pinggang / finger touch pad**  
   MAX30102 untuk membaca denyut jantung ibu agar tidak teredam jaringan lemak perut.

5. **Main Hub Control**  
   Berisi ESP32, baterai, power management, dan rangkaian utama. Ditempatkan agar bobot elektronik tidak menekan rahim secara langsung.

### 10.5 Rangkaian Analog Front-End

Sinyal piezoelektrik sangat lemah sehingga proposal menggunakan LM324 sebagai pre-amplifier. Konsepnya:

- piezo menghasilkan sinyal analog getaran,
- sinyal diperkuat oleh LM324,
- kemungkinan melalui filter analog seperti low-pass atau band-pass,
- sinyal masuk ke ADC ESP32,
- ESP32 mengirim data mentah atau hasil preprocessing ke server.

Untuk pengembangan nyata, bagian ini perlu dirancang sangat hati-hati karena pembacaan sinyal janin melalui sensor pasif rentan noise. Topik penting yang harus dibahas lanjut:

- konfigurasi op-amp untuk piezo,
- impedansi input tinggi,
- proteksi ADC ESP32 agar tidak menerima tegangan negatif atau di atas 3.3 V,
- filter analog,
- bias tengah untuk sinyal AC,
- shielding kabel,
- ground layout,
- sampling rate,
- resolusi ADC,
- validasi SNR.

### 10.6 Sistem Power

Proposal menggunakan:

- baterai Li-Po 3.7 V 2000 mAh,
- modul charger TP4056,
- step-up MT3608 untuk menaikkan tegangan ke 5 V,
- jalur 5 V untuk sensor analog, op-amp, dan VIN ESP32,
- indikator LED.

Catatan teknis untuk pengembangan:

- TP4056 cocok untuk baterai Li-ion/Li-Po 1S, tetapi perlu modul proteksi baterai dan idealnya load sharing/power path management.
- ESP32 cukup boros arus saat Wi-Fi aktif, sehingga estimasi daya harus dihitung sejak awal.
- Penggunaan MT3608 step-up dapat menghasilkan switching noise yang mengganggu sensor analog; perlu filtering, pemisahan jalur analog-digital, dan grounding yang baik.
- Sensor analog dan op-amp perlu suplai stabil dan referensi ground yang bersih.
- Untuk wearable kesehatan, aspek keamanan baterai, isolasi, casing, panas, dan charging wajib diprioritaskan.

---

## 11. Daftar Komponen Utama dari Proposal

Daftar alat dan bahan utama pada proposal:

| No | Komponen | Jumlah desain utama |
|---:|---|---:|
| 1 | ESP32 DevKit V1 | 1 |
| 2 | Sensor piezoelektrik | 4 |
| 3 | MAX30102 | 1 |
| 4 | LM324 | 2 |
| 5 | Baterai LiPo 2000 mAh | 1 |
| 6 | TP4056 | 1 |
| 7 | MT3608 | 1 |
| 8 | Mikrofon kondenser MAX4466 | 1 |
| 9 | Sabuk elastis kehamilan | 1 |
| 10 | FSR408 | 1 |
| 11 | Casing elektronik | 3 |
| 12 | Resistor 220 ohm | 2 |
| 13 | Resistor 10k ohm | 4 |
| 14 | Resistor 100k ohm | 4 |
| 15 | Resistor 1M ohm | 4 |
| 16 | Kapasitor 100 nF | 10 |
| 17 | LED merah | 1 |
| 18 | LED hijau | 1 |
| 19 | Strap penopang | 2 |
| 20 | PCB | 1 |

Lampiran anggaran memperluas jumlah pembelian untuk kebutuhan prototipe dan cadangan, misalnya beberapa unit ESP32, piezo, MAX30102, baterai, FSR, sabuk, casing, PCB, kabel shielded, busa EVA, solder kit, breadboard, heatshrink, dan komponen pendukung.

---

## 12. Spesifikasi Alat Menurut Proposal

| Kategori | Detail |
|---|---|
| Nama alat | FETAL-GUARD |
| Fungsi utama | Pemantauan simultan DJJ, intensitas kontraksi rahim, dan parameter vital ibu secara non-invasif. |
| Sensor utama | Array 4 sensor piezoelektrik untuk vibrasi mekanik DJJ. |
| Sensor pendukung | FSR408, MAX4466, MAX30102. |
| Unit pemroses | ESP32 dual-core dengan Wi-Fi/Bluetooth. |
| Pengkondisi sinyal | LM324 untuk pra-amplifikasi analog. |
| Indikator status | LED status dan output visual pada aplikasi/dashboard. |
| Sumber daya | Li-Po 3.7 V 2000 mAh, TP4056, MT3608 5 V. |
| Dimensi sabuk | 80-117 cm, adjustable, model maternity support belt. |
| Material sabuk | Cotton Lycra, mesh fabric, Velcro high-grade. |
| Housing/casing | PLA 3D printed dan akrilik tipis/PLA fleksibel. |
| Akuisisi data | Fusi sensor terdistribusi, pre-amplification, LPF analog, ADC. |
| Algoritma | Hybrid CNN-LSTM dengan optimasi noise cancellation. |
| Output | Grafik DJJ, kurva tokografi/kontraksi, vital ibu, alert via mobile app dan dashboard web. |
| Kalibrasi | Kalibrasi otomatis dan smart switching sensor piezo dengan SNR terbaik. |
| Fitur tambahan | USB Type-C charging dan finger touch pad eksternal. |

---

## 13. Arsitektur Software dan IoT

### 13.1 Alur Data

Alur data yang dijelaskan dalam proposal:

```text
Sensor pada sabuk
  -> Analog front-end / pembacaan digital
  -> ESP32
  -> Wi-Fi + MQTT
  -> Server/cloud
  -> Model AI hybrid CNN-LSTM
  -> Mobile app ibu hamil
  -> Dashboard website tenaga kesehatan
  -> Alert / notifikasi / rekomendasi tindakan
```

### 13.2 Protokol Komunikasi

Proposal menggunakan Wi-Fi dan MQTT. MQTT cocok untuk IoT karena ringan dan dapat mengirim data secara publish-subscribe.

Topik pengembangan yang perlu dibahas lanjut:

- struktur topic MQTT,
- format payload JSON,
- interval pengiriman data,
- mode data raw vs fitur terkompresi,
- keamanan koneksi,
- autentikasi perangkat,
- enkripsi data,
- pengelolaan banyak perangkat,
- offline buffer jika internet putus,
- sinkronisasi ulang data saat koneksi kembali.

### 13.3 Masalah Koneksi untuk Pengguna Banyak

Proposal menyebut Wi-Fi/MQTT, tetapi belum menjelaskan detail provisioning koneksi jika alat digunakan banyak pengguna. Untuk pengembangan lanjutan, opsi yang perlu dibandingkan:

1. **Wi-Fi provisioning melalui aplikasi mobile**  
   Alat membuat mode Access Point sementara, pengguna mengisi SSID/password melalui aplikasi, lalu ESP32 tersambung ke Wi-Fi rumah/hotspot.

2. **Bluetooth Low Energy sebagai gateway ke smartphone**  
   Alat mengirim data ke HP melalui BLE, lalu HP mengirim ke cloud menggunakan internet HP. Ini mirip konsep smartwatch/smartband dan lebih realistis untuk pengguna umum.

3. **Hotspot HP**  
   Sederhana untuk prototipe: pengguna menyalakan hotspot, ESP32 tersambung ke SSID yang sudah disimpan.

4. **Modul GSM/4G**  
   Lebih mandiri tanpa HP, tetapi biaya, daya, SIM card, sinyal, dan integrasi lebih kompleks.

5. **Mode offline-sync**  
   Data disimpan lokal pada perangkat/HP, lalu diunggah saat internet tersedia.

Rekomendasi pengembangan bertahap:

- MVP mahasiswa: Wi-Fi + MQTT menggunakan hotspot HP/lab.
- Versi prototipe lanjut: Wi-Fi provisioning via aplikasi.
- Versi produk portable: BLE ke smartphone sebagai gateway, atau 4G untuk versi klinis tertentu.

---

## 14. Mobile App untuk Ibu Hamil

Aplikasi mobile dirancang sebagai antarmuka utama bagi ibu hamil. Tujuan desainnya adalah memberi informasi yang mudah dipahami, mengurangi kecemasan, dan menyediakan akses darurat.

### 14.1 Home / Beranda

Fitur yang ditampilkan:

- usia gestasi,
- pembacaan DJJ terakhir,
- status kesejahteraan janin seperti Normal Status,
- tombol Mulai Pemantauan,
- status koneksi perangkat,
- sisa baterai,
- kualitas sinyal,
- rekomendasi durasi pemantauan,
- riwayat pemeriksaan terakhir,
- tombol DARURAT.

### 14.2 History / Riwayat

Fungsi halaman riwayat:

- menjadi rekam medis digital mandiri,
- menampilkan total sesi pemantauan,
- akumulasi waktu penggunaan,
- rata-rata DJJ,
- daftar sesi secara kronologis,
- durasi sesi,
- status kondisi janin,
- ekspor PDF untuk konsultasi dokter,
- filter status.

Kategori visual sesi:

- Normal / hijau,
- Watch atau Waspada / kuning,
- Alarm atau Bahaya / merah.

### 14.3 Monitoring Aktif

Fitur halaman monitoring:

- kualitas sinyal,
- status posisi tubuh,
- timer durasi pemantauan,
- DJJ real-time dalam bpm,
- cuplikan gelombang sinyal,
- rata-rata DJJ,
- vital ibu,
- grafik sinyal live menyerupai CTG.

### 14.4 Notifikasi / Alerts

Fitur halaman notifikasi:

- alert merah untuk kondisi kritis seperti deselerasi lambat,
- alert kuning untuk waspada seperti variabilitas menurun atau baterai rendah,
- alert biru untuk informasi sistem seperti sesi selesai atau sinkronisasi data,
- rekomendasi tindakan otomatis,
- status apakah notifikasi sudah ditangani,
- tombol darurat.

Contoh rekomendasi tindakan yang disebutkan:

- mengubah posisi tidur miring ke kiri selama 10 menit,
- segera menghubungi dokter jika kondisi berlanjut.

### 14.5 Settings / Pengaturan Mobile

Fitur pengaturan:

- profil pengguna,
- koneksi ke klinik/dokter penanggung jawab,
- status perangkat,
- baterai,
- versi firmware,
- sinkronisasi MQTT,
- preferensi notifikasi,
- haptic feedback,
- batas baterai rendah,
- izin berbagi lokasi darurat,
- eskalasi otomatis ke klinik,
- hapus data mandiri,
- dark mode,
- opsi pemrosesan AI lokal / on-device inference.

---

## 15. Dashboard Website untuk Tenaga Kesehatan

Dashboard website ditujukan sebagai portal klinis bagi tenaga kesehatan, klinik, atau rumah sakit. Perannya bukan sekadar menampilkan data satu pasien, tetapi juga pemantauan banyak pasien dan alur tanggap darurat.

### 15.1 Dashboard Overview

Fitur utama:

- system overview,
- total pasien aktif,
- jumlah pasien normal,
- warning,
- urgent,
- recent alerts,
- grafik distribusi mingguan,
- akses cepat ke emergency protocol.

Sistem AI melakukan triase otomatis terhadap pasien berdasarkan status risiko.

### 15.2 Active Patient Monitoring

Fitur utama:

- daftar pasien aktif,
- filter berdasarkan tingkat risiko,
- filter departemen rawat,
- filter usia gestasi,
- tabel metrik real-time,
- label risk level,
- last sync,
- action untuk melihat detail pasien dan grafik sinyal.

Contoh skenario: jika DJJ terdeteksi 168 bpm, sistem dapat memberi label High Risk berwarna merah.

### 15.3 Clinical Alerts

Fungsi:

- pusat komando tanggap darurat,
- menampilkan critical condition saat terdeteksi anomali,
- menampilkan lokasi pasien berbasis geolokasi/GPS,
- menampilkan tren DJJ 5 menit terakhir,
- menampilkan parameter vital maternal seperti saturasi oksigen dan suhu tubuh,
- tombol Call Patient,
- tombol Call Ambulance.

### 15.4 Staff Schedules

Fitur:

- pemetaan jadwal shift dokter dan perawat,
- daftar personel yang sedang bertugas,
- on-call backup,
- estimasi waktu kedatangan / ETA,
- tombol pager darurat,
- indikator coverage strength.

Tujuannya agar saat AI memicu alarm, rumah sakit tahu siapa yang harus merespons.

### 15.5 System Analytics

Fungsi:

- pusat data intelligence untuk manajemen rumah sakit atau kepala departemen,
- KPI operasional,
- total jam pemantauan,
- rata-rata waktu respons terhadap alarm,
- tren peringatan risiko tinggi,
- distribusi risiko pasien,
- export report,
- dukungan audit medis dan evaluasi efisiensi layanan.

### 15.6 Settings Dashboard

Fitur:

- FHR threshold configuration,
- pengaturan batas bradikardia dan takikardia,
- safe zone 110-160 bpm,
- escalation protocols bertingkat,
- Tier 1 perawat,
- Tier 2 dokter jaga,
- Tier 3 tim respons cepat,
- system health,
- latensi sensor,
- uptime server,
- staff access settings berbasis peran.

---

## 16. Sistem AI Hybrid Deep Learning

### 16.1 Konsep AI dalam Proposal

Proposal menggunakan model hybrid deep learning **CNN-LSTM** untuk analisis sinyal biologis janin yang non-stasioner dan rentan noise.

Peran CNN:

- ekstraksi fitur lokal,
- membaca morfologi sinyal,
- membantu pemisahan sinyal dari noise,
- dapat digunakan pada sinyal 1D atau representasi citra/grafik.

Peran LSTM:

- mempelajari pola temporal,
- melihat perubahan DJJ dari waktu ke waktu,
- menangkap dependensi jangka panjang,
- membantu klasifikasi kondisi normal/abnormal.

### 16.2 Preprocessing Data

Proposal menyebut preprocessing berupa:

- filtrasi noise,
- normalisasi,
- representasi data ke bentuk citra/grafik,
- validasi model dengan K-fold cross-validation.

Untuk pengembangan praktis, preprocessing dapat diperjelas menjadi:

1. sinkronisasi multi-channel sensor,
2. filter analog dan digital,
3. segmentasi sinyal per window,
4. perhitungan SNR atau signal quality index,
5. normalisasi amplitudo,
6. ekstraksi fitur time-domain dan frequency-domain,
7. pelabelan window data,
8. augmentasi noise jika data terbatas,
9. pemisahan train/validation/test berbasis subjek, bukan hanya berbasis window.

### 16.3 Output AI yang Aman

Output AI sebaiknya tidak langsung berupa diagnosis. Output yang lebih aman:

- estimasi DJJ,
- estimasi kualitas sinyal,
- deteksi sinyal valid/tidak valid,
- status risiko rendah/sedang/tinggi,
- rekomendasi ulang pemasangan sensor,
- rekomendasi konsultasi tenaga kesehatan,
- alert bila nilai melewati ambang aman.

### 16.4 Catatan Kritis AI

Agar model AI valid, perlu ground truth yang jelas. Proposal menyebut dataset publik seperti PhysioNet dan data primer, tetapi perlu diperinci:

- data sensor FETAL-GUARD sendiri,
- data referensi dari CTG/toco/Doppler/alat medis,
- label dari tenaga kesehatan,
- metadata usia kehamilan,
- posisi sensor,
- aktivitas ibu,
- noise lingkungan,
- kualitas pemasangan sabuk,
- kondisi gerakan,
- durasi perekaman.

---

## 17. Dataset dan Ground Truth yang Perlu Dibahas Lanjut

Proposal menyebut penggunaan dataset publik dan data primer, tetapi belum sepenuhnya menjelaskan strategi ground truth. Untuk konteks pengembangan AI, bagian ini penting.

### 17.1 Data yang Dibutuhkan

Jenis data yang ideal:

1. **Data raw dari sensor piezoelektrik**  
   Empat channel sinyal getaran dari abdomen.

2. **Data FSR408**  
   Sinyal tekanan/kontraksi sebagai indikator mekanik aktivitas rahim.

3. **Data MAX30102**  
   Denyut jantung ibu dan kemungkinan SpO2 jika digunakan.

4. **Data referensi klinis**  
   CTG/toco/Doppler/rekam medis atau interpretasi tenaga kesehatan.

5. **Data subjektif dan observasi**  
   Posisi ibu, aktivitas, keluhan, gerakan janin, usia kehamilan, posisi sensor, dan kualitas pemasangan.

6. **Data kualitas sinyal**  
   SNR, noise, artefak gerakan, sensor lepas, kabel terganggu.

### 17.2 Ground Truth yang Ideal

Ground truth terbaik untuk validasi:

- FHR/DJJ referensi dari CTG atau Doppler klinis,
- kontraksi referensi dari tocotransducer/toco CTG,
- interpretasi tenaga kesehatan terhadap pola FHR,
- label waktu kejadian: normal, waspada, abnormal, sinyal tidak valid.

### 17.3 Jika Belum Ada Akses Rumah Sakit

Tahapan yang realistis:

1. uji elektronik sensor dengan sinyal buatan,
2. uji getaran menggunakan sumber mekanik terkontrol,
3. uji FSR dengan tekanan terukur,
4. uji MAX30102 pada relawan sehat untuk denyut ibu,
5. uji sabuk pada phantom/manekin atau simulasi mekanik,
6. gunakan dataset publik untuk latihan pipeline AI,
7. validasi terbatas dengan pendampingan tenaga kesehatan,
8. baru masuk ke validasi pembanding CTG/toco.

---

## 18. Pengujian dan Validasi Sistem

Proposal menyebut pengujian:

- SNR fusi sensor,
- akurasi estimasi DJJ,
- latensi transmisi data MQTT,
- efisiensi daya baterai,
- classification error pada model AI,
- usability test ergonomis,
- penyesuaian dengan ISO 13485, ISO 14971, IEC 62304.

### 18.1 Metrik Pengujian yang Disarankan

Metrik teknis:

- SNR sinyal piezo,
- sampling stability,
- packet loss MQTT,
- latency end-to-end,
- battery life,
- suhu casing/baterai,
- kestabilan pembacaan ADC,
- noise power supply,
- koneksi Wi-Fi/BLE.

Metrik estimasi DJJ:

- MAE bpm terhadap alat referensi,
- RMSE bpm,
- korelasi dengan CTG/Doppler,
- persentase window valid,
- error saat ibu bergerak vs diam.

Metrik kontraksi:

- korelasi sinyal FSR terhadap toco,
- deteksi onset kontraksi,
- durasi kontraksi,
- jumlah kontraksi per periode,
- false alarm kontraksi akibat gerakan.

Metrik klasifikasi risiko:

- accuracy,
- sensitivity/recall,
- specificity,
- precision,
- F1-score,
- confusion matrix,
- false alarm rate,
- missed alarm rate.

Metrik usability:

- kenyamanan sabuk,
- kemudahan pemasangan,
- stabilitas posisi sensor,
- waktu pemasangan,
- tekanan pada abdomen,
- kemudahan membaca aplikasi.

---

## 19. Desain Sabuk dan Implementasi Wearable

Konsep sabuk:

- model maternity support belt,
- melingkari abdomen dan punggung bawah,
- panjang adjustable 80-117 cm,
- material Cotton Lycra, mesh fabric, dan Velcro,
- casing PLA 3D printed,
- bobot elektronik didistribusikan agar tidak menekan rahim,
- kabel sensor dijahit atau disembunyikan di lapisan kain,
- sensor ditempatkan berdasarkan target anatomi.

Hal yang perlu diperhatikan saat implementasi:

1. sensor tidak boleh memberi tekanan berlebih,
2. posisi sensor harus konsisten,
3. sabuk harus nyaman untuk pemakaian beberapa menit hingga puluhan menit,
4. casing tidak boleh tajam atau panas,
5. kabel harus aman dan tidak mudah tertarik,
6. perangkat harus mudah dibersihkan,
7. desain harus memungkinkan kalibrasi dan perbaikan sensor.

---

## 20. Keunggulan Dibanding Alat Konvensional

| Aspek | FETAL-GUARD | Alat konvensional |
|---|---|---|
| Mobilitas | Wearable, portabel, bisa dipakai di rumah | Besar/stasioner, umumnya di fasilitas kesehatan |
| Parameter | DJJ, kontraksi, vital ibu | CTG: DJJ dan kontraksi; Doppler: umumnya DJJ saja |
| Kenyamanan | Distributed design, sabuk elastis | Probe/transduser diikat dan memakai gel |
| Sensor | Fusi multisensor pasif | Umumnya satu jenis sensor |
| Analisis | Pre-amplification, noise cancellation, CNN-LSTM | Filter standar dan interpretasi manual |
| Peringatan dini | Alert otomatis ke aplikasi dan dashboard | Alarm lokal saat pemeriksaan berlangsung |

---

## 21. Tahapan Pelaksanaan Proposal

Tahapan yang tertulis dalam proposal:

1. Studi literatur dan survei kebutuhan pengguna.
2. Perancangan metode dan arsitektur sistem.
3. Perancangan dan pembuatan perangkat keras.
4. Pengembangan perangkat lunak dan model hybrid deep learning.
5. Integrasi sistem, pengujian, dan validasi.
6. Evaluasi dan penyempurnaan sistem.

---

## 22. Jadwal Kegiatan 4 Bulan

Rencana aktivitas dalam proposal:

| Kegiatan | Penanggung jawab utama |
|---|---|
| Studi literatur | Mailani Anatasya |
| Pengembangan ide dan proposal | Tasya Adinda Putri |
| Penentuan metode, dataset, dan persiapan komponen | Fitriah Ramadhani Aulia Rasyidin |
| Perancangan hardware | Arris Ahmad Fadillah |
| Perancangan software, integrasi, dan pengujian | Aditya Kristian Novalino |
| Penulisan laporan akhir | Mailani Anatasya |

Catatan: proposal menempatkan seluruh program dalam durasi sekitar 4 bulan.

---

## 23. Pembagian Tugas Tim

Ringkasan pembagian tugas:

### 23.1 Mailani Anatasya

- Koordinator tim dan penanggung jawab utama.
- Konsultasi dengan dosen pembimbing.
- Koordinasi integrasi hardware, software, aplikasi mobile, dan dashboard.
- Mengawasi penelitian dan pengembangan alat.
- Bertanggung jawab atas laporan kemajuan dan laporan akhir.

### 23.2 Fitriah Ramadhani Aulia Rasyidin

- Mengumpulkan referensi terkait deteksi gawat janin.
- Terlibat dalam pengujian fungsional alat.
- Evaluasi kinerja sistem.
- Membantu perancangan sistem dan desain wearable.

### 23.3 Tasya Adinda Putri

- Studi literatur dan penguatan konsep klinis-teknis.
- Analisis hasil pengujian.
- Penyempurnaan alat berdasarkan evaluasi.
- Penyusunan proposal dan dokumentasi pendukung.

### 23.4 Arris Ahmad Fadillah

- Pengadaan komponen elektronik.
- Perancangan sistem dan desain perangkat wearable.
- Perakitan rangkaian hardware sesuai skematik.
- Pengujian awal fungsi rangkaian elektronik.
- Membantu pengembangan pemrosesan sinyal dan AI.

### 23.5 Aditya Kristian Novalino

- Pengembangan pemrosesan sinyal dan kecerdasan buatan.
- Implementasi algoritma analisis data.
- Integrasi hardware dan software.
- Pengujian integrasi perangkat keras dan lunak.

---

## 24. Anggaran Proposal

Total anggaran proposal: **Rp8.745.000**

Rekap sumber dana:

| Sumber | Jumlah |
|---|---:|
| Belmawa | Rp6.745.000 |
| Perguruan Tinggi | Rp2.000.000 |
| Instansi lain | Rp0 |
| Total | Rp8.745.000 |

Kategori pengeluaran:

| Kategori | Total |
|---|---:|
| Belanja bahan | Rp5.195.000 |
| Belanja sewa/jasa | Rp1.250.000 |
| Perjalanan | Rp1.000.000 |
| Lain-lain | Rp1.300.000 |
| Total | Rp8.745.000 |

Contoh komponen biaya:

- ESP32 DevKit V1,
- piezoelektrik,
- MAX30102,
- LM324,
- Li-Po 2000 mAh,
- TP4056,
- MT3608,
- MAX4466,
- FSR408,
- sabuk elastis,
- casing,
- PCB,
- kabel shielded,
- busa EVA,
- solder kit,
- breadboard,
- heatshrink,
- transportasi pembelian komponen,
- kunjungan klinik,
- pengujian/kalibrasi,
- iklan media sosial,
- internet.

---

## 25. Referensi yang Digunakan dalam Proposal

Referensi yang disebutkan dalam daftar pustaka proposal:

1. Azwari dan Turabieh (2021) - Deep Learning LSTM.
2. Hug dkk. (2021) - estimasi global/regional/nasional stillbirth.
3. Ismail dkk. (2025) - hubungan preeklamsia dengan IUFD.
4. Kauffmann dan Silberman (2026) - fetal monitoring.
5. Kling, Rehnström, dan Herbst (2024) - performa klasifikasi CTG.
6. Liu dkk. (2024) - wearable sensors, data processing, dan AI dalam monitoring kehamilan.
7. Motie-Shirazi dkk. (2024) - kualitas sinyal fetal Doppler real-time dengan deep learning.
8. Sahid dkk. (2023) - faktor risiko kematian janin dalam rahim.
9. Singh dkk. (2022) - CTG intrapartum dan korelasi dengan outcome neonatal.
10. Spairani dkk. (2022) - deep learning mixed-data untuk klasifikasi FHR.
11. Varthaliti dkk. (2024) - safety obstetric ultrasound.
12. Wang dkk. (2021) - wearable / referensi yang dicantumkan dalam proposal.

Catatan: beberapa referensi perlu dicek ulang kesesuaian topik dan validitas bibliografinya, terutama referensi yang tampak tidak langsung terkait FETAL-GUARD.

---

## 26. Titik Kuat Proposal

1. Mengangkat masalah kesehatan ibu dan janin yang relevan.
2. Menggabungkan wearable, sensor, IoT, dashboard, dan AI dalam satu ekosistem.
3. Menyasar pemantauan non-invasif dan portabel.
4. Membagi sistem ke aplikasi ibu dan dashboard tenaga kesehatan.
5. Memiliki konsep fusi sensor, bukan hanya satu sensor.
6. Memperhatikan ergonomi sabuk dan kenyamanan ibu hamil.
7. Menyebut validasi SNR, akurasi DJJ, latensi MQTT, baterai, dan usability.
8. Memuat rencana visual antarmuka aplikasi dan dashboard yang cukup lengkap.

---

## 27. Titik yang Perlu Diperjelas untuk Diskusi AI Selanjutnya

Bagian ini penting agar AI yang membaca dokumen ini bisa langsung membantu pengembangan berikutnya.

### 27.1 Validasi Klinis

Perlu dijelaskan:

- apakah alat akan dibandingkan dengan CTG, Doppler, atau toco,
- siapa yang memberi label ground truth,
- bagaimana prosedur pengambilan data pada ibu hamil,
- izin etik dan keselamatan subjek,
- metrik evaluasi yang digunakan,
- batas klaim alat sebagai skrining, bukan diagnosis.

### 27.2 Rangkaian Sensor Piezo

Perlu dibuat detail:

- konfigurasi penguat LM324,
- nilai resistor/kapasitor,
- bias ADC,
- rentang frekuensi target,
- proteksi input ESP32,
- metode filtering,
- metode pembacaan 4 channel,
- cara memilih channel terbaik.

### 27.3 FSR untuk Kontraksi

Perlu dibuktikan apakah FSR408 bisa menjadi proksi kontraksi rahim yang cukup bermakna. FSR membaca tekanan lokal pada sabuk, sehingga sinyalnya dapat dipengaruhi oleh:

- kencang/longgarnya sabuk,
- posisi tubuh,
- gerakan ibu,
- tekanan tangan,
- perubahan postur,
- posisi sensor relatif terhadap fundus.

Validasi terhadap toco klinis penting jika ingin mengklaim deteksi kontraksi.

### 27.4 AI Hybrid CNN-LSTM

Perlu diperjelas:

- input model berupa raw signal 1D atau spectrogram/citra,
- panjang window,
- sampling rate,
- jumlah channel,
- label target,
- dataset publik yang digunakan,
- data primer yang dikumpulkan,
- strategi menghindari data leakage,
- apakah inference di cloud, aplikasi, atau perangkat.

### 27.5 Koneksi IoT

Proposal menyebut Wi-Fi/MQTT tetapi belum membahas detail provisioning. Untuk alat portabel, masalah utama adalah bagaimana perangkat terhubung ke internet saat berpindah pengguna. Opsi yang perlu dipilih:

- Wi-Fi provisioning,
- BLE ke smartphone,
- hotspot HP,
- 4G module,
- offline-sync.

### 27.6 Keamanan Data

Data kehamilan dan kesehatan bersifat sensitif. Perlu dirancang:

- autentikasi user,
- enkripsi data,
- izin berbagi data dengan nakes,
- manajemen akses berbasis peran,
- kebijakan penyimpanan data,
- penghapusan data,
- audit log,
- keamanan MQTT/API.

### 27.7 Keselamatan Wearable

Perlu diperhatikan:

- keamanan baterai,
- isolasi listrik,
- pemanasan casing,
- tekanan sabuk pada abdomen,
- material kontak kulit,
- kemudahan disinfeksi,
- waterproof/sweat resistance,
- keamanan kabel.

---

## 28. Roadmap Pengembangan yang Sesuai Isi Proposal

### Tahap 1 - Proof of Concept Sensor dan Power

Target:

- ESP32 membaca piezo, FSR, dan MAX30102.
- Serial monitor menampilkan data raw.
- Power dari baterai dan regulator stabil.
- Data bisa dikirim MQTT sederhana.

Output:

- rangkaian breadboard,
- data raw CSV,
- grafik sensor sederhana,
- uji baterai dasar,
- uji noise dasar.

### Tahap 2 - Akuisisi Data dan Dashboard Dasar

Target:

- data sensor masuk server/cloud,
- dashboard real-time menampilkan grafik,
- mobile app atau web app sederhana untuk pengguna,
- penyimpanan riwayat sesi.

Output:

- struktur database,
- API/MQTT broker,
- halaman monitoring,
- ekspor data CSV/PDF.

### Tahap 3 - Preprocessing dan Deteksi Sinyal

Target:

- filtering sinyal piezo,
- deteksi puncak atau estimasi denyut,
- signal quality index,
- deteksi data tidak valid,
- estimasi FHR awal.

Output:

- pipeline Python/MATLAB,
- analisis SNR,
- grafik sebelum/sesudah filter,
- perbandingan dengan sinyal referensi sederhana.

### Tahap 4 - Model AI Awal

Target:

- model baseline rule-based,
- model CNN/LSTM sederhana,
- training dengan dataset publik atau data simulasi,
- klasifikasi normal/warning berdasarkan window.

Output:

- notebook training,
- metrik awal,
- confusion matrix,
- dokumentasi dataset.

### Tahap 5 - Validasi dengan Referensi Klinis

Target:

- pengambilan data terbatas dengan pendampingan nakes,
- perbandingan dengan Doppler/CTG/toco bila tersedia,
- perbaikan label dan metrik.

Output:

- protokol pengujian,
- dataset primer terstruktur,
- hasil MAE DJJ,
- hasil korelasi kontraksi,
- laporan keterbatasan.

### Tahap 6 - Integrasi Wearable Final

Target:

- PCB lebih rapi,
- casing 3D printed,
- sabuk ergonomis,
- kabel aman,
- app/dashboard versi demo,
- demo end-to-end.

Output:

- prototipe siap presentasi,
- video demo,
- dokumentasi arsitektur,
- laporan akhir.

---

## 29. Prompt Siap Pakai untuk AI Berdasarkan Proposal

Gunakan prompt berikut bila ingin meminta AI membantu roadmap lanjutan:

```text
Kami sedang mengembangkan FETAL-GUARD, yaitu wearable maternity belt untuk skrining risiko dini kondisi janin. Alat ini memantau denyut jantung janin (DJJ/FHR), indikator kontraksi rahim, dan parameter vital ibu secara non-invasif. Sistem menggunakan ESP32, array 4 sensor piezoelektrik untuk vibrasi DJJ, FSR408 untuk kontraksi, MAX30102 untuk denyut jantung ibu, analog front-end LM324, baterai Li-Po 3.7 V 2000 mAh, TP4056, MT3608, serta komunikasi Wi-Fi/MQTT ke aplikasi mobile ibu dan dashboard website tenaga kesehatan. Proposal asli juga mencantumkan mikrofon MAX4466 sebagai referensi noise untuk ANC, tetapi bagian ini bisa direvisi jika implementasi terbaru tidak menggunakan mikrofon.

Konsep AI yang diusulkan adalah hybrid CNN-LSTM untuk preprocessing, ekstraksi fitur, analisis temporal, dan klasifikasi risiko awal. Output alat tidak boleh dianggap diagnosis medis, melainkan status skrining risiko seperti normal, waspada, atau perlu konsultasi tenaga kesehatan. Dashboard nakes memiliki fitur monitoring pasien aktif, clinical alerts, GPS lokasi pasien, call patient/ambulance, staff schedule, system analytics, dan settings threshold FHR.

Tolong bantu susun roadmap teknis lengkap dari sisi hardware, power management, sensor, akuisisi data, filtering, dataset, ground truth, AI, IoT/cloud, mobile app, dashboard nakes, desain sabuk, validasi terhadap CTG/toco/Doppler, keamanan data, dan tahapan MVP sampai prototipe siap diuji. Berikan prioritas pengerjaan, risiko terbesar, solusi realistis untuk tim mahasiswa, serta batasan klaim agar tidak menggantikan alat medis klinis.
```

---

## 30. Prompt Khusus untuk Bahas Dataset dan Ground Truth

```text
Kami ingin melatih AI untuk FETAL-GUARD, wearable maternity belt untuk skrining risiko dini kondisi janin. Sensor yang digunakan adalah 4 piezoelektrik untuk menangkap vibrasi DJJ, FSR408 untuk indikator kontraksi, MAX30102 untuk denyut jantung ibu, dan ESP32 sebagai akuisisi data. Data dikirim ke cloud/dashboard. Model awal yang direncanakan adalah hybrid CNN-LSTM.

Tolong jelaskan secara teknis data apa saja yang harus kami kumpulkan, bagaimana format datasetnya, bagaimana menentukan ground truth menggunakan CTG/Doppler/toco atau observasi tenaga kesehatan, apa yang bisa dilakukan jika belum memiliki akses rumah sakit, bagaimana membedakan label diagnosis klinis vs label risiko skrining, serta bagaimana strategi validasi yang realistis untuk tim mahasiswa.
```

---

## 31. Prompt Khusus untuk Bahas Hardware dan Power

```text
Kami sedang membuat FETAL-GUARD, sabuk pintar berbasis ESP32 untuk membaca 4 piezoelektrik, FSR408, dan MAX30102. Proposal menggunakan baterai Li-Po 3.7 V 2000 mAh, TP4056, MT3608 5 V, LM324 untuk penguatan sinyal piezo, dan komunikasi Wi-Fi/MQTT. Tolong bantu desain arsitektur hardware yang aman dan realistis: blok diagram power, proteksi baterai, charger, regulator, pembagian rail 3.3 V/5 V, analog front-end piezo, filter, proteksi ADC ESP32, layout ground, shielding kabel, estimasi konsumsi daya, serta urutan pengujian dari breadboard hingga PCB.
```

---

## 32. Prompt Khusus untuk Bahas IoT dan Koneksi Portable

```text
FETAL-GUARD adalah wearable portabel untuk ibu hamil yang harus mengirim data sensor ke cloud agar AI dan dashboard bisa berjalan. Proposal awal memakai Wi-Fi/MQTT dari ESP32. Masalahnya, jika alat dipakai banyak pengguna, SSID dan password Wi-Fi akan berubah-ubah. Tolong bandingkan opsi Wi-Fi provisioning, hotspot HP, Bluetooth Low Energy ke smartphone sebagai gateway, modul 4G, dan offline-sync. Rekomendasikan arsitektur koneksi paling realistis untuk prototipe mahasiswa dan versi produk.
```

---

## 33. Ringkasan Super Singkat untuk Ditempel ke Chat AI

FETAL-GUARD adalah proposal PKM-KC untuk membuat sabuk pintar ibu hamil berbasis wearable multisensor, IoT, dan hybrid deep learning. Sistem memantau DJJ/FHR, indikator kontraksi rahim, dan vital ibu secara non-invasif. Hardware utama: ESP32 DevKit V1, 4 piezoelektrik untuk vibrasi jantung janin, FSR408 untuk kontraksi, MAX30102 untuk denyut ibu, LM324 sebagai analog pre-amplifier, Li-Po 3.7 V 2000 mAh, TP4056, MT3608, dan dashboard berbasis Wi-Fi/MQTT. Proposal asli juga mencantumkan MAX4466 untuk referensi noise/ANC. Software mencakup mobile app untuk ibu, dashboard website untuk tenaga kesehatan, dan AI CNN-LSTM untuk preprocessing/analisis temporal/klasifikasi risiko. Output harus diposisikan sebagai skrining risiko dini, bukan diagnosis medis. Validasi perlu membandingkan estimasi DJJ dan kontraksi terhadap alat medis referensi seperti CTG/Doppler/toco serta label tenaga kesehatan. Tantangan utama: noise sinyal piezo, ground truth, koneksi portabel, keamanan data kesehatan, power management, kenyamanan sabuk, dan batas klaim medis.

---

## 34. Catatan Akhir

Dokumen ini cocok digunakan sebagai konteks awal AI untuk:

- menyusun roadmap proyek,
- mengembangkan skematik hardware,
- membuat rencana dataset,
- menyusun pipeline AI,
- membuat arsitektur IoT,
- menulis ulang proposal,
- membuat laporan kemajuan,
- menyiapkan presentasi,
- menyusun validasi alat.

Hal yang paling perlu diperkuat sebelum implementasi nyata adalah strategi validasi klinis, ground truth, desain analog front-end, keamanan baterai, koneksi portable, dan pembatasan klaim medis agar alat tetap berada pada ranah skrining risiko awal.
