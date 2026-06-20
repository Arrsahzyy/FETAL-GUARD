# AGENTS.md — Fetal Guard PKM-KC

## Project Overview

Fetal Guard adalah prototype PKM-KC untuk skrining awal risiko pada ibu hamil berbasis sensor, konektivitas, dashboard, dan rencana hybrid AI/deep learning.

Project ini tidak boleh diklaim sebagai alat diagnosis medis dan tidak menggantikan CTG, tocotransducer, Doppler, dokter, bidan, atau alat rumah sakit.

## Agent Workflow

Sebelum mengedit file, agent wajib:

1. Membaca konteks project.
2. Menjelaskan ulang permintaan user.
3. Mengidentifikasi subsystem terdampak.
4. Bertanya jika requirement belum jelas.
5. Membuat implementation plan.
6. Menunggu approval untuk perubahan besar.

## Subsystem

- Frontend/dashboard
- Mobile/Android/Capacitor
- API/backend
- Embedded/ESP32
- BLE/WiFi/cloud connectivity
- AI/ML pipeline
- Dokumentasi dan proposal
- Validasi dan testing

## Safety Rules

- Jangan membuat klaim medis berlebihan.
- Jangan mengarang akurasi, sensitivitas, spesifisitas, atau hasil validasi.
- Jangan menampilkan API key, token, password, atau isi `.env`.
- Jangan menjalankan command destruktif seperti `git reset --hard` tanpa izin.
- Jangan install dependency baru tanpa menjelaskan alasannya.

## Development Commands

Gunakan command berikut jika relevan:

```bash
npm install
npm run dev
npm run build
npm run lint
```
