#!/usr/bin/env node
/**
 * Print comma-separated sha256 fingerprints of the distinctive lines (40+ characters
 * after normalization) of a local voice profile, for the SSM parameter that
 * check-leaks.mjs reads in CodeBuild:
 *
 *   node scripts/make-voice-fingerprints.mjs agent/voice-profile.md > /tmp/fp.txt
 *   aws ssm put-parameter --name /blog-agent/voice-fingerprints --type SecureString \
 *     --value "file:///tmp/fp.txt" --overwrite
 *
 * Never prints the lines themselves: stdout is only the hash list, stderr only a count.
 * Normalization lives in voice-fingerprint.mjs.
 */
import { readFileSync } from 'node:fs';
import { normalizeLine, fingerprint, MIN_PROFILE_LINE } from './voice-fingerprint.mjs';

const file = process.argv[2] || 'agent/voice-profile.md';
let text;
try {
  text = readFileSync(file, 'utf8');
} catch (err) {
  console.error(`make-voice-fingerprints: cannot read ${file} (${err.code || 'read error'})`);
  process.exit(2);
}

const hashes = new Set();
for (const line of text.split(/\r?\n/)) {
  const n = normalizeLine(line);
  if (n.length >= MIN_PROFILE_LINE) hashes.add(fingerprint(n));
}
if (hashes.size === 0) {
  console.error(`make-voice-fingerprints: no lines of ${MIN_PROFILE_LINE}+ characters in ${file}`);
  process.exit(1);
}
process.stdout.write([...hashes].join(',') + '\n');
console.error(`make-voice-fingerprints: ${hashes.size} fingerprints`);
