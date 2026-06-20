---
name: fetal-guard-review
description: Use this after implementing a Fetal Guard task to review code, docs, medical-claim safety, build status, and next steps.
---

# Fetal Guard Review Skill

Review perubahan sebelum dianggap selesai.

## Review Checklist

Cek:

- Apakah perubahan sesuai issue/PRD?
- Apakah klaim medis tetap konservatif?
- Apakah build/lint sudah dijalankan?
- Apakah dokumentasi perlu diupdate?
- Apakah ada asumsi yang perlu dicatat?
- Apakah ada secret/API key yang tidak sengaja terbuka?
- Apakah ada perubahan tidak terkait?

## Output Format

````md
## Ringkasan Perubahan
...

## File yang Diubah
...

## Hasil Build/Test
...

## Risiko
...

## Dokumentasi yang Perlu Diupdate
...

## Status
DONE / NEEDS_REVISION / BLOCKED
````
