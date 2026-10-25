#!/usr/bin/env node
/**
 * Visual layout gate for charts and posts. Runs in CI after `npm run build`.
 *
 * Two checks a text diff cannot see, both of which shipped and were fixed by hand:
 *
 *   1. SVG text overflow (public/postimages/charts/*.svg). Each figure is rendered in
 *      headless Chromium and every <text> is measured with getBBox():
 *        - text outside the viewBox (e3e0151: a stage subtitle clipped by the canvas);
 *        - text spilling out of the smallest rect that contains its centre.
 *   2. Phone layout (dist/blog/*): every built post is loaded at 375px and must not
 *      scroll sideways (tables with long tokens did, on every post that had one), and
 *      no ordinary word may be split across lines. A CSS fix for the first
 *      (overflow-wrap: anywhere on table cells) squeezed columns until words broke
 *      mid-letter ("AI MS sta tus"); the page no longer scrolled, so only this second
 *      rule sees it. Code, paths, URLs and hyphenated words may still break.
 *   3. Scoped styles: every rule in a figure's <style> must target that figure's own
 *      root class (svg.kzc-... / .dark svg.kzc-...). The post layout inlines every SVG
 *      into one page, so a :root rule in one figure recoloured all the others.
 *   4. Missing images: every local image a built post references must exist in dist/
 *      (the-evaluation-stack-... pointed at a diagram that was never generated, and
 *      readers saw a broken-image icon for months).
 *
 * Defects that predate this gate are listed in scripts/check-svg-baseline.json and
 * reported but not failed; anything new fails. Refresh the baseline only on purpose:
 *   node scripts/check-svg.mjs --update-baseline
 *
 * Fonts: figures are measured with the site's own Inter and Lora files (the post
 * layout inlines SVGs, so readers see them in those fonts), which also keeps the
 * result identical on any machine instead of depending on its fallback fonts.
 *
 *   node scripts/check-svg.mjs [--update-baseline] [--skip-pages]
 *   CHECK_SVG_DIR=some/dir node scripts/check-svg.mjs --skip-pages   # check other SVGs
 */
