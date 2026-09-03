import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const SRC_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const LOCALES = ['id', 'en'];

const readLocaleSource = (locale) => fs.readFileSync(
  new URL(`./${locale}.json`, import.meta.url),
  'utf8',
);

const flatten = (value, prefix = '') => Object.entries(value).reduce((keys, [key, entry]) => {
  const path = prefix ? `${prefix}.${key}` : key;
  if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
    return { ...keys, ...flatten(entry, path) };
  }
  return { ...keys, [path]: entry };
}, {});

// JSON.parse silently keeps the last of two identical keys, so a duplicated
// block disappears without any parse error. That is exactly how a whole set of
// `common.*` strings became unreachable and started rendering as raw dotted keys
// in the UI. Walk the raw text instead of trusting the parsed object.
const findDuplicateKeys = (source) => {
  const duplicates = [];
  const stack = [new Set()];
  let insideString = false;
  let escaped = false;
  let current = '';
  let capturing = false;

  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];

    if (insideString) {
      if (escaped) {
        current += character;
        escaped = false;
      } else if (character === '\\') {
        escaped = true;
      } else if (character === '"') {
        insideString = false;
        capturing = true;
      } else {
        current += character;
      }
      continue;
    }

    if (character === '"') {
      insideString = true;
      current = '';
      continue;
    }
    if (character === ':' && capturing) {
      const scope = stack[stack.length - 1];
      if (scope.has(current)) duplicates.push(current);
      scope.add(current);
      capturing = false;
      continue;
    }
    if (character === '{') {
      stack.push(new Set());
      capturing = false;
      continue;
    }
    if (character === '}') {
      stack.pop();
      capturing = false;
      continue;
    }
    if (character === ',') capturing = false;
  }

  return duplicates;
};

test('no locale defines the same key twice in one object', () => {
  for (const locale of LOCALES) {
    const duplicates = findDuplicateKeys(readLocaleSource(locale));
    assert.deepEqual(
      duplicates,
      [],
      `${locale}.json defines duplicate keys, which silently shadow the earlier block: ${duplicates.join(', ')}`,
    );
  }
});

test('the duplicate detector actually detects a duplicate', () => {
  const source = '{"a": {"x": 1}, "b": {"x": 2}, "a": {"y": 3}}';

  assert.deepEqual(findDuplicateKeys(source), ['a']);
});

test('locales define exactly the same keys', () => {
  const [id, en] = LOCALES.map((locale) => flatten(JSON.parse(readLocaleSource(locale))));
  const idKeys = Object.keys(id).sort();
  const enKeys = Object.keys(en).sort();

  assert.deepEqual(idKeys.filter((key) => !(key in en)), [], 'keys missing from en.json');
  assert.deepEqual(enKeys.filter((key) => !(key in id)), [], 'keys missing from id.json');
});

test('no locale ships an empty string', () => {
  for (const locale of LOCALES) {
    const entries = Object.entries(flatten(JSON.parse(readLocaleSource(locale))));
    const empty = entries.filter(([, value]) => typeof value === 'string' && !value.trim());
    assert.deepEqual(empty.map(([key]) => key), [], `${locale}.json has empty values`);
  }
});

// Every dotted key the source passes to t() must resolve, otherwise t() returns
// the key itself and the user reads "common.apiUnavailable" on screen.
const collectReferencedKeys = (directory) => {
  const referenced = new Set();
  const pattern = /\bt\(\s*(['"`])([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)\1/g;

  const walk = (currentPath) => {
    for (const entry of fs.readdirSync(currentPath, { withFileTypes: true })) {
      const entryPath = path.join(currentPath, entry.name);
      if (entry.isDirectory()) {
        walk(entryPath);
        continue;
      }
      if (!/\.(js|jsx)$/.test(entry.name) || entry.name.endsWith('.test.js')) continue;
      const source = fs.readFileSync(entryPath, 'utf8');
      for (const match of source.matchAll(pattern)) referenced.add(match[2]);
    }
  };

  walk(directory);
  return referenced;
};

test('every translation key used in the app resolves in both locales', () => {
  const referenced = collectReferencedKeys(SRC_ROOT);
  const catalogues = Object.fromEntries(
    LOCALES.map((locale) => [locale, flatten(JSON.parse(readLocaleSource(locale)))]),
  );
  const missing = [];

  assert.ok(referenced.size > 50, 'expected to find translation keys to check');
  for (const key of referenced) {
    for (const locale of LOCALES) {
      if (!(key in catalogues[locale])) missing.push(`${locale}: ${key}`);
    }
  }

  assert.deepEqual(missing.sort(), [], 'these keys render as raw text in the UI');
});
