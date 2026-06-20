---
name: fetal-guard-tdd
description: Use this when implementing or fixing Fetal Guard code. Work in small slices, run checks, and avoid broad rewrites.
---

# Fetal Guard TDD Skill

Implementasikan satu issue kecil dalam satu sesi.

## Rules

1. Baca `AGENTS.md` dan `docs/ai/CONTEXT.md` terlebih dahulu.
2. Baca issue yang dipilih dari `docs/issues/`.
3. Jelaskan ulang target implementasi dan subsystem yang tersentuh.
4. Identifikasi slice terkecil yang bisa diuji.
5. Lakukan perubahan minimal — hanya file yang ada di scope issue.
6. Jalankan check yang relevan berdasarkan subsystem (lihat tabel di bawah).
7. Ringkas file yang berubah dan hasil test/build.

## Preferred Commands — Per Subsystem

| Subsystem | Build/Compile | Test/Verify | Monitor/Debug |
|---|---|---|---|
| **Frontend/Dashboard** | `npm run build` | `npm run lint` | `npm run dev` |
| **Mobile App** | `npm run build` | `npx cap sync` | `npx cap run android` |
| **API/Backend** | `npm run build` | `npm test` | `npm run dev` |
| **Embedded (PlatformIO)** | `pio run` | `pio test` | `pio device monitor` |
| **Embedded (Arduino CLI)** | `arduino-cli compile` | — | `arduino-cli monitor` |
| **AI/ML** | — | `python -m pytest` | `python train.py` |

## Forbidden

- Jangan rewrite file besar tanpa alasan — edit hanya bagian yang relevan.
- Jangan mengubah modul yang tidak ada di scope issue.
- Jangan tambah dependency tanpa approval (jelaskan alasan jika perlu).
- Jangan klaim validasi medis.
- Jangan mengubah threshold klinis (FHR 110-160 bpm) tanpa approval.
- Jangan mengubah pin mapping ESP32 tanpa mengecek skematik.
- Jangan menghapus sensor dari arsitektur.

## Output Format

Setelah implementasi selesai, berikan ringkasan:

````md
## Target Issue
- [Judul issue dan path file di `docs/issues/`]

## Subsystem yang Tersentuh
- [Daftar subsystem yang benar-benar diubah]

## File yang Diubah
- [Daftar file beserta ringkasan perubahan per file]

## Hasil Build/Test
- [Output dari command yang dijalankan]

## Catatan
- [Hal yang perlu diperhatikan untuk issue berikutnya]
````

Setelah implementasi selesai, rekomendasikan menjalankan `fetal-guard-review`.
