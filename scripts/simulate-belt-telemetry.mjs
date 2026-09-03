#!/usr/bin/env node
/**
 * Stream telemetry v2 straight into the API, with no ESP32 and no BLE.
 *
 * This exists to separate two questions that are easy to confuse during bring-up:
 * "does the backend and dashboard chain work?" and "does the firmware work?".
 * Run this first. If the dashboard stays empty here, the problem is not the belt.
 *
 * It drives the same endpoints the phone gateway uses, so the session, derivation,
 * alerting, and clinician feed all exercise their real code paths.
 *
 * The waveform is synthetic. It is a signal generator, not a patient: the numbers
 * it produces are not measurements of anything and must never be presented as
 * clinical data. Point it at a dedicated test patient and a device registered as
 * bench hardware, and never at a production deployment.
 *
 * Usage:
 *   node scripts/simulate-belt-telemetry.mjs --email pasien@example.com --password ... \
 *     --device-uid FG-BENCH-01 [--fhr 140] [--maternal-hr 82] [--seconds 120]
 *
 * Options:
 *   --api            API base URL (default http://127.0.0.1:3020)
 *   --email          Patient account email (required)
 *   --password       Patient account password (required)
 *   --device-uid     Registered device UID to send as (required)
 *   --claim-code     Claim the device first, if not already paired
 *   --fhr            Fetal heart rate to synthesise, bpm (default 140)
 *   --maternal-hr    Maternal heart rate to synthesise, bpm (default 82)
 *   --seconds        How long to stream; 0 runs until interrupted (default 120)
 *   --contractions   Add periodic FSR deflections
 *   --drift          Slowly walk the fetal rate outside the reference range,
 *                    to exercise the alert path end to end
 *   --packet-secret  Sign each packet with the device's HMAC key, as firmware does.
 *                    Required once a device has a signing key provisioned.
 */

import { createHash, createHmac } from 'node:crypto';

const PIEZO_RATE_HZ = 200;
const PIEZO_CHANNELS = 4;
const FSR_RATE_HZ = 50;
const PPG_RATE_HZ = 100;
const CHUNK_SECONDS = 1;

const FHR_REFERENCE_RANGE = [110, 160];

const parseArgs = (argv) => {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const key = token.slice(2);
    const next = argv[index + 1];
    if (next === undefined || next.startsWith('--')) {
      args[key] = true;
    } else {
      args[key] = next;
      index += 1;
    }
  }
  return args;
};

const args = parseArgs(process.argv.slice(2));
const apiBase = (args.api || 'http://127.0.0.1:3020').replace(/\/+$/, '');
const email = args.email;
const password = args.password;
const deviceUid = args['device-uid'];
const claimCode = args['claim-code'];
const baseFhr = Number(args.fhr ?? 140);
const baseMaternalHr = Number(args['maternal-hr'] ?? 82);
const totalSeconds = Number(args.seconds ?? 120);
const withContractions = Boolean(args.contractions);
const withDrift = Boolean(args.drift);
const packetSecret = typeof args['packet-secret'] === 'string' ? args['packet-secret'] : null;

const SIGNED_CHANNEL_ORDER = ['p', 'fsr', 'hr_ir', 'hr_red'];

/**
 * Reproduces backend/core/device_auth.py exactly. Built from parsed values rather
 * than JSON text so it survives re-serialisation, and lists all four channels
 * every time so that omitting one changes the digest instead of colliding with a
 * packet that never carried it.
 */
const signPacket = (secret, { deviceUid: uid, bootId, sequenceNumber, capturedAtMs, schemaVersion, channels }) => {
  const digestInput = SIGNED_CHANNEL_ORDER
    .map((name) => `${name}:${(channels[name] || []).join(',')}`)
    .join('|');
  const payloadDigest = createHash('sha256').update(digestInput, 'utf8').digest('hex');
  const message = [
    'FGSIG1',
    uid,
    bootId,
    String(sequenceNumber),
    String(capturedAtMs),
    String(schemaVersion),
    payloadDigest,
  ].join('|');
  return createHmac('sha256', secret).update(message, 'utf8').digest('hex');
};

