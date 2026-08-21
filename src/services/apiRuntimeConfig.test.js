import assert from 'node:assert/strict';
import test from 'node:test';

import {
  evaluateApiRuntimePolicy,
  isPrivateNetworkHttpUrl,
  normalizePrivateNetworkApiBaseUrl,
} from './apiRuntimeConfig.js';

test('private HTTP API detection is limited to RFC1918 IPv4 ranges', () => {
  assert.equal(isPrivateNetworkHttpUrl('http://192.168.1.22:8000'), true);
  assert.equal(isPrivateNetworkHttpUrl('http://172.20.4.2:8000'), true);
  assert.equal(isPrivateNetworkHttpUrl('http://10.0.2.2:8000'), true);
  assert.equal(isPrivateNetworkHttpUrl('http://8.8.8.8:8000'), false);
  assert.equal(isPrivateNetworkHttpUrl('https://192.168.1.22:8000'), false);
});

test('local API address normalization accepts only a private HTTP origin', () => {
  assert.equal(
    normalizePrivateNetworkApiBaseUrl(' http://192.168.1.15:8000/ '),
    'http://192.168.1.15:8000',
  );
  assert.equal(normalizePrivateNetworkApiBaseUrl('http://192.168.1.15:8000/auth'), null);
  assert.equal(normalizePrivateNetworkApiBaseUrl('http://user:pass@192.168.1.15:8000'), null);
  assert.equal(normalizePrivateNetworkApiBaseUrl('http://8.8.8.8:8000'), null);
  assert.equal(normalizePrivateNetworkApiBaseUrl('https://192.168.1.15:8000'), null);
});

test('production rejects insecure remote APIs by default', () => {
  const policy = evaluateApiRuntimePolicy({
    configuredApiBaseUrl: 'http://192.168.1.22:8000',
    isNativeRuntime: true,
    isProduction: true,
    mode: 'production',
    allowInsecureLocalApi: false,
  });

  assert.equal(policy.hasUnsafeProductionApiConfig, true);
  assert.equal(policy.localAndroidDebugAllowed, false);
});

test('explicit Android local mode only permits a private development API', () => {
  const localPolicy = evaluateApiRuntimePolicy({
    configuredApiBaseUrl: 'http://192.168.1.22:8000',
    isNativeRuntime: true,
    isProduction: true,
    mode: 'android-local',
    allowInsecureLocalApi: true,
  });
  const publicPolicy = evaluateApiRuntimePolicy({
    configuredApiBaseUrl: 'http://8.8.8.8:8000',
    isNativeRuntime: true,
    isProduction: true,
    mode: 'android-local',
    allowInsecureLocalApi: true,
  });

  assert.equal(localPolicy.localAndroidDebugAllowed, true);
  assert.equal(localPolicy.hasUnsafeProductionApiConfig, false);
  assert.equal(publicPolicy.localAndroidDebugAllowed, false);
  assert.equal(publicPolicy.hasUnsafeProductionApiConfig, true);
});
