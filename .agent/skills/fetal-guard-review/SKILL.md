---
name: fetal-guard-review
description: Use this after implementing a Fetal Guard task to review code, docs, medical-claim safety, build status, and next steps.
---

# Fetal Guard Review Skill

Review perubahan sebelum dianggap selesai dan siap commit.

## Review Checklist

### Fungsional
- [ ] Apakah perubahan sesuai issue/PRD?
- [ ] Apakah build/lint berhasil tanpa error?
- [ ] Apakah hanya file di dalam scope issue yang diubah?

### Medical Safety
- [ ] Apakah klaim medis tetap konservatif ("skrining awal", bukan "diagnosis")?
- [ ] Apakah threshold klinis (FHR 110-160 bpm) tidak berubah tanpa approval?
- [ ] Apakah output AI menggunakan istilah aman (normal/waspada/konsultasi)?
- [ ] Apakah tidak ada teks di UI yang menyiratkan penggantian alat medis?

### Hardware/Safety
- [ ] Apakah pin mapping ESP32 konsisten dengan skematik?
- [ ] Apakah proteksi ADC (maks 3.3V) masih terjaga?
- [ ] Apakah konsumsi daya tidak bertambah signifikan?
- [ ] Apakah tidak ada risiko keselamatan baru (baterai, panas, tekanan)?

### Connectivity
- [ ] Apakah BLE UUID / MQTT topic konsisten dengan definisi yang ada?
- [ ] Apakah format payload JSON tidak berubah tanpa update di semua subscriber?
- [ ] Apakah offline fallback masih berjalan?

### Security
- [ ] Apakah tidak ada secret/API key/token/password yang ter-expose?
- [ ] Apakah tidak ada data sensitif pasien yang di-hardcode?

### Documentation
- [ ] Apakah dokumentasi perlu diupdate (PRD, CONTEXT.md, README)?
- [ ] Apakah ada asumsi baru yang perlu dicatat?
- [ ] Apakah ada keputusan arsitektur yang perlu ADR?

## Output Format

````md
## Ringkasan Perubahan
- [Deskripsi teknis: apa yang berubah dan dampaknya pada alur data]

## Issue yang Dikerjakan
- [Path ke file issue di `docs/issues/`]

## File yang Diubah
| File | Perubahan |
|---|---|
| `path/to/file` | [Ringkasan singkat] |

## Hasil Build/Test
- [Output `npm run build` / `pio run` / `npm run lint`]
- [Status pengujian data sensor dummy / validasi hardware]

## Medical Claim Check
- [Apakah ada teks baru di UI/output yang menyentuh kesehatan? Jika ya, apakah sudah menggunakan frasa aman?]

## Risiko
- [Apakah implementasi berpotensi membuat bottleneck memori ESP32?]
- [Apakah ada kata/teks medis di UI yang berpotensi melanggar guardrail?]
- [Apakah ada risiko keselamatan (baterai, panas, tekanan sensor)?]

## Dokumentasi yang Perlu Diupdate
- [ ] `docs/ai/CONTEXT.md` — jika arsitektur berubah
- [ ] `docs/prd/` — jika requirement berubah
- [ ] `FETALGUARD_Technical_Roadmap.md` — jika tahap berubah
- [ ] `README.md` — jika setup berubah

## ADR yang Perlu Dibuat
- [Jika ada keputusan arsitektur baru, buat ADR di `docs/adr/`]
- [Jika tidak ada, tulis "Tidak ada"]

## Status
DONE / NEEDS_REVISION / BLOCKED

## Next Steps
- [Issue berikutnya yang direkomendasikan]
- [Jika DONE: rekomendasikan commit dan update CONTEXT.md jika arsitektur berubah]
````
