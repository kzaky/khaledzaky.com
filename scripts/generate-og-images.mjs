/**
 * Generates per-post OG images (1200x630 JPEG) at build time.
 * Style: Dark & Bold — dark navy gradient, dot grid, cyan accents.
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

const ACCENT = '#0ea5e9';

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

function buildDotGrid() {
  const dots = [];
  for (let r = 0; r < 22; r++) {
    for (let c = 0; c < 42; c++) {
      dots.push(`<circle cx="${30 + c * 30}" cy="${30 + r * 30}" r="0.8" fill="#334155"/>`);
    }
  }
  return dots.join('\n  ');
}

function buildCategoryPills(categories) {
  if (!categories || categories.length === 0) return '';
  const cats = categories.slice(0, 3);
  let x = 80;
  return cats.map((cat) => {
    const label = escapeXml(cat.toUpperCase());
    const width = label.length * 9 + 24;
    const pill = `<rect x="${x}" y="86" rx="12" ry="12" width="${width}" height="24" fill="rgba(14,165,233,0.15)"/>
  <text x="${x + width / 2}" y="103" font-family="Inter, system-ui, sans-serif" font-size="11" font-weight="600" fill="${ACCENT}" text-anchor="middle" letter-spacing="0.5">${label}</text>`;
    x += width + 10;
    return pill;
  }).join('\n  ');
}

function buildSvg(title, author, date, categories) {
  const lines = wrapText(title, 32);
  const lineHeight = 62;
  const startY = lines.length <= 2 ? 210 : 180;

  const titleLines = lines
    .map((line, i) => `<text x="80" y="${startY + i * lineHeight}" font-family="Georgia, serif" font-size="52" font-weight="700" fill="#ffffff">${escapeXml(line)}</text>`)
    .join('\n  ');

  const metaY = startY + lines.length * lineHeight + 50;

  return `<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  ${buildDotGrid()}
  <rect x="0" y="0" width="5" height="630" fill="${ACCENT}"/>
  <rect x="0" y="622" width="1200" height="8" fill="${ACCENT}"/>
  ${buildCategoryPills(categories)}
  ${titleLines}
  <text x="80" y="${metaY}" font-family="Inter, system-ui, sans-serif" font-size="22" fill="#94a3b8">${escapeXml(author)}</text>
  <text x="80" y="${metaY + 30}" font-family="Inter, system-ui, sans-serif" font-size="18" fill="#64748b">${escapeXml(date)}</text>
  <text x="1120" y="${metaY + 30}" font-family="Inter, system-ui, sans-serif" font-size="18" fill="${ACCENT}" text-anchor="end">khaledzaky.com</text>
</svg>`;
}

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const fm = {};
  let categories = [];
  for (const line of match[1].split('\n')) {
    const catMatch = line.match(/^categories:\s*\[(.+)\]/);
    if (catMatch) {
      categories = catMatch[1].split(',').map((c) => c.trim().replace(/"/g, ''));
      continue;
    }
    const m = line.match(/^(\w+):\s*"?(.+?)"?\s*$/);
    if (m) fm[m[1]] = m[2];
  }
  fm.categories = categories;
  return fm;
}

async function main() {
  const forceRegen = process.argv.includes('--force');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const files = fs.readdirSync(BLOG_DIR).filter((f) => f.endsWith('.md'));
  let generated = 0;
  let skipped = 0;

  for (const file of files) {
    const slug = file.replace(/\.md$/, '');
    const outPath = path.join(OUT_DIR, `${slug}.jpg`);

    if (fs.existsSync(outPath) && !forceRegen) {
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

    const svg = buildSvg(title, author, date, fm.categories);

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
