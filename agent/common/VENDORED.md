# Vendored third-party packages

`gate.py` needs to know what the site's Markdown processor will render, so it uses a real
CommonMark parser instead of regexes. Lambda packages carry no dependencies, so the parser
ships here, unmodified, and `.common-deps` copies it into each package that vendors `gate.py`.

| Package | Version | Licence | Wheel sha256 (checked against PyPI) |
|---|---|---|---|
| markdown-it-py | 4.2.0 | MIT | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` |
| mdurl | 0.1.2 | MIT | `84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8` |

Each package keeps its wheel's `RECORD`, and `test_vendored_packages_are_unmodified` checks
every file against it. To update: `pip download --no-deps` the wheel, compare its hash with
PyPI, unzip the package and copy `RECORD` and the licences in, then update this table. Run
`scripts/render-h1-count.mjs` over `agent/tests/fixtures/h1_render_cases.json` to confirm the
counts still match the renderer.
