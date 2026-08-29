import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, '..');

export function parseLocalServerArgs(argv) {
  const options = {
    backendPort: 3020,
    frontendPort: 5173,
    smoke: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === '--smoke') {
      options.smoke = true;
      continue;
    }
    if (argument === '--backend-port' || argument === '--frontend-port') {
      const value = Number(argv[index + 1]);
      if (!Number.isInteger(value) || value < 1024 || value > 65535) {
        throw new Error(`${argument} harus berupa port 1024-65535`);
      }
      if (argument === '--backend-port') options.backendPort = value;
      else options.frontendPort = value;
      index += 1;
      continue;
    }
    throw new Error(`Argumen local server tidak dikenal: ${argument}`);
  }
  if (options.backendPort === options.frontendPort) {
    throw new Error('Port backend dan frontend harus berbeda');
  }
  return options;
}

export function createLocalEnvironment({ backendPort, frontendPort, databasePath }) {
  const normalizedDatabasePath = path.resolve(databasePath).replaceAll('\\', '/');
  const frontendOrigins = [
    `http://127.0.0.1:${frontendPort}`,
    `http://localhost:${frontendPort}`,
  ];
  return {
    backend: {
      ...process.env,
      ENVIRONMENT: 'development',
      AUTO_CREATE_DB: 'false',
      SQLALCHEMY_DATABASE_URI: `sqlite:///${normalizedDatabasePath}`,
      BACKEND_CORS_ORIGINS: JSON.stringify(frontendOrigins),
      TRUSTED_HOSTS: JSON.stringify(['127.0.0.1', 'localhost']),
      AI_PIPELINE_MODE: 'disabled',
    },
    frontend: {
      ...process.env,
      VITE_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
    },
  };
}

function assertFile(filePath, message) {
  if (!fs.existsSync(filePath)) throw new Error(message);
}

function assertPortAvailable(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once('error', (error) => {
      if (error.code === 'EADDRINUSE') {
        reject(new Error(`Port ${port} sedang dipakai. Hentikan server lama, lalu coba lagi.`));
        return;
      }
      reject(error);
    });
    server.listen({ host: '127.0.0.1', port }, () => {
      server.close(resolve);
    });
  });
}

function isUrlReady(url) {
  return new Promise((resolve) => {
    const request = http.get(url, { timeout: 1500 }, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 500);
    });
    request.once('timeout', () => {
      request.destroy();
      resolve(false);
    });
    request.once('error', () => resolve(false));
  });
}

async function waitForUrl(url, child, label, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`${label} berhenti sebelum siap (exit ${child.exitCode})`);
    }
    if (await isUrlReady(url)) return;
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  throw new Error(`${label} tidak siap dalam ${Math.round(timeoutMs / 1000)} detik`);
}

function terminateChild(child) {
  if (child && child.exitCode === null && !child.killed) child.kill();
}

export async function runLocalServer(argv = process.argv.slice(2)) {
  const options = parseLocalServerArgs(argv);
  const backendDirectory = path.join(repositoryRoot, 'backend');
  const pythonPath = path.join(backendDirectory, 'venv', 'Scripts', 'python.exe');
  const vitePath = path.join(repositoryRoot, 'node_modules', 'vite', 'bin', 'vite.js');
  const databasePath = path.join(backendDirectory, 'fetal_guard.local-mobile.db');

  assertFile(pythonPath, 'Backend virtual environment belum tersedia di backend/venv.');
  assertFile(vitePath, 'Dependency frontend belum tersedia. Jalankan npm.cmd install terlebih dahulu.');
  await Promise.all([
    assertPortAvailable(options.backendPort),
    assertPortAvailable(options.frontendPort),
  ]);

  const environment = createLocalEnvironment({
    backendPort: options.backendPort,
    frontendPort: options.frontendPort,
    databasePath,
  });

  console.log('[local] Menjalankan migrasi database local-mobile...');
  const migration = spawnSync(
    pythonPath,
    ['-m', 'alembic', 'upgrade', 'head'],
    {
      cwd: backendDirectory,
      env: environment.backend,
      stdio: 'inherit',
      windowsHide: true,
    },
  );
  if (migration.error) throw migration.error;
  if (migration.status !== 0) throw new Error('Migrasi database local-mobile gagal');
  assertFile(databasePath, 'Database local-mobile tidak berhasil dibuat atau ditemukan.');

  let backend = null;
  let frontend = null;
  let stopping = false;
  const stopChildren = () => {
    if (stopping) return;
    stopping = true;
    terminateChild(frontend);
    terminateChild(backend);
  };

  try {
    backend = spawn(
      pythonPath,
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(options.backendPort)],
      {
        cwd: backendDirectory,
        env: environment.backend,
        stdio: 'inherit',
        windowsHide: true,
      },
    );
    frontend = spawn(
      process.execPath,
      [vitePath, '--host', '127.0.0.1', '--port', String(options.frontendPort), '--strictPort'],
      {
        cwd: repositoryRoot,
        env: environment.frontend,
        stdio: 'inherit',
        windowsHide: true,
      },
    );

    const backendHealthUrl = `http://127.0.0.1:${options.backendPort}/health/live`;
    const frontendUrl = `http://127.0.0.1:${options.frontendPort}`;
    await Promise.all([
      waitForUrl(backendHealthUrl, backend, 'Backend'),
      waitForUrl(frontendUrl, frontend, 'Frontend'),
    ]);

    console.log('');
    console.log('[local] FETAL-GUARD siap digunakan.');
    console.log(`[local] Website       : ${frontendUrl}`);
    console.log(`[local] Login pasien  : ${frontendUrl}/login/ibu-hamil`);
    console.log(`[local] Login nakes   : ${frontendUrl}/login/nakes`);
    console.log(`[local] Login admin   : ${frontendUrl}/login/admin`);
    console.log(`[local] Backend health: ${backendHealthUrl}`);
    console.log(`[local] API docs      : http://127.0.0.1:${options.backendPort}/docs`);
    console.log(`[local] Database      : ${databasePath}`);

    if (options.smoke) {
      console.log('[local] Smoke check lulus; menghentikan server uji.');
      return;
    }

    console.log('[local] Tekan Ctrl+C untuk menghentikan frontend dan backend.');
    await new Promise((resolve, reject) => {
      const handleSignal = () => resolve();
      process.once('SIGINT', handleSignal);
      process.once('SIGTERM', handleSignal);
      backend.once('exit', (code) => {
        if (!stopping) reject(new Error(`Backend berhenti (exit ${code})`));
      });
      frontend.once('exit', (code) => {
        if (!stopping) reject(new Error(`Frontend berhenti (exit ${code})`));
      });
    });
  } finally {
    stopChildren();
  }
}

const isMainModule = process.argv[1]
  && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMainModule) {
  runLocalServer().catch((error) => {
    console.error(`[local] Gagal: ${error.message}`);
    process.exitCode = 1;
  });
}
