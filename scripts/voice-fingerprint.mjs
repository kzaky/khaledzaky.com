/**
 * Shared line normalization for voice-profile fingerprints.
 *
 * make-voice-fingerprints.mjs hashes lines of the private profile with this, and
 * check-leaks.mjs hashes lines of the built site with it, so both sides must agree.
 * A line is: HTML tags removed, common entities decoded, curly quotes straightened,
 * leading Markdown markers (#, >, -, *, +, "1.") removed, emphasis/code markers
 * (*, `) removed, whitespace collapsed, trimmed and lowercased. The fingerprint is
 * the sha256 hex of that string.
 */
import { createHash } from 'node:crypto';

export const MIN_PROFILE_LINE = 40;

const ENTITIES = {
  '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'",
  '&#x27;': "'", '&apos;': "'", '&nbsp;': ' ', '&rsquo;': "'", '&lsquo;': "'",
  '&ldquo;': '"', '&rdquo;': '"',
};

export function normalizeLine(line) {
  let s = String(line)
    .replace(/<[^>]*>/g, ' ')
    .replace(/&(?:amp|lt|gt|quot|#39|#x27|apos|nbsp|rsquo|lsquo|ldquo|rdquo);/g, (e) => ENTITIES[e])
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, ' ')
    .trim();
  let prev;
  do {
    prev = s;
    s = s.replace(/^(?:#{1,6}|>|[-*+]|\d+[.)])\s+/, '');
  } while (s !== prev);
  return s.replace(/[*`]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
}

export function fingerprint(normalized) {
  return createHash('sha256').update(normalized, 'utf8').digest('hex');
}
