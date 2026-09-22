"""Conceptual framework card renderer.

Spec format (pipe-delimited):
  framework | Title | Term;Question | Term;Question | ...

Renders unordered rows: a labelled term on the left, its question on the right.

The existing renderers all imply an ordering or an opposition that a framework does
not have — progression and stack number their rows and deepen the shade top to bottom,
and comparison frames the two columns as 'A vs B'. A set of named checks is neither
sequential nor adversarial, so rows here are visually equal: no numbering, no shade
ramp, no arrows. Styling otherwise matches the other renderers (Lora serif title with
an accent rule, Inter body text, rounded var(--card) rows, CSS variables for dark mode).
"""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _wrap_text


def render_framework_diagram(fields):
    """Render a framework as equal-weight term/question rows."""
    if len(fields) < 2:
        return None

    title = fields[0]
    rows = []
    for f in fields[1:]:
        parts = [p.strip() for p in f.split(";")]
        term = parts[0] if parts else ""
        detail = parts[1] if len(parts) > 1 else ""
        if term:
            rows.append((term, detail))

    if not rows:
        return None

    w = 700
    row_h = 52
    gap = 8
    col_gap = 26
    term_w = 170
    pad = 30

    title_lines = _wrap_text(title, w - 2 * pad, 20, max_lines=2)
    rule_y = 30 + (len(title_lines) - 1) * 22 + 12
    top = rule_y + 26
    total_h = top + len(rows) * (row_h + gap) + 14

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)"/>',
    ]
    for i, line in enumerate(title_lines):
        fs = 20 if len(title_lines) == 1 else 18
        svg.append(
            f'<text x="{pad}" y="{30 + i * 22}" text-anchor="start" fill="var(--text)" '
            f'font-size="{fs}" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(line)}</text>'
        )
    svg.append(
        f'<line x1="{pad}" y1="{rule_y}" x2="{w - pad}" y2="{rule_y}" '
        f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
    )

    detail_w = w - 2 * pad - term_w - col_gap
    for i, (term, detail) in enumerate(rows):
        y = top + i * (row_h + gap)
        # Term cell uses the same solid brand fill as comparison.py's headers. Every row
        # gets the identical colour, so the set stays unordered.
        svg.append(
            f'<rect x="{pad}" y="{y}" width="{term_w}" height="{row_h}" fill="var(--c0)" rx="6"/>'
        )
        svg.append(
            f'<text x="{pad + term_w // 2}" y="{y + row_h // 2 + 4}" text-anchor="middle" '
            f'fill="var(--on-primary)" font-size="13" font-weight="700">{_escape_xml(term)}</text>'
        )

        svg.append(
            f'<rect x="{pad + term_w + col_gap}" y="{y}" width="{detail_w}" height="{row_h}" '
            f'fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{pad + term_w + col_gap // 2}" y="{y + row_h // 2 + 5}" '
            f'text-anchor="middle" fill="var(--muted)" font-size="14">\u2192</text>'
        )
        lines = _wrap_text(detail, detail_w - 24, 12, max_lines=2)
        if len(lines) == 1:
            svg.append(
                f'<text x="{pad + term_w + col_gap + 14}" y="{y + row_h // 2 + 4}" '
                f'text-anchor="start" fill="var(--text)" font-size="12">'
                f'{_escape_xml(lines[0])}</text>'
            )
        else:
            svg.append(
                f'<text x="{pad + term_w + col_gap + 14}" y="{y + row_h // 2 - 3}" '
                f'text-anchor="start" fill="var(--text)" font-size="12">'
                f'{_escape_xml(lines[0])}</text>'
            )
            svg.append(
                f'<text x="{pad + term_w + col_gap + 14}" y="{y + row_h // 2 + 12}" '
                f'text-anchor="start" fill="var(--text)" font-size="12">'
                f'{_escape_xml(lines[1])}</text>'
            )

    svg.append("</svg>")
    return "\n".join(svg)