import { readdirSync, readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { join, extname } from 'node:path';
import { chromium } from 'playwright';

// CHECK_SVG_DIR points the figure pass at another folder (e.g. freshly rendered charts).
const CHARTS = process.env.CHECK_SVG_DIR || 'public/postimages/charts';
const DIST = 'dist';
const BASELINE = 'scripts/check-svg-baseline.json';
const PHONE_WIDTH = 375;
const args = new Set(process.argv.slice(2));

const FONT_FILES = [
  ['Inter Variable', 'normal', '@fontsource-variable/inter/files/inter-latin-wght-normal.woff2'],
  ['Inter Variable', 'italic', '@fontsource-variable/inter/files/inter-latin-wght-italic.woff2'],
  ['Lora Variable', 'normal', '@fontsource-variable/lora/files/lora-latin-wght-normal.woff2'],
  ['Lora Variable', 'italic', '@fontsource-variable/lora/files/lora-latin-wght-italic.woff2'],
];
const FONT_FACES = FONT_FILES.map(([family, style, file]) => {
  const data = readFileSync(join('node_modules', file)).toString('base64');
  return `@font-face{font-family:'${family}';font-style:${style};font-weight:100 900;src:url(data:font/woff2;base64,${data}) format('woff2');}`;
}).join('');

function launch() {
  // Cloud sessions ship a Chromium outside Playwright's cache; CI installs its own.
  const exe = process.env.CHECK_SVG_CHROMIUM;
  return chromium.launch(exe ? { executablePath: exe } : {});
}

async function checkSvgs(browser) {
  const page = await browser.newPage();
  const files = readdirSync(CHARTS).filter((f) => f.endsWith('.svg')).sort();
  const issues = [];
  for (const file of files) {
    const svg = readFileSync(join(CHARTS, file), 'utf8');
    const cls = (svg.match(/^\s*<svg\b[^>]*\bclass="([^"]*\bkzc-[0-9a-f]+)/) || [])[1]?.match(/kzc-[0-9a-f]+/)[0];
    for (const [, css] of svg.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) {
      for (const [, sel] of css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{/g)) {
        const ok = cls && sel.split(',').every((x) => new RegExp(`^\\s*(\\.dark\\s+)?svg\\.${cls}\\b`).test(x));
        if (!ok) issues.push({ file, kind: 'style', text: `unscoped selector "${sel.trim().slice(0, 40)}"`, key: `${file} :: style :: ${sel.trim()}` });
      }
    }
    await page.setContent(`<!doctype html><html><head><style>${FONT_FACES}</style></head><body style="margin:0">${svg}</body></html>`);
    await page.evaluate(async () => {
      await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
      await document.fonts.ready;
    });
    const found = await page.evaluate(() => {
      const s = document.querySelector('svg');
      if (!s || !s.viewBox || !s.viewBox.baseVal) return [{ kind: 'canvas', text: '(no svg viewBox)' }];
      const vb = s.viewBox.baseVal;
      const out = [];
      const boxes = [...s.querySelectorAll('rect')].map((r) => r.getBBox())
        .filter((b) => b.width < vb.width - 1 || b.height < vb.height - 1);
      for (const t of s.querySelectorAll('text')) {
        const b = t.getBBox();
        const text = t.textContent.trim().replace(/\s+/g, ' ').slice(0, 60);
        if (!text) continue;
        if (b.x < vb.x - 1 || b.x + b.width > vb.x + vb.width + 1 || b.y < vb.y - 1 || b.y + b.height > vb.y + vb.height + 1) {
          out.push({ kind: 'canvas', text });
          continue;
        }
        const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
        const box = boxes.filter((r) => cx > r.x && cx < r.x + r.width && cy > r.y && cy < r.y + r.height)
          .sort((a, c) => a.width * a.height - c.width * c.height)[0];
        if (box && (b.x < box.x + 1 || b.x + b.width > box.x + box.width - 1)) out.push({ kind: 'box', text });
      }
      return out;
    });
    for (const f of found) issues.push({ file, ...f, key: `${file} :: ${f.kind} :: ${f.text}` });
  }
  await page.close();
  return { count: files.length, issues };
}

