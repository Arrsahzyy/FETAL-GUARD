---
name: fetal-guard-issue-slicer
description: Use this to split a Fetal Guard PRD, roadmap, or implementation plan into small local issues in docs/issues.
---

# Fetal Guard Issue Slicer

Pecah PRD atau rencana implementasi menjadi issue kecil yang actionable.

## Rules

- Setiap issue harus kecil dan bisa dikerjakan dalam satu sesi (1-3 jam).
- Setiap issue harus punya acceptance criteria yang bisa diverifikasi.
- Setiap issue harus punya cara verifikasi (build, test, atau observasi).
- Jangan membuat task terlalu umum seperti "improve system" atau "fix bugs".
- Jangan implementasi dulu — hanya pecah menjadi daftar issue.
- Simpan issue di `docs/issues/`.
- Nama file: `docs/issues/NNNN-judul-singkat.md` (contoh: `0001-baca-piezo-serial.md`).

## Label System

Gunakan label berikut di judul issue untuk identifikasi cepat:

| Label | Subsystem |
|---|---|
| `[HW]` | Hardware/embedded (ESP32, sensor, rangkaian) |
| `[AFE]` | Analog front-end (LM324, filter, ADC) |
| `[PWR]` | Power management (baterai, charger, regulator) |
| `[BLE]` | Bluetooth Low Energy |
| `[IoT]` | WiFi/MQTT/cloud connectivity |
| `[API]` | Backend/API/database |
| `[UI]` | Frontend/dashboard/mobile app |
| `[AI]` | AI/ML pipeline |
| `[DOC]` | Documentation/proposal |
| `[TEST]` | Validation/testing |
| `[BELT]` | Wearable/belt/casing design |

## Priority — Berdasarkan Roadmap

Issue harus diurutkan berdasarkan tahap roadmap:

1. **Tahap 1** (PoC Sensor & Power) → dikerjakan duluan
2. **Tahap 2** (Akuisisi & Dashboard Dasar)
3. **Tahap 3** (Preprocessing & Deteksi)
4. **Tahap 4** (Model AI Awal)
5. **Tahap 5** (Validasi Klinis)
6. **Tahap 6** (Integrasi Final)

## Output Format

````md
# Issue: [LABEL] <Judul Singkat>

## Roadmap Stage
- Tahap [1-6]: [Nama tahap]

## Goal
- [Apa yang spesifik ingin dicapai? Misal: "ESP32 membaca 4 channel piezo dan menampilkan data di Serial Monitor"]

## Scope
- [Bagian mana saja yang BOLEH disentuh? Misal: "Hanya firmware ESP32 C++"]
- [Bagian mana yang TIDAK BOLEH disentuh? Misal: "JANGAN sentuh UI dashboard"]

## Files Likely Affected
- [Daftar file/folder yang kemungkinan besar perlu diedit]

## Depends On
- [Sebutkan issue lain yang harus selesai duluan, atau "Tidak ada"]

## Acceptance Criteria
- [ ] [Kriteria fungsional yang harus berjalan]
- [ ] [Kriteria performa/batas aman]
- [ ] [Validasi bahwa klaim statis di UI tidak melanggar batasan medis]

## Test / Verification
```bash
# Sesuaikan dengan subsystem:
# Embedded:
pio run
pio device monitor

# Frontend:
npm run build
npm run lint

# API:
npm test

# AI:
python -m pytest
```

## Notes
- [Catatan tambahan, referensi ke section di `fetal_guard_context_ai.md`, atau keputusan desain]
````
