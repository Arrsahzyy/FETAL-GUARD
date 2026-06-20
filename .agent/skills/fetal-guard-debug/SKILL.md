---
name: fetal-guard-debug
description: Use this to debug Fetal Guard build errors, runtime errors, BLE connection issues, API errors, Android/Capacitor errors, sensor data flow problems, or dashboard bugs.
---

# Fetal Guard Debug Skill

Gunakan alur diagnosis, bukan tebak-tebakan.

## Debugging Loop

1. Reproduce issue.
2. Catat error message persis.
3. Minimalkan kasus gagal.
4. Buat hipotesis.
5. Tambahkan log jika perlu.
6. Fix penyebab paling kecil.
7. Jalankan regression check.
8. Dokumentasikan root cause.

## Rules

- Jangan menebak tanpa log.
- Minta terminal output jika dibutuhkan.
- Jangan ubah banyak modul sekaligus.

## Required Output

````md
## Gejala
...

## Bukti Error
...

## Hipotesis
1. ...
2. ...
3. ...

## Langkah Diagnosis
...

## Perubahan yang Dilakukan
...

## Verifikasi
...

## Root Cause Sementara / Final
...
````
