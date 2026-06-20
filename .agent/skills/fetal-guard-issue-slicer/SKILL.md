---
name: fetal-guard-issue-slicer
description: Use this to split a Fetal Guard PRD, roadmap, or implementation plan into small local issues in docs/issues.
---

# Fetal Guard Issue Slicer

Pecah PRD atau rencana implementasi menjadi issue kecil.

## Rules

- Setiap issue harus kecil dan bisa dikerjakan dalam satu sesi.
- Setiap issue harus punya acceptance criteria.
- Setiap issue harus punya cara verifikasi.
- Jangan membuat task terlalu umum seperti "improve system".
- Jangan implementasi dulu.
- Simpan issue di `docs/issues/`.

## Output Format

````md
# Issue: <Judul Singkat>

## Goal
...

## Scope
...

## Files Likely Affected
...

## Acceptance Criteria
- [ ] ...

## Test / Verification
```bash
npm run build
npm run lint
```
````
