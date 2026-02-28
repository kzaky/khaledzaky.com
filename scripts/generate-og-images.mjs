/**
 * Generates per-post OG images (1200x630 JPEG) at build time.
 * Uses sharp to render an SVG template with the post title.
 * Output: public/og/<slug>.jpg
 */
import fs from 'fs';
import path from 'path';
import sharp from 'sharp';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const BLOG_DIR = path.join(ROOT, 'src', 'content', 'blog');
const OUT_DIR = path.join(ROOT, 'public', 'og');

// Brand colors from tailwind.config.mjs
const PRIMARY_600 = '#0284c7';
const GRAY_900 = '#111827';
const GRAY_500 = '#6b7280';

function wrapText(text, maxCharsPerLine) {
  const words = text.split(' ');
  const lines = [];
  let current = '';

  for (const word of words) {
    if (current.length + word.length + 1 > maxCharsPerLine && current.length > 0) {
      lines.push(current);
      current = word;
    } else {
      current = current ? `${current} ${word}` : word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function escapeXml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildSvg(title, author, date) {
  const lines = wrapText(title, 35);
  const lineHeight = 58;
  const titleStartY = lines.length <= 2 ? 260 : 220;

  const titleLines = lines
    .map((line, i) => `<text x="80" y="${titleStartY + i * lineHeight}" font-family="Georgia, Lora, serif" font-size="48" font-weight="700" fill="${GRAY_900}">${escapeXml(line)}</text>`)
    .join('\n    ');

  const metaY = titleStartY + lines.length * lineHeight + 40;

  return `<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
  <rect width="1200" height="630" fill="#ffffff"/>
  <rect x="0" y="0" width="6" height="630" fill="${PRIMARY_600}"/>
  <rect x="0" y="620" width="1200" height="10" fill="${PRIMARY_600}"/>

  <!-- Title -->
  ${titleLines}

  <!-- Author + Date -->
  <text x="80" y="${metaY}" font-family="Inter, system-ui, sans-serif" font-size="22" fill="${GRAY_500}">${escapeXml(author)}</text>
  <text x="80" y="${metaY + 32}" font-family="Inter, system-ui, sans-serif" font-size="18" fill="${GRAY_500}">${escapeXml(date)}</text>

  <!-- Domain -->
  <text x="1120" y="${metaY + 32}" font-family="Inter, system-ui, sans-serif" font-size="18" fill="${PRIMARY_600}" text-anchor="end">khaledzaky.com</text>
</svg>`;
}

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const fm = {};
  for (const line of match[1].split('\n')) {
    const m = line.match(/^(\w+):\s*"?(.+?)"?\s*$/);
    if (m) fm[m[1]] = m[2];
  }
  return fm;
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const files = fs.readdirSync(BLOG_DIR).filter((f) => f.endsWith('.md'));
  let generated = 0;
  let skipped = 0;

  for (const file of files) {
    const slug = file.replace(/\.md$/, '');
    const outPath = path.join(OUT_DIR, `${slug}.jpg`);

    // Skip if already generated (idempotent)
    if (fs.existsSync(outPath)) {
      skipped++;
      continue;
    }

    const content = fs.readFileSync(path.join(BLOG_DIR, file), 'utf-8');
    const fm = parseFrontmatter(content);
    if (!fm || fm.draft === 'true') continue;

    const title = fm.title || slug;
    const author = fm.author || 'Khaled Zaky';
    const date = fm.date
      ? new Date(fm.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      : '';

    const svg = buildSvg(title, author, date);

    await sharp(Buffer.from(svg))
      .jpeg({ quality: 85 })
      .toFile(outPath);

    generated++;
  }

  console.log(`OG images: ${generated} generated, ${skipped} skipped (already exist)`);
}

main().catch((err) => {
  console.error('OG image generation failed:', err);
  process.exit(1);
});
