# Site Audit Report — khaledzaky.com

**Date:** 2026-04-02
**Scope:** Full-stack audit — frontend, content, infrastructure, CI/CD, agent pipeline

---

## Critical

| # | Area | Issue | Location |
|---|------|-------|----------|
| 1 | CI/CD | `buildspec.yml` runs `s3 sync --delete` with no validation that `dist/` is complete. An incomplete build will **delete the live site**. | `buildspec.yml:31-34` |
| 2 | Infrastructure | CSP header includes `script-src 'unsafe-inline'` — opens XSS vector. Should whitelist specific origins instead. | `infra/template.yaml:65` |
| 3 | Agent | Bedrock client configured with `max_attempts: 1` — zero retries on transient errors (502/503/504). | `agent/research/index.py:44` |
| 4 | CI/CD | `npm audit` failure is silently swallowed with `\|\| echo "..."` — pipeline passes with known vulnerabilities. | `.github/workflows/ci.yml:24`, `buildspec.yml:21` |
| 5 | Infrastructure | IAM permissions grant `s3:PutObject/GetObject/DeleteObject` on `/*` — too broad, should be scoped to `dist/*`. | `infra/template.yaml:201-215` |

---

## High

| # | Area | Issue | Location |
|---|------|-------|----------|
| 6 | Content | Empty description field — missing meta tags for SEO/social sharing. | `src/content/blog/operational-excellence-ten-dives-into-a-production-personal-site.md:6` |
| 7 | Content | 3 posts have truncated descriptions ending in `"..."` — cut off mid-word in meta tags. | `agent-observability-...md:6`, `evaluations-...md:6`, `the-ietf-...md:6` |
| 8 | Content | Markdown formatting (`**TL;DR:**`) in frontmatter description — renders literally in meta tags. | `src/content/blog/evaluations-the-control-plane-for-ai-governance.md:6` |
| 9 | Agent | `verify/index.py` URL regex fails on parentheses in URLs (e.g. Wikipedia links). | `agent/verify/index.py:178` |
| 10 | Agent | `_MAX_FETCH_BYTES = 8192` is too small — most articles are >8KB, truncating content extraction. | `agent/verify/index.py:35` |
| 11 | Agent | `get_tavily_api_key()` has no caching — re-fetches from SSM on every invocation (+100-200ms). | `agent/research/index.py:89-96` |
| 12 | Infrastructure | `TreatMissingData: breaching` on CloudWatch alarm — fires when CloudWatch itself is down, creating noise. | `infra/template.yaml:313` |

---

## Medium

| # | Area | Issue | Location |
|---|------|-------|----------|
| 13 | SEO | Blog posts missing `og:article:published_time` and `og:article:modified_time` meta tags. | `src/layouts/BlogPost.astro:39-49` |
| 14 | UX | Mermaid diagram CDN import has no error handling — if CDN fails, diagrams silently break. | `src/layouts/BlogPost.astro:162-185` |
| 15 | UX | Mobile menu doesn't close when a nav link is clicked. | `src/components/Header.astro:126-137` |
| 16 | A11y | Footer social icons use `text-gray-400` on white — contrast ratio ~3.2:1, below WCAG AA 4.5:1. | `src/components/Footer.astro:20` |
| 17 | A11y | Mobile menu toggle missing `aria-controls` attribute linking to menu element. | `src/components/Header.astro:67-79` |
| 18 | Scripts | OG image generator frontmatter regex fails on Windows line endings (CRLF). | `scripts/generate-og-images.mjs:93` |
| 19 | Scripts | Draft check `fm.draft === 'true'` is string comparison — YAML booleans may be actual booleans. | `scripts/generate-og-images.mjs:129` |
| 20 | Content | 3 post descriptions missing trailing period (inconsistent punctuation). | `building-an-automated-...md`, `delegation-...md`, `from-periodic-reviews-...md` |
| 21 | Agent | `_smoke_test_thinking()` runs synchronously on every cold start — adds 1-2s latency. | `agent/research/index.py:56-86` |
| 22 | Agent | Verify quality calculation doesn't exclude UNREACHABLE links, inflating denominator. | `agent/notify/index.py:82` |
| 23 | Styles | Hardcoded RGB values (`rgb(55 65 81)`) instead of Tailwind theme tokens. | `src/styles/global.css:62` |
| 24 | Dependencies | 11 npm audit vulnerabilities (1 low, 7 moderate, 3 high) in `yaml` → `@astrojs/check` chain. | `package.json` devDeps |