function serve(root) {
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.xml': 'application/xml' };
  const server = createServer((req, res) => {
    let p = join(root, decodeURIComponent(req.url.split('?')[0]));
    if (existsSync(p) && statSync(p).isDirectory()) p = join(p, 'index.html');
    if (!existsSync(p)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': types[extname(p)] || 'application/octet-stream' });
    res.end(readFileSync(p));
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function checkPages(browser) {
  const blog = join(DIST, 'blog');
  if (!existsSync(blog)) throw new Error(`${blog} not found; run npm run build first`);
  const slugs = readdirSync(blog).filter((d) => existsSync(join(blog, d, 'index.html')) && d !== 'category');
  const server = await serve(DIST);
  const base = `http://127.0.0.1:${server.address().port}`;
  const page = await browser.newPage({ viewport: { width: PHONE_WIDTH, height: 800 } });
  const wide = [], split = [], missing = [];
  for (const slug of slugs.sort()) {
    const html = readFileSync(join(blog, slug, 'index.html'), 'utf8');
    for (const [, src] of html.matchAll(/<img[^>]+src="(\/[^"#?]+)"/g)) {
      if (!existsSync(join(DIST, decodeURIComponent(src)))) missing.push({ slug, src });
    }
    await page.goto(`${base}/blog/${slug}/`, { waitUntil: 'load' });
    const r = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const sw = document.documentElement.scrollWidth;
      if (sw <= vw) return null;
      const leaf = [...document.querySelectorAll('body *')]
        .find((e) => e.getBoundingClientRect().right > vw + 1 && ![...e.children].some((c) => c.getBoundingClientRect().right > vw + 1));
      return { sw, vw, culprit: leaf ? `<${leaf.tagName.toLowerCase()}> ${leaf.textContent.trim().slice(0, 50)}` : '' };
    });
    if (r) wide.push({ slug, ...r });
    const words = await page.evaluate(() => {
      const out = [];
      const walker = document.createTreeWalker(document.querySelector('article') || document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (n.parentElement.closest('code, pre, svg, script, style')) continue;
        for (const m of n.textContent.matchAll(/[A-Za-z\u00C0-\u024F']{4,}/g)) {
          // Only whole words: a letter run glued to '-', '/', '.' or a digit is part of a
          // token (path, URL, version) that may legitimately break.
          const before = n.textContent[m.index - 1] || ' ', after = n.textContent[m.index + m[0].length] || ' ';
          if (/[-\/.\w]/.test(before) || /[-\/\w]/.test(after)) continue;
          const range = document.createRange();
          range.setStart(n, m.index);
          range.setEnd(n, m.index + m[0].length);
          const tops = new Set([...range.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top)));
          if (tops.size > 1) out.push(m[0]);
        }
      }
      return out;
    });
    if (words.length) split.push({ slug, words });
  }
  await page.close();
  server.close();
  return { count: slugs.length, wide, split, missing };
}

const browser = await launch();
let failed = false;
try {
  const svg = await checkSvgs(browser);
  const pages = args.has('--skip-pages') ? null : await checkPages(browser);
  if (args.has('--update-baseline')) {
    writeFileSync(BASELINE, JSON.stringify({
      _doc: 'Defects present when scripts/check-svg.mjs was introduced (or deliberately accepted since). They are reported, not failed; anything not listed fails CI. Remove an entry when its figure is fixed.',
      svg: svg.issues.map((i) => i.key).sort(),
      wide_pages: pages ? pages.wide.map((w) => w.slug).sort() : [],
    }, null, 2) + '\n');
    console.log(`check-svg: baseline written`);
  }
  // The baseline describes the published figures; another folder is checked against none.
  const base = existsSync(BASELINE) && !process.env.CHECK_SVG_DIR ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { svg: [], wide_pages: [] };
  const knownSvg = new Set(base.svg), knownWide = new Set(base.wide_pages);

  const fresh = svg.issues.filter((i) => !knownSvg.has(i.key));
  const staleSvg = [...knownSvg].filter((k) => !svg.issues.some((i) => i.key === k));
  console.log(`check-svg: ${svg.count} SVGs, ${fresh.length} new problem(s), ${svg.issues.length - fresh.length} known (baseline)`);
  for (const e of fresh) console.log(`  ${{ canvas: 'OUTSIDE CANVAS', box: 'OUTSIDE BOX   ', style: 'UNSCOPED STYLE' }[e.kind]} ${e.file}: "${e.text}"`);
  for (const k of staleSvg) console.log(`  note: fixed, remove from baseline: ${k}`);
  if (fresh.length) failed = true;

  if (pages) {
    const freshWide = pages.wide.filter((w) => !knownWide.has(w.slug));
    console.log(`check-svg: ${pages.count} posts at ${PHONE_WIDTH}px, ${freshWide.length} new sideways scroll(s), ${pages.wide.length - freshWide.length} known (baseline)`);
    for (const w of freshWide) console.log(`  WIDE ${w.slug}: ${w.sw}px > ${w.vw}px ${w.culprit}`);
    for (const k of [...knownWide].filter((k) => !pages.wide.some((w) => w.slug === k))) console.log(`  note: fixed, remove from baseline: ${k}`);
    if (freshWide.length) failed = true;
    console.log(`check-svg: ${pages.count} posts at ${PHONE_WIDTH}px, ${pages.split.length} with words split mid-word`);
    for (const w of pages.split) console.log(`  SPLIT ${w.slug}: ${w.words.slice(0, 6).join(', ')}${w.words.length > 6 ? ` (+${w.words.length - 6})` : ''}`);
    if (pages.split.length) failed = true;
    console.log(`check-svg: ${pages.count} posts, ${pages.missing.length} missing image(s)`);
    for (const m of pages.missing) console.log(`  MISSING ${m.slug}: ${m.src}`);
    if (pages.missing.length) failed = true;
  }
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
