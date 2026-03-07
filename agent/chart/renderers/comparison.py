"""Two-column comparison diagram renderer."""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


def render_comparison_diagram(fields):
    """Render a two-column comparison diagram with dark mode support.
    fields: [left_header, right_header, row1_left:row1_right, ...]
    """
    if len(fields) < 3:
        return None

    left_header = fields[0]
    right_header = fields[1]
    rows = []
    for f in fields[2:]:
        if ":" in f:
            left, right = f.split(":", 1)
            rows.append((left.strip(), right.strip()))

    if not rows:
        return None

    row_h = 48
    gap = 10
    header_h = 32
    top = 70
    w = 700
    col_w = 300
    total_h = top + header_h + gap + (row_h + gap) * len(rows) + 20

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{w//2}" y="35" text-anchor="middle" fill="var(--text)" font-size="16" font-weight="700">{_escape_xml(left_header)} vs {_escape_xml(right_header)}</text>',
        # Headers
        f'<rect x="30" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c0)" rx="6"/>',
        f'<text x="{30 + col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-primary)" font-size="13" font-weight="600">{_escape_xml(left_header)}</text>',
        f'<rect x="{w - 30 - col_w}" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c1)" rx="6"/>',
        f'<text x="{w - 30 - col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-primary)" font-size="13" font-weight="600">{_escape_xml(right_header)}</text>',
        f'<text x="{w//2}" y="{top + 16}" text-anchor="middle" fill="var(--muted)" font-size="16">\u2192</text>',
    ]

    y = top + header_h + gap
    for left, right in rows:
        svg.append(f'<rect x="30" y="{y}" width="{col_w}" height="{row_h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        svg.append(f'<text x="{30 + col_w//2}" y="{y + row_h//2 + 5}" text-anchor="middle" fill="var(--text)" font-size="12" font-weight="600">{_escape_xml(left)}</text>')
        svg.append(f'<rect x="{w - 30 - col_w}" y="{y}" width="{col_w}" height="{row_h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        svg.append(f'<text x="{w - 30 - col_w//2}" y="{y + row_h//2 + 5}" text-anchor="middle" fill="var(--text)" font-size="12" font-weight="600">{_escape_xml(right)}</text>')
        svg.append(f'<text x="{w//2}" y="{y + row_h//2 + 5}" text-anchor="middle" fill="var(--muted)" font-size="14">\u2192</text>')
        y += row_h + gap

    svg.append("</svg>")
    return "\n".join(svg)
