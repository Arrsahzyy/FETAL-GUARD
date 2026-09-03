# Telemetry contract fixtures

Golden packets shared by the firmware, the phone gateway, and the backend. They are
loaded directly by `src/hooks/useBluetooth.test.js`, `backend/tests/test_devices.py`,
and `backend/tests/test_device_packet_auth.py`, so a change here must keep every
side in agreement.

| File | Schema | Represents |
|---|---|---|
| `v1/golden-esp32.json` | 1 | One 1 Hz snapshot frame |
| `v2/golden-esp32-window.json` | 2 | One multi-rate raw window |

## Packet signature test key

Both fixtures carry a `packet_signature` produced with this **test-only** key:

```
00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff
```

It is a fixture value, not a credential: it authenticates nothing, is not accepted
by any deployment, and must never be flashed onto a real belt. Real keys are issued
per device by `POST /devices/{id}/signing-key` and disclosed exactly once.

The signed message is built from parsed values rather than JSON text, so it is
stable across re-serialisation by the gateway:

```
FGSIG1|<device_uid>|<boot_id>|<sequence_number>|<captured_at_ms>|<schema_version>|<payload_digest>
```

`payload_digest` is `SHA-256` over `p:<v,…>|fsr:<v,…>|hr_ir:<v,…>|hr_red:<v,…>`, always
listing all four channels in that order so that omitting a channel changes the
digest instead of colliding with a packet that never carried it. `captured_at_ms` is
integer milliseconds since the Unix epoch.

Reference implementations: `backend/core/device_auth.py` and the
`appendPacketSignature` / `appendMissingDigestChannels` helpers in
`fetalguard/fetalguard.ino`.

## Regenerating a signature

After changing any signed field in a fixture:

```powershell
cd backend
.\venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'.'); from datetime import datetime; from core.device_auth import build_signing_message, sign_packet; d=json.load(open('../contracts/telemetry/v1/golden-esp32.json')); print(sign_packet('00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff', build_signing_message(device_uid=d['device_uid'], boot_id=d['boot_id'], sequence_number=d['sequence_number'], captured_at=datetime.fromisoformat(d['captured_at'].replace('Z','+00:00')), schema_version=d['schema_version'], channels=d['channels'])))"
```

## Known limitation

These fixtures verify that the backend and the JavaScript gateway agree on the
signing scheme. They do **not** prove the C++ in `fetalguard.ino` produces the same
bytes — that stays unverified until the firmware is compiled and a real packet from
hardware is checked against `POST /sessions/{id}/data`.
