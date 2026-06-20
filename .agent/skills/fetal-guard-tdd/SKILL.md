---
name: fetal-guard-tdd
description: Use this when implementing or fixing Fetal Guard code. Work in small slices, run checks, and avoid broad rewrites.
---

# Fetal Guard TDD Skill

Implementasikan satu issue kecil dalam satu sesi.

## Rules

1. Baca `AGENTS.md` dan `docs/ai/CONTEXT.md`.
2. Baca issue yang dipilih.
3. Jelaskan ulang target implementasi.
4. Identifikasi slice terkecil yang bisa diuji.
5. Lakukan perubahan minimal.
6. Jalankan check yang relevan.
7. Ringkas file yang berubah dan hasil test/build.

## Preferred Commands

```bash
npm run lint
npm run build
```

## Forbidden

- Jangan rewrite file besar tanpa alasan.
- Jangan mengubah modul yang tidak terkait.
- Jangan tambah dependency tanpa approval.
- Jangan klaim validasi medis.
