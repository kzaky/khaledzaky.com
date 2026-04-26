"""Horizontal timeline diagram renderer.

Spec format:
  timeline | Title | Label;detail | Label;detail | ...

Renders a left-to-right timeline with dots on a center line.
Labels alternate above/below to prevent crowding.
Supports up to 7 items cleanly.
"""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _text_lines

_MAX_ITEMS = 7


def render_timeline_diagram(fields):
    """Render a horizontal timeline with alternating above/below label pairs."""
    if len(fields) < 2:
        return None

    title = fields[0]
    items = []
    for f in fields[1:_MAX_ITEMS + 1]:
        parts = [p.strip() for p in f.split(";")]
        label = parts[0] if parts else ""
        detail = parts[1] if len(parts) > 1 else ""
        if label:
            items.append((label, detail))

    if not items:
        return None

    n = len(items)
    W = 700
    PAD = 55
    LINE_Y = 150
    TICK = 22
    DOT_R = 6
    TOTAL_H = 270
    CX = W // 2

    xs = [W // 2] if n == 1 else [PAD + i * (W - 2 * PAD) // (n - 1) for i in range(n)]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {TOTAL_H}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{W}" height="{TOTAL_H}" fill="var(--bg)"/>',
        f'<text x="{CX}" y="28" text-anchor="middle" fill="var(--text)" font-size="20" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title)}</text>',
        f'<line x1="30" y1="40" x2="{W - 30}" y2="40" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>',
        # Main timeline line
        f'<line x1="{PAD - 12}" y1="{LINE_Y}" x2="{W - PAD + 12}" y2="{LINE_Y}" stroke="var(--muted)" stroke-width="2"/>',
        # Arrow tip on right
        f'<polygon points="{W - PAD + 12},{LINE_Y} {W - PAD + 4},{LINE_Y - 4} {W - PAD + 4},{LINE_Y + 4}" fill="var(--muted)"/>',
    ]

    for i, (label, detail) in enumerate(items):
        x = xs[i]
        above = (i % 2 == 0)
        is_endpoint = (i == 0 or i == n - 1)

        # Dot — endpoints solid, middle dots are rings
        if is_endpoint:
            svg.append(f'<circle cx="{x}" cy="{LINE_Y}" r="{DOT_R + 1}" fill="var(--c0)"><title>{_escape_xml(label)}</title></circle>')
        else:
            svg.append(f'<circle cx="{x}" cy="{LINE_Y}" r="{DOT_R}" fill="var(--muted)"><title>{_escape_xml(label)}</title></circle>')
            svg.append(f'<circle cx="{x}" cy="{LINE_Y}" r="{DOT_R - 3}" fill="var(--bg)"/>')

        label_lines = _text_lines(label, 110, 11)
        has_detail = bool(detail)

        if above:
            tick_y2 = LINE_Y - DOT_R - TICK
            svg.append(f'<line x1="{x}" y1="{LINE_Y - DOT_R}" x2="{x}" y2="{tick_y2}" stroke="var(--muted)" stroke-width="1"/>')

            if len(label_lines) == 1:
                label_y = tick_y2 - (14 if has_detail else 7)
            else:
                label_y = tick_y2 - (26 if has_detail else 20)

            for j, line in enumerate(label_lines):
                svg.append(
                    f'<text x="{x}" y="{label_y + j * 13}" text-anchor="middle" '
                    f'fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(line)}</text>'
                )
            if has_detail:
                detail_y = label_y + len(label_lines) * 13
                svg.append(
                    f'<text x="{x}" y="{detail_y}" text-anchor="middle" '
                    f'fill="var(--subtext)" font-size="9.5">{_escape_xml(detail)}</text>'
                )
        else:
            tick_y2 = LINE_Y + DOT_R + TICK
            svg.append(f'<line x1="{x}" y1="{LINE_Y + DOT_R}" x2="{x}" y2="{tick_y2}" stroke="var(--muted)" stroke-width="1"/>')

            label_y = tick_y2 + 14
            for j, line in enumerate(label_lines):
                svg.append(
                    f'<text x="{x}" y="{label_y + j * 13}" text-anchor="middle" '
                    f'fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(line)}</text>'
                )
            if has_detail:
                detail_y = label_y + len(label_lines) * 13
                svg.append(
                    f'<text x="{x}" y="{detail_y}" text-anchor="middle" '
                    f'fill="var(--subtext)" font-size="9.5">{_escape_xml(detail)}</text>'
                )

    svg.append("</svg>")
    return "\n".join(svg)
