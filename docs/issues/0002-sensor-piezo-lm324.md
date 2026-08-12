# Issue: [AFE] Rangkaian 4x Piezo dan LM324 Pre-Amp

## Roadmap Stage
- Tahap 1: PoC Sensor & Power

## Goal
- Mengkondisikan sinyal analog dari 4 sensor piezoelektrik menggunakan LM324 (Pre-Amplifier) agar memiliki amplitudo yang cukup untuk dibaca oleh ADC ESP32.

## Scope
- Boleh menyentuh: Rangkaian piezoelektrik, LM324, resistor, kapasitor (filter dasar).
- Tidak boleh menyentuh: Modul FSR, MAX30102, firmware BLE.

## Files Likely Affected
- `docs/hardware/afe_schematic.md`

## Depends On
- `0001-power-2s-buck-converter.md` (Membutuhkan supply 5V yang stabil untuk LM324)

## Acceptance Criteria
- [ ] 4 piezoelektrik terhubung ke 4 op-amp (dalam 1 atau 2 chip LM324).
- [ ] Sinyal output AFE berada di rentang tegangan 0-3.3V (agar aman untuk pin ADC ESP32).
- [ ] Mengetuk sensor piezoelektrik akan menghasilkan lonjakan tegangan yang terukur di pin output.

## Test / Verification
```bash
# Pengujian dilakukan dengan osiloskop portabel atau dengan ESP32 sederhana.
# Flash kode ADC read sederhana:
pio run -t upload
pio device monitor
```

## Notes
- Referensi canonical: `AGENTS.md` bagian hardware baseline dan `FETAL_GUARD_ROADMAP.md` bagian hardware PoC. Pin output LM324 tidak boleh melebih 3.3V, atau wajib menggunakan *voltage divider* pelindung sebelum masuk ke ESP32.
