# Issue: [HW] Integrasi FSR408 dan MAX30102

## Roadmap Stage
- Tahap 1: PoC Sensor & Power

## Goal
- Merangkai FSR408 dengan *voltage divider* untuk mengukur tekanan fisik (indikasi kontraksi).
- Menghubungkan MAX30102 ke pin I2C ESP32 untuk mendeteksi denyut jantung ibu.

## Scope
- Boleh menyentuh: Hardware wiring FSR408 dan MAX30102.
- Tidak boleh menyentuh: Rangkaian piezoelektrik.

## Files Likely Affected
- `docs/hardware/sensor_wiring.md`

## Depends On
- `0001-power-2s-buck-converter.md` (Supply 3.3V stabil diperlukan untuk MAX30102)

## Acceptance Criteria
- [ ] FSR408 memberikan pembacaan analog yang berubah ketika ditekan.
- [ ] I2C Scanner pada ESP32 dapat mendeteksi alamat I2C MAX30102 (umumnya 0x57).
- [ ] Pembacaan nilai Red dan IR dari MAX30102 berhasil ditampilkan di Serial Monitor tanpa error *buffer underflow*.

## Test / Verification
```bash
# Flash kode I2C scanner & analog read
pio run -t upload
pio device monitor
```

## Notes
- FSR408 dirangkai dengan resistor 10k Ohm sebagai pembagi tegangan (pull-down).
- MAX30102 sangat sensitif terhadap fluktuasi daya 3.3V. Pastikan VCC dari regulator LDO murni, bukan dari pin 3.3V ESP32 jika ESP32 sedang *heavy transmitting*.
