#!/usr/bin/env node
/**
 * Privacy-leak gate, run after `npm run build` (CI and CodeBuild). Exits 1 when:
 *
 *   (a) any built file in dist/ other than the /drop page itself (sitemaps, rss.xml,
 *       other pages) links to /drop, the private upload page;
 *   (b) any git-tracked path is a voice profile (*voice-profile*) other than
 *       voice-profile.sample.md. The real profile is private and gitignored;
 *   (c) VOICE_FINGERPRINTS is set (comma-separated sha256 of normalized profile
 *       lines, from make-voice-fingerprints.mjs) and a normalized line of any
 *       dist/ .html, .xml or .txt file matches one. Skipped with a note when unset.
 *
 * Matching lines are reported by file and line number only, never their text.
 *
 *   node scripts/check-leaks.mjs [dist-dir]
 */
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, relative, sep, basename } from 'node:path';
import { execFileSync } from 'node:child_process';
import { normalizeLine, fingerprint } from './voice-fingerprint.mjs';

const distDir = process.argv[2] || 'dist';
if (!existsSync(join(distDir, 'index.html'))) {
  console.error(`check-leaks: ${distDir}/index.html not found — run the build first`);
  process.exit(2);
}

const failures = [];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

const relOf = (f) => relative(distDir, f).split(sep).join('/');
const files = walk(distDir).filter((f) => /\.(html|xml|txt)$/i.test(f));

// (a) links to /drop: absolute URLs to the site, and root-relative href/src/action.
const DROP_ABS = /(?:https?:)?\/\/(?:www\.)?khaledzaky\.com\/drop(?=[/?#"'<\s]|$)/i;
const DROP_REL = /\b(?:href|src|action|formaction)\s*=\s*["']?\/drop(?=[/?#"'\s>]|$)/i;
let scannedA = 0;
for (const f of files) {
  const rel = relOf(f);
  // The page itself is allowed; robots.txt names /drop in a Disallow rule, not a link.
  if (rel === 'drop.html' || rel.startsWith('drop/') || rel === 'robots.txt') continue;
  scannedA++;
  readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
    if (DROP_ABS.test(line) || DROP_REL.test(line)) {
      failures.push(`(a) ${rel}:${i + 1} links to /drop`);
    }
  });
}
console.log(`check-leaks (a): ${scannedA} files scanned for links to /drop`);

// (b) tracked voice-profile files.
let tracked = null;
try {
  tracked = execFileSync('git', ['ls-files', '-z'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  })
    .split('\0')
    .filter(Boolean);
} catch {
  console.log('check-leaks (b): skipped, not a git checkout (git ls-files failed)');
}
if (tracked) {
  for (const p of tracked) {
    const b = basename(p).toLowerCase();
    if (b.includes('voice-profile') && b !== 'voice-profile.sample.md') {
      failures.push(`(b) tracked private voice profile: ${p}`);
    }
  }
  console.log(`check-leaks (b): ${tracked.length} tracked paths checked`);
}

// (c) voice fingerprints. The AWS CLI prints "None" for an empty value.
const raw = (process.env.VOICE_FINGERPRINTS || '').trim();
if (!raw || raw === 'None') {
  console.log('check-leaks (c): skipped, VOICE_FINGERPRINTS is not set');
} else {
  const wanted = new Set(
    raw
      .split(',')
      .map((h) => h.trim().toLowerCase())
      .filter((h) => /^[0-9a-f]{64}$/.test(h)),
  );
  if (wanted.size === 0) {
    failures.push('(c) VOICE_FINGERPRINTS is set but holds no valid sha256 hex values');
  }
  let lineCount = 0;
  for (const f of files) {
    const rel = relOf(f);
    readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
      const n = normalizeLine(line);
      if (!n) return;
      lineCount++;
      if (wanted.has(fingerprint(n))) {
        failures.push(`(c) ${rel}:${i + 1} matches a voice-profile fingerprint`);
      }
    });
  }
  console.log(
    `check-leaks (c): ${lineCount} lines in ${files.length} files checked against ${wanted.size} fingerprints`,
  );
}

if (failures.length) {
  console.error(`\ncheck-leaks: FAILED (${failures.length})`);
  for (const f of failures) console.error(`  ${f}`);
  process.exit(1);
}
console.log('check-leaks: OK');
