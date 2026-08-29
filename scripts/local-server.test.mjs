import assert from 'node:assert/strict';
import path from 'node:path';
import test from 'node:test';

import { createLocalEnvironment, parseLocalServerArgs } from './local-server.mjs';

test('local server uses the canonical 3020/5173 ports by default', () => {
  assert.deepEqual(parseLocalServerArgs([]), {
    backendPort: 3020,
    frontendPort: 5173,
    smoke: false,
  });
});

test('local server validates explicit smoke-test ports', () => {
  assert.deepEqual(
    parseLocalServerArgs(['--smoke', '--backend-port', '3021', '--frontend-port', '5174']),
    { backendPort: 3021, frontendPort: 5174, smoke: true },
  );
  assert.throws(() => parseLocalServerArgs(['--backend-port', '80']), /1024-65535/);
  assert.throws(
    () => parseLocalServerArgs(['--backend-port', '3020', '--frontend-port', '3020']),
    /harus berbeda/,
  );
});

test('local environment binds Vite, CORS, and the local-mobile database together', () => {
  const databasePath = path.join('E:', 'PROJECT', 'PKM KC ACA', 'backend', 'fetal_guard.local-mobile.db');
  const environment = createLocalEnvironment({
    backendPort: 3020,
    frontendPort: 5173,
    databasePath,
  });

  assert.equal(environment.frontend.VITE_API_BASE_URL, 'http://127.0.0.1:3020');
  assert.match(environment.backend.SQLALCHEMY_DATABASE_URI, /fetal_guard\.local-mobile\.db$/);
  assert.deepEqual(JSON.parse(environment.backend.BACKEND_CORS_ORIGINS), [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
  ]);
  assert.equal(environment.backend.AI_PIPELINE_MODE, 'disabled');
});
