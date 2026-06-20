---
name: fetal-guard-prd
description: Use this to turn a clarified Fetal Guard feature idea into a PRD stored in docs/prd.
---

# Fetal Guard PRD Skill

Ubah requirement yang sudah jelas menjadi PRD praktis.

## Rules

- Tulis dalam bahasa Indonesia.
- Klaim medis harus konservatif.
- Jika fitur menyentuh interpretasi kesehatan, wajib sebutkan kebutuhan validasi.
- Simpan PRD di `docs/prd/`.
- Jangan implementasi kode sebelum diminta.

## PRD Structure

```md
# PRD: <Nama Fitur>

## 1. Latar Belakang
...

## 2. Tujuan
...

## 3. Non-Tujuan
...

## 4. Pengguna
- Pasien/ibu hamil
- Tenaga kesehatan
- Tim pengembang/admin

## 5. Requirement Fungsional
...

## 6. Requirement Non-Fungsional
...

## 7. Data yang Dibutuhkan
...

## 8. Alur Sistem
...

## 9. Risiko dan Batasan
...

## 10. Validasi
...

## 11. Acceptance Criteria
- [ ] ...
- [ ] ...
- [ ] ...
```

Setelah PRD selesai, rekomendasikan menjalankan `fetal-guard-issue-slicer`.
