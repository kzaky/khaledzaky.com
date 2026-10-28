#!/usr/bin/env node
/**
 * Render-shape gate: the last check before a build is allowed to deploy.
 *
 * A fenced article body is valid Markdown, so `astro build` produced the coverage
 * post green while the live page rendered as one <pre><code> block. This script
 * inspects every built blog page in dist/ and fails the build when a page's
 * <article> does not have the shape of a rendered post:
 *
 *   - exactly one <h1> (the layout's title)
 *   - at least two section headings when the article is >= 800 words
 *     (short personal posts legitimately have none)
 *   - no <pre> block holding more than half of the article text
 *   - no review annotation left in the HTML (<!-- CITATION FAIL/NOTE/WARN/REPLACED,
 *     INSIGHT, ENTITY CHECK, STRUCTURE, VOICE --> — comments survive the build)
 *   - no unrendered <!-- CHART: --> / <!-- DIAGRAM: --> placeholder
 *   - no review notes published as sections (a heading named Change Log, Citation
 *     Audit, Remaining Blockers, ... went live on df7a2c6's parent)
 *   - no executable or embedded HTML in the post body: <script>, <iframe>, <form>,
 *     <object>, <embed>, an inline on*= event handler, or a javascript: URL. Scoped
 *     to the rendered Markdown (the layout's <div class="prose"> up to the article
 *     footer), so the site's own layout scripts never trip it
 *   - placeholder hedging in prose ("pending verification", ...) written where a
 *     repair pass dropped a claim is reported as a WARNING only: a hand-written
 *     sentence can use these words, and this script gates every page's deploy. The
 *     pipeline's Notify step still blocks hedging before a draft reaches review.
 *
 * APPENDIX_HEADINGS, HEDGE_PHRASES and RAW_HTML_TAGS mirror agent/common/gate.py, which runs the
 * same rules on the Markdown inside the pipeline; agent/tests/test_gate_rules.py
 * fails if the two lists drift apart. Keep them valid JSON (double quotes).
 *
 * Runs in CI (.github/workflows/ci.yml) and in CodeBuild (buildspec.yml) between
 * `npm run build` and the S3 sync, so a broken post is committed but never served.
 *
 *   node scripts/check-render-shape.mjs [dist-dir]
 */
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const distDir = process.argv[2] || 'dist';
const blogDir = join(distDir, 'blog');
if (!existsSync(blogDir)) {
  console.error(`check-render-shape: ${blogDir} not found — run the build first`);
  process.exit(2);
}

const REVIEW_ANNOTATION = /<!--\s*(?:[^\w\s<>-]+\s*)?(?:CITATION\s+(?:FAIL|WARN|NOTE|REPLACED)|INSIGHT|ENTITY\s+CHECK|STRUCTURE|VOICE)\b/i;
const PLACEHOLDER = /<!--\s*(?:CHART|DIAGRAM):/;
const APPENDIX_HEADINGS = ["change log", "changelog", "citation audit", "remaining blockers", "revision notes", "revision summary", "changes made", "review notes", "reviewer notes"];
const HEDGE_PHRASES = ["pending verification", "unverified pending", "unconfirmed pending", "remain unconfirmed", "remains unconfirmed", "could not be verified against", "cannot be independently verified", "not been independently verified"];
const RAW_HTML_TAGS = ["script", "iframe", "form", "object", "embed"];
const RAW_HTML_TAG = new RegExp(`<\\s*(${RAW_HTML_TAGS.join('|')})\\b`, 'gi');
const EVENT_HANDLER = /<[a-zA-Z][^>]*?\s(on[a-z]+)\s*=/gi;
const JS_URL = /=\s*["']?\s*javascript\s*(?::|&#0*58;|&#x0*3a;|&colon;)/i;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const APPENDIX = new RegExp(`^(?:\\d+[.)]\\s*)?(?:${APPENDIX_HEADINGS.map((h) => escapeRe(h).replace(/ /g, '\\s+')).join('|')})\\b`, 'i');
const HEDGE = new RegExp(HEDGE_PHRASES.map(escapeRe).join('|'), 'i');

function textOf(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const warnings = [];

/** The rendered Markdown inside the article: from the layout's prose wrapper to the
 * article footer (falls back to the whole article if the layout changes shape). */
function postBody(article) {
  const start = article.search(/<div\b[^>]*class="[^"]*\bprose\b/i);
  if (start === -1) return article;
  const end = article.lastIndexOf('<footer');
  return article.slice(start, end > start ? end : undefined);
}

/** Names of the raw-HTML hazards in a fragment of built HTML. */
function rawHtmlHazards(html) {
  const hits = new Set();
  for (const m of html.matchAll(RAW_HTML_TAG)) hits.add(`<${m[1].toLowerCase()}>`);
  for (const m of html.matchAll(EVENT_HANDLER)) hits.add(`${m[1].toLowerCase()}=`);
  if (JS_URL.test(html)) hits.add('javascript: URL');
  return [...hits].sort();
}

function checkPage(slug, html) {
  const errors = [];
  const m = html.match(/<article[\s\S]*?<\/article>/i);
  if (!m) return [`${slug}: no <article> element`];
  const article = m[0];
  const words = textOf(article).split(' ').filter(Boolean).length;

  const h1 = (article.match(/<h1\b/gi) || []).length;
  if (h1 !== 1) errors.push(`${slug}: ${h1} <h1> (expected 1)`);

  const sections = (article.match(/<h[23]\b/gi) || []).length;
  if (words >= 800 && sections < 2) errors.push(`${slug}: ${sections} section headings in a ${words}-word article`);

  let preWords = 0;
  for (const pre of article.match(/<pre[\s\S]*?<\/pre>/gi) || []) preWords += textOf(pre).split(' ').filter(Boolean).length;
  if (words > 0 && preWords / words > 0.5) errors.push(`${slug}: ${Math.round((100 * preWords) / words)}% of the article is inside <pre> — body rendered as code`);

  if (REVIEW_ANNOTATION.test(article)) errors.push(`${slug}: review annotation leaked into the page`);
  if (PLACEHOLDER.test(article)) errors.push(`${slug}: unrendered CHART/DIAGRAM placeholder`);
  const hazards = rawHtmlHazards(postBody(article).replace(/<!--[\s\S]*?-->/g, ' '));
  if (hazards.length) errors.push(`${slug}: executable or embedded HTML in the post body (${hazards.join(', ')})`);

  for (const h of article.match(/<h[1-6]\b[^>]*>[\s\S]*?<\/h[1-6]>/gi) || []) {
    const text = textOf(h);
    if (APPENDIX.test(text)) errors.push(`${slug}: review notes published as a section ("${text.slice(0, 40)}")`);
  }
  const hedge = textOf(article).match(HEDGE);
  if (hedge) warnings.push(`${slug}: placeholder hedging in the prose ("${hedge[0]}")`);
  return errors;
}

const pages = readdirSync(blogDir)
  .filter((name) => name !== 'category' && statSync(join(blogDir, name)).isDirectory())
  .map((name) => [name, join(blogDir, name, 'index.html')])
  .filter(([, p]) => existsSync(p));

const failures = [];
for (const [slug, path] of pages) failures.push(...checkPage(slug, readFileSync(path, 'utf8')));

console.log(`check-render-shape: ${pages.length} blog pages, ${failures.length} problem(s), ${warnings.length} warning(s)`);
for (const f of failures) console.log(`  FAIL ${f}`);
for (const w of warnings) console.log(`  WARN ${w}`);
process.exit(failures.length ? 1 : 0);
