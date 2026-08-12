# Issue: [PWR] Setup Baterai 2S dan Buck Converter

## Roadmap Stage
- Tahap 1: PoC Sensor & Power

## Goal
- Mendesain dan merakit sirkuit daya untuk mengubah output baterai Li-ion 2S (7.4V) menjadi tegangan stabil 5V (untuk LM324) dan 3.3V (untuk ESP32 dan MAX30102).

## Scope
- Boleh menyentuh: Skematik daya, modul TP5100 (charger), LM2596/MP1584 (buck converter 5V), AMS1117-3.3 (LDO 3.3V).
- Tidak boleh menyentuh: Sensor akuisisi, firmware, atau mobile app.

## Files Likely Affected
- `docs/hardware/power_schematic.md` (Jika ada/dibuat baru)

## Depends On
- Tidak ada

## Acceptance Criteria
- [ ] Baterai 2S dapat dicas menggunakan modul TP5100 tanpa overcharge.
- [ ] Buck converter menghasilkan tegangan stabil 5V (toleransi ±0.1V) saat ESP32 aktif.
- [ ] Modul LDO / internal regulator ESP32 menghasilkan tegangan stabil 3.3V.
- [ ] Komponen tidak mengalami overheating saat beroperasi selama 30 menit.

## Test / Verification
```bash
# Pengujian dilakukan secara manual menggunakan Multimeter Digital.
# 1. Ukur Vout baterai 2S (max 8.4V).
# 2. Ukur Vout buck converter (target 5V).
# 3. Ukur Vout pin 3.3V ESP32.
```

## Notes
- Referensi canonical: `AGENTS.md` bagian hardware baseline dan `FETAL_GUARD_ROADMAP.md` bagian hardware PoC/power.
- Sangat penting untuk menyesuaikan trimpot buck converter ke 5V *sebelum* menghubungkannya ke komponen lain agar tidak terjadi kerusakan *overvoltage*.
