# khaledzaky.com

Astro site (src/) plus the AI blog agent (agent/, AWS Lambdas + Step Functions). README.md
covers architecture; this file covers how to change things here without breaking them.

## Deploying

- **Site:** push to `master`. CodeBuild runs `npm ci`, `npm run build` and
  `npm run check:render`, then syncs to S3 and invalidates CloudFront. A failed
  check:render stops the deploy for every page, not just the broken one.
- **Agent Lambdas:** not deployed by a push. Run `agent/scripts/deploy-lambda.sh <fn>`
  (needs AWS credentials; it packages, deploys and smoke-imports). Changes to
  `agent/common/gate.py` reach draft, evaluate and notify only when those are redeployed.
- The author wants changes taken all the way to `master` unless they say otherwise.

## Checks to run before pushing (CI runs the same)

```bash
python3 -m pytest agent/tests/ -q            # needs: pip install ruff pytest pyyaml cfn-lint
ruff check agent/ --config agent/ruff.toml
cfn-lint agent/template.yaml
python3 agent/evals/run_gate.py              # oracle: 0 gate errors on every published post
npx astro check && npm run build
npm run check:render                         # built-HTML gate (also runs in CodeBuild)
npm run check:svg                            # figure overflow; at 375px: sideways scroll, words split mid-word (CI only)
```

After editing a remark/rehype plugin in `src/plugins/`, delete `node_modules/.astro` before
building: Astro caches rendered Markdown and only invalidates it when `astro.config.mjs`
changes, so a local build otherwise checks the old HTML (CI and CodeBuild build clean).

CI's Python job does not install boto3; tests that import a Lambda must not need it at
import time beyond what the handlers already stub.

## Editing a published post

- Edit the Markdown in `src/content/blog/` directly. Do **not** run the blog agent or its
  review pipeline on an approved post.
- Every hand fix to a post the pipeline published becomes an eval case in the same
  commit: add it to `agent/evals/manifest.json`, run `python3 agent/evals/build_cases.py`,
  set `gate_detectable`/`expect` from what the gate actually reports, and update the
  pinned counts in `agent/tests/test_evals.py`.
- Never leave review notes in a post: no "Change Log", "Citation Audit", "Remaining
  Blockers" sections, no `<!-- CITATION ... -->` comments, no "pending verification"
  prose. The pipeline gate blocks all of these. check:render (the deploy gate) fails on
  review-note headings and comments, and only warns on hedging phrases so a sentence
  you write by hand can never stop the whole site deploying.

## Author conventions

- TL;DR first: 24 of the 25 posts that have one open with it (as `## TL;DR`,
  `**TL;DR:**`, or a `> **TL;DR:**` blockquote; the blockquote is the current style).
  The gate warns (`tldr_late`) when it sits more than 10% into the post.
- Canadian spelling: -ize/-ization, -our (behaviour, favour).
- No em or en dashes anywhere, including frontmatter `description`.
- First person and contractions are the author's current voice. The 18 pre-agent posts
  (dated before 2026-02-21) are the calibration set for voice rules; a new rule must not
  fire on them (see `agent/tests/test_gate_rules.py`).
- End on plain prose, not an italic aphorism or a restated summary.
- `.devin/workflows/post-review.md` is the author's own pre-publish checklist.

## Figures

- Site brand: one primary blue (sky `#0284c7`, `#38bdf8` in dark) on gray, Lora for
  titles and numerals, Inter for text, hairline gray borders, and the blockquote motif
  (pale blue tint + 4px blue bar) for the one thing a figure emphasizes. No rainbow
  palettes, outlined pill chips, letter-spaced caps or corner badges.
- Hand-made SVGs in `public/postimages/charts/` are inlined into the page by
  `BlogPost.astro`, so their `<style>` lands in the document: prefix custom CSS
  variables (e.g. `--kz-*`) and define both `:root` and `.dark svg` values.
- Agent-rendered charts use the brand palette by default (`CHART_STYLE=classic` brings
  back the older eight-hue set). Every brand text/fill pairing meets WCAG AA in light and
  dark; `test_brand_text_meets_wcag_aa_in_both_modes` fails if a token change breaks that.
  Text drawn on a `--c0`/`--c1` fill uses `--on-accent`, which turns navy in dark mode.
- Check new or edited figures with `npm run check:svg` (or
  `CHECK_SVG_DIR=dir node scripts/check-svg.mjs --skip-pages`). Its baseline
  (`scripts/check-svg-baseline.json`) is empty: every published figure passes. Never add
  an entry to silence a figure; fix the figure.
- To fix a published agent chart, recover its data from the SVG and re-render it with the
  current renderer in `agent/chart/renderers/`; check that every label and value
  survives, and never draw numbers the post or its source does not support.

## Gate rules live in two places

`agent/common/gate.py` (Markdown, in the pipeline and the eval harness) and
`scripts/check-render-shape.mjs` (built HTML, before deploy) share `APPENDIX_HEADINGS`
and `HEDGE_PHRASES`; `test_gate_rules.py` fails if they drift. New error rules must
produce zero errors on all published posts (`run_gate.py` oracle) before they ship.
