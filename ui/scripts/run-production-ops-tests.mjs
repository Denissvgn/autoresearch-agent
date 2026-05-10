import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outDir = join(tmpdir(), 'autoresearch-agent-ui-production-ops-tests');
if (existsSync(outDir)) rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'package.json'), '{"type":"module"}\n', 'utf8');

execFileSync(
  join(root, 'node_modules', '.bin', 'tsc'),
  [
    '--target',
    'ES2020',
    '--module',
    'ES2020',
    '--moduleResolution',
    'bundler',
    '--strict',
    '--skipLibCheck',
    '--outDir',
    outDir,
    join(root, 'src', 'vite-env.d.ts'),
    join(root, 'src', 'utils', 'productionOps.ts'),
    join(root, 'src', 'api', 'client.ts'),
  ],
  { stdio: 'inherit' }
);

function findCompiledModule(dir, fileName) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      const found = findCompiledModule(path, fileName);
      if (found) return found;
    }
    if (entry.isFile() && entry.name === fileName) return path;
  }
  return null;
}

const compiledPath = findCompiledModule(outDir, 'productionOps.js');
assert.ok(compiledPath, 'compiled productionOps.js exists');
const ops = await import(pathToFileURL(compiledPath).href);
const compiledClientPath = findCompiledModule(outDir, 'client.js');
assert.ok(compiledClientPath, 'compiled client.js exists');
const client = await import(pathToFileURL(compiledClientPath).href);

test('scopeSummary blocks promotion when prior scopes are missing', () => {
  const summary = ops.scopeSummary({
    scope: 'production',
    status: 'blocked',
    ready: false,
    requires_approval: true,
    required_prior_scopes: ['development', 'paper', 'canary'],
    blockers: ['missing_canary_promotion'],
    blocker_details: [{ code: 'missing_canary_promotion', label: 'A canary promotion record is required first.' }],
    promotion: null,
  });

  assert.equal(summary.tone, 'danger');
  assert.equal(summary.canConfirm, false);
  assert.match(summary.message, /canary promotion/);
});

test('scopeSummary allows ready development promotions', () => {
  const summary = ops.scopeSummary({
    scope: 'development',
    status: 'ready',
    ready: true,
    requires_approval: false,
    required_prior_scopes: [],
    blockers: [],
    blocker_details: [],
    promotion: null,
  });

  assert.equal(summary.tone, 'success');
  assert.equal(summary.canConfirm, true);
});

test('productionReady recognizes promoted production scope', () => {
  assert.equal(ops.productionReady({
    promotion: {
      scopes: [
        { scope: 'development', status: 'promoted' },
        { scope: 'paper', status: 'promoted' },
        { scope: 'canary', status: 'promoted' },
        { scope: 'production', status: 'promoted' },
      ],
    },
  }), true);
});

test('humanizeBlocker keeps operator-readable fallback labels', () => {
  assert.equal(ops.humanizeBlocker('missing_rl_oos_provenance'), 'RL OOS and feature provenance evidence is missing.');
  assert.equal(ops.humanizeBlocker('custom_blocker_name'), 'Custom blocker name.');
});

test('normalizeListResponse accepts paginated and legacy array API shapes', () => {
  const items = [{ id: 'research-1' }];
  assert.deepEqual(client.normalizeListResponse(items), items);
  assert.deepEqual(client.normalizeListResponse({ items, total: 1, limit: 100, offset: 0 }), items);
  assert.deepEqual(client.normalizeListResponse({ detail: 'not a list' }), []);
});