if (!email || !password || !deviceUid) {
  console.error('Missing required options. Run with --help for usage.\n');
  console.error('  node scripts/simulate-belt-telemetry.mjs \\');
  console.error('    --email pasien@example.com --password "..." --device-uid FG-BENCH-01');
  process.exit(2);
}

const request = async (path, { method = 'GET', token, body } = {}) => {
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail = payload?.detail ?? payload ?? response.statusText;
    throw new Error(`${method} ${path} -> ${response.status}: ${JSON.stringify(detail)}`);
  }
  return payload;
};

/**
 * One second of a beating-heart envelope: narrow amplitude bursts at `bpm`,
 * carried on a faster oscillation, matching the shape the piezo array sees.
 * `startIndex` keeps the phase continuous across chunk boundaries -- restarting
 * the phase every second would make the concatenated window unreadable to the
 * autocorrelation the backend runs.
 */
const beatWaveform = (bpm, sampleRateHz, seconds, startIndex, { amplitude = 800, baseline = 2048 } = {}) => {
  const total = Math.round(sampleRateHz * seconds);
  const period = (sampleRateHz * 60) / bpm;
  const samples = new Array(total);
  for (let step = 0; step < total; step += 1) {
    const index = startIndex + step;
    const phase = (index % period) / period;
    const envelope = Math.exp(-((phase * 8) ** 2));
    const carrier = Math.sin((2 * Math.PI * 12 * index) / sampleRateHz);
    samples[step] = Math.round(baseline + amplitude * envelope * carrier);
  }
  return samples;
};

const interleave = (channels) => {
  const length = channels[0].length;
  const output = new Array(length * channels.length);
  for (let sample = 0; sample < length; sample += 1) {
    for (let channel = 0; channel < channels.length; channel += 1) {
      output[sample * channels.length + channel] = channels[channel][sample];
    }
  }
  return output;
};

const fsrWaveform = (seconds, elapsedSeconds) => {
  const total = Math.round(FSR_RATE_HZ * seconds);
  const samples = new Array(total);
  for (let step = 0; step < total; step += 1) {
    // A slow swell every ~40 s, roughly the cadence of a contraction pattern.
    const t = elapsedSeconds + step / FSR_RATE_HZ;
    const swell = withContractions ? Math.max(0, Math.sin((2 * Math.PI * t) / 40)) ** 4 : 0;
    samples[step] = Math.round(700 + swell * 900);
  }
  return samples;
};