---

## Low

| # | Area | Issue | Location |
|---|------|-------|----------|
| 25 | A11y | Header theme toggle uses `text-gray-500` — borderline WCAG AA (4.54:1 vs 4.5:1 required). | `src/components/Header.astro:41` |
| 26 | SEO | No breadcrumb structured data on blog posts. | `src/pages/blog/[...slug].astro` |
| 27 | A11y | Footer social links in generic `<div>` instead of `<nav aria-label="Social links">`. | `src/components/Footer.astro:2-7` |
| 28 | Performance | Google Analytics inline script runs before external gtag library loads (minor race condition). | `src/layouts/BaseLayout.astro:76-82` |
| 29 | Infrastructure | CloudFront invalidation always invalidates `/*` — wastes invalidation quota on minor changes. | `buildspec.yml:38` |
| 30 | Agent | Publish retry max backoff is only 4s — too short for GitHub outages. | `agent/publish/index.py:62` |

---

## Verified OK

These areas were checked and found to be in good shape:

- **Astro build**: 52 pages built successfully, no compile errors
- **OG images**: 36 generated for 36 posts — all accounted for
- **Agent tests**: 49/49 pass (Python 3.11)
- **Ruff lint**: All checks pass
- **Dark mode**: Proper flash prevention, localStorage persistence, system preference detection
- **Skip-to-content**: Keyboard navigation link present
- **SVG sanitization**: XSS protection when inlining external SVGs
- **External link security**: All external links use `rel="noopener noreferrer"`
- **RSS feed**: Filters drafts, sanitizes HTML, includes full content
- **Structured data**: JSON-LD for WebSite, Person, and Article schemas
- **OG/Twitter cards**: Comprehensive implementation across all pages
- **404 page**: Custom design with `noindex` directive
- **S3 bucket security**: All public access blocked, OAC configured
- **Content schema**: Well-defined Zod schema, all frontmatter compliant
- **Routing**: All dynamic routes generate correctly
- **Sitemap**: Properly configured with `@astrojs/sitemap`

---

## Fix Plan

### Phase 1 — Critical (security & data loss prevention)
1. Add `dist/index.html` existence check before `s3 sync --delete` in `buildspec.yml`
2. Replace `'unsafe-inline'` in CSP with explicit origin whitelist in `infra/template.yaml`
3. Increase Bedrock `max_attempts` to 3 in `agent/research/index.py`
4. Remove `|| echo` from `npm audit` in CI so failures block the build
5. Scope IAM S3 permissions to the deployment prefix

### Phase 2 — High (content & agent reliability)
6. Fix empty/truncated/markdown-in-description across 7 blog posts
7. Fix URL regex in `agent/verify/index.py` to handle parentheses
8. Increase `_MAX_FETCH_BYTES` to 32768 in `agent/verify/index.py`
9. Add SSM caching for `get_tavily_api_key()` in `agent/research/index.py`
10. Change `TreatMissingData` to `notBreaching` in `infra/template.yaml`

### Phase 3 — Medium (SEO, UX, a11y, resilience)
11. Add `og:article:published_time` / `modified_time` to `BlogPost.astro`
12. Add try-catch around Mermaid CDN import with fallback message
13. Close mobile menu on nav link click
14. Bump footer icon color from `text-gray-400` to `text-gray-500`
15. Add `aria-controls="mobile-menu"` to menu toggle button
16. Fix OG script frontmatter regex for CRLF and boolean draft check
17. Fix 3 missing periods in post descriptions
18. Add Tavily key caching, fix quality denominator, use Tailwind tokens in CSS
19. Address npm audit vulnerabilities

### Phase 4 — Low (polish)
20. Bump header toggle to `text-gray-600` for better contrast
21. Add breadcrumb structured data to blog posts
22. Wrap footer social links in `<nav>`
23. Reorder analytics script (external before inline)
24. Selective CloudFront invalidation
25. Increase publish retry backoff
