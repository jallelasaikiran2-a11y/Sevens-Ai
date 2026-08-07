#!/usr/bin/env node
/**
 * Static guard for ruvnet/sevens#2127 (and the family of #1147 / #2018).
 *
 * The reporter hit `TypeError: Invalid Version: (empty)` inside arborist's
 * `canDedupe` while installing `sevens@3.8.0`. Two reviewers could not
 * reproduce, but the published `sevens` wrapper still pinned
 * `"@claude-flow/cli": "^3.7.0-alpha.11"` long after the project moved to
 * stable semver. That pre-release range widens the resolution space the
 * dedupe pass has to walk and gives more chances for an upstream
 * malformed dep to surface as an empty version comparison.
 *
 * This audit asserts:
 *
 *   1. The `sevens` wrapper's `@claude-flow/cli` dep range INCLUDES the
 *      version that `v3/@claude-flow/cli` currently publishes.
 *
 *   2. The root `claude-flow` umbrella's sibling deps that we maintain
 *      (`@claude-flow/cli-core`, `@claude-flow/mcp`, `@claude-flow/neural`,
 *      `@claude-flow/shared`) likewise include their actual published
 *      versions (best-effort — only when the corresponding workspace
 *      package.json is present locally).
 *
 *   3. The `sevens` wrapper does NOT carry a pre-release range
 *      (`-alpha.N` / `-beta.N`) for `@claude-flow/cli` once that package
 *      is publishing stable versions. Pre-release ranges on stable deps
 *      are the specific shape that caused #2127.
 *
 * Failure modes return non-zero with a clear remediation. Runs in CI on
 * every PR via v3-ci.yml `wrapper-dep-ranges-audit` job.
 */

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import semver from 'semver';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');

function readPkg(relPath) {
  const p = join(REPO_ROOT, relPath);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch (err) {
    return null;
  }
}

const violations = [];
const checks = [];

// ── 1. sevens wrapper's @claude-flow/cli dep range ────────────────────────────

const sevensPkg = readPkg('sevens/package.json');
const cliPkg = readPkg('v3/@claude-flow/cli/package.json');

if (!sevensPkg) {
  violations.push('sevens/package.json not found');
} else if (!cliPkg) {
  violations.push('v3/@claude-flow/cli/package.json not found');
} else {
  const cliVersion = cliPkg.version;
  const sevensDepRange = sevensPkg.dependencies?.['@claude-flow/cli'];

  if (!sevensDepRange) {
    violations.push(
      `sevens/package.json does not declare @claude-flow/cli — wrapper must depend on the CLI it wraps`
    );
  } else {
    checks.push(`sevens wraps @claude-flow/cli with range "${sevensDepRange}" — cli published as ${cliVersion}`);

    // 1a. Range must include the current cli version
    if (!semver.satisfies(cliVersion, sevensDepRange, { includePrerelease: true })) {
      violations.push(
        `sevens's "@claude-flow/cli": "${sevensDepRange}" does NOT include the cli's actual ` +
        `version ${cliVersion}. Bump the range to "^${cliVersion}" or wider that covers it.`
      );
    }

    // 1b. If the cli is on stable semver (no pre-release), the dep must not be on a pre-release range
    const cliPrerelease = semver.prerelease(cliVersion);
    const rangeUsesPrerelease = /-alpha\.|-beta\.|-rc\.|alpha\.\d+|beta\.\d+|rc\.\d+/.test(sevensDepRange);
    if (!cliPrerelease && rangeUsesPrerelease) {
      violations.push(
        `sevens's "@claude-flow/cli": "${sevensDepRange}" carries a pre-release tag but cli ${cliVersion} ` +
        `is on stable semver. Pre-release ranges widen the dedupe walk and have caused real-world ` +
        `crashes (see #1147 / #2018 / #2127). Replace with a plain caret range like "^${cliVersion}".`
      );
    }
  }
}

// ── 2. root claude-flow umbrella sibling deps ────────────────────────────────

const rootPkg = readPkg('package.json');
const siblingsToCheck = [
  { dep: '@claude-flow/cli-core', workspace: 'v3/@claude-flow/cli-core/package.json' },
  { dep: '@claude-flow/mcp',      workspace: 'v3/@claude-flow/mcp/package.json' },
  { dep: '@claude-flow/neural',   workspace: 'v3/@claude-flow/neural/package.json' },
  { dep: '@claude-flow/shared',   workspace: 'v3/@claude-flow/shared/package.json' },
];

for (const { dep, workspace } of siblingsToCheck) {
  const wsPkg = readPkg(workspace);
  if (!wsPkg) continue; // best-effort — skip if workspace missing
  const range = rootPkg?.dependencies?.[dep];
  if (!range) continue;
  checks.push(`claude-flow umbrella → ${dep}: range "${range}" — workspace at ${wsPkg.version}`);

  if (!semver.satisfies(wsPkg.version, range, { includePrerelease: true })) {
    violations.push(
      `claude-flow's "${dep}": "${range}" does NOT include the workspace's actual ` +
      `version ${wsPkg.version}. Bump the range.`
    );
  }
}

// ── 3. report ────────────────────────────────────────────────────────────────

console.log(`wrapper-dep-ranges audit — scanned ${checks.length} declaration(s)`);
for (const c of checks) console.log(`  ${c}`);

if (violations.length === 0) {
  console.log('  ok: all wrapper ranges include their published target versions');
  console.log('  ok: no pre-release ranges pointing at stable deps');
  process.exit(0);
}

console.error('\nviolations:');
for (const v of violations) console.error(`  ✗ ${v}`);
console.error(`\n${violations.length} violation(s) — see remediation hints above.`);
console.error('Reference: ruvnet/sevens#2127 (Invalid Version dedupe crash).');
process.exit(1);