/** Walks the fetal rate outside the reference range so the alert path can be seen firing. */
const fhrAtSecond = (second) => {
  if (!withDrift) return baseFhr;
  const cycle = second % 180;
  if (cycle < 60) return baseFhr;
  if (cycle < 120) return Math.max(70, baseFhr - Math.round((cycle - 60) * 0.9));
  return baseFhr;
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const main = async () => {
  console.log(`FETAL-GUARD telemetry simulator -> ${apiBase}`);
  console.log('Synthetic signal generator. Not patient data. Do not run against production.\n');

  const login = await request('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  const token = login.access_token;
  if (!token) throw new Error('Login succeeded but returned no access token');
  console.log(`Signed in as ${email}`);

  if (claimCode) {
    try {
      await request('/devices/claim', {
        method: 'POST',
        token,
        body: { device_uid: deviceUid, claim_code: claimCode },
      });
      console.log(`Claimed device ${deviceUid}`);
    } catch (error) {
      console.log(`Claim skipped: ${error.message}`);
    }
  }

  const registered = await request('/devices/me', { token });
  const match = registered.find((device) => device.device_uid?.toUpperCase() === deviceUid.toUpperCase());
  if (!match) {
    throw new Error(
      `Device ${deviceUid} is not paired to this patient. `
      + 'Register it and pass --claim-code, or pair it in the app first.',
    );
  }
  if (match.packet_secret_provisioned_at && !packetSecret) {
    throw new Error(
      `Device ${deviceUid} has a packet signing key provisioned, so every packet must be signed. `
      + 'Pass --packet-secret with the key issued by POST /devices/{id}/signing-key.',
    );
  }
  if (packetSecret) console.log('Signing every packet with the provided device key');

  let session;
  try {
    session = await request('/sessions/active', { token });
    console.log(`Reusing active session ${session.id}`);
  } catch {
    session = await request('/sessions', { method: 'POST', token, body: {} });
    console.log(`Started session ${session.id}`);
  }

  const bootId = `boot-sim-${Date.now().toString(36)}`;
  let sequence = 0;
  let piezoIndex = 0;
  let ppgIndex = 0;
  let sent = 0;
  let failed = 0;
  let stopping = false;

  process.on('SIGINT', () => {
    stopping = true;
    console.log('\nStopping after the current packet...');
  });

  const startedAt = Date.now();
  while (!stopping && (totalSeconds === 0 || sequence < totalSeconds)) {
    const elapsedSeconds = Math.round((Date.now() - startedAt) / 1000);
    const fhr = fhrAtSecond(elapsedSeconds);
    const capturedAt = new Date();

    const beat = beatWaveform(fhr, PIEZO_RATE_HZ, CHUNK_SECONDS, piezoIndex);
    const quiet = new Array(beat.length).fill(2048);
    const piezo = interleave([quiet, quiet, beat, quiet]);
    const ppg = beatWaveform(baseMaternalHr, PPG_RATE_HZ, CHUNK_SECONDS, ppgIndex, {
      baseline: 50000,
      amplitude: 6000,
    });

    piezoIndex += Math.round(PIEZO_RATE_HZ * CHUNK_SECONDS);
    ppgIndex += Math.round(PPG_RATE_HZ * CHUNK_SECONDS);

    const channels = {
      p: piezo,
      fsr: fsrWaveform(CHUNK_SECONDS, elapsedSeconds),
      hr_ir: ppg,
      hr_red: ppg,
    };

    const chunk = {
      payload: { t: capturedAt.getTime(), ...channels },
      schema_version: 2,
      ingestion_id: `sim-${bootId}-${sequence}`,
      boot_id: bootId,
      sequence_number: sequence,
      captured_at: capturedAt.toISOString(),
      sample_rates_hz: {
        p: PIEZO_RATE_HZ,
        fsr: FSR_RATE_HZ,
        hr_ir: PPG_RATE_HZ,
        hr_red: PPG_RATE_HZ,
      },
      channel_layout: { p: PIEZO_CHANNELS },
      device_uid: deviceUid,
      source: 'ble',
      is_simulated: false,
    };

    if (packetSecret) {
      chunk.packet_signature = signPacket(packetSecret, {
        deviceUid,
        bootId,
        sequenceNumber: sequence,
        capturedAtMs: capturedAt.getTime(),
        schemaVersion: 2,
        channels,
      });
    }

    try {
      await request(`/sessions/${session.id}/data`, { method: 'POST', token, body: chunk });
      sent += 1;
      const outOfRange = fhr < FHR_REFERENCE_RANGE[0] || fhr > FHR_REFERENCE_RANGE[1];
      process.stdout.write(
        `\rseq ${sequence}  sent ${sent}  failed ${failed}  fhr ${fhr} bpm${outOfRange ? ' (outside reference range)' : ''}   `,
      );
    } catch (error) {
      failed += 1;
      console.error(`\n${error.message}`);
      if (failed >= 5) throw new Error('Too many consecutive upload failures, stopping.');
    }

    sequence += 1;
    await sleep(CHUNK_SECONDS * 1000);
  }

  console.log(`\n\nSent ${sent} packets (${failed} failed).`);
  console.log(`Session ${session.id} is still open. Stop it from the patient app when you are done.`);
};

main().catch((error) => {
  console.error(`\n${error.message}`);
  process.exit(1);
});
