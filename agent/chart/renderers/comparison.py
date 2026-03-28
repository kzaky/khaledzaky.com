"""Two-column comparison diagram renderer."""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml, _text_lines


def render_comparison_diagram(fields):
    """Render a two-column comparison diagram with dark mode support.
    fields: [left_header, right_header, row1_left:row1_right, ...]
    """
    if len(fields) < 3:
        return None

    left_header = fields[0]
    right_header = fields[1]
    rows = []

    if len(fields) == 3 and ";" in fields[2] and ":" not in fields[2]:
        # Format: 'left_header | right_header | left1;left2 | right1;right2' collapsed into two fields
        # Actually: 'left_header | right_header | item1;item2;...' — zip left and right semicolon lists
        lefts = [x.strip() for x in fields[2].split(";") if x.strip()]
        rights = lefts  # single column fallback — use same values
        rows = [(item, item) for item in lefts]
    elif len(fields) >= 4 and ";" in fields[2]:
        # Format: 'left_header | right_header | left1;left2;left3 | right1;right2;right3'
        lefts = [x.strip() for x in fields[2].split(";") if x.strip()]
        rights = [x.strip() for x in fields[3].split(";") if x.strip()]
        rows = list(zip(lefts, rights, strict=False))
    else:
        # Original format: 'left_header | right_header | left:right | left:right | ...'
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

    title_str = f"{left_header} vs {right_header}"
    title_lines = _text_lines(title_str, w - 60, 14)
    title_block_h = 16 if len(title_lines) == 1 else 34
    top = 50 + title_block_h  # push content down if title wraps

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h + (title_block_h - 16)}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h + (title_block_h - 16)}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
    ]
    if len(title_lines) == 1:
        svg.append(f'<text x="{w//2}" y="30" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="700">{_escape_xml(title_lines[0])}</text>')
    else:
        svg.append(f'<text x="{w//2}" y="22" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="700">{_escape_xml(title_lines[0])}</text>')
        svg.append(f'<text x="{w//2}" y="40" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="700">{_escape_xml(title_lines[1])}</text>')
    svg += [
        # Headers
        f'<rect x="30" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c0)" rx="6"/>',
        f'<text x="{30 + col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-primary)" font-size="12" font-weight="600">{_escape_xml(left_header)}</text>',
        f'<rect x="{w - 30 - col_w}" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c1)" rx="6"/>',
        f'<text x="{w - 30 - col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-primary)" font-size="12" font-weight="600">{_escape_xml(right_header)}</text>',
        f'<text x="{w//2}" y="{top + 16}" text-anchor="middle" fill="var(--muted)" font-size="16">\u2192</text>',
    ]

    y = top + header_h + gap
    for left, right in rows:
        left_lines = _text_lines(left, col_w - 14, 11)
        right_lines = _text_lines(right, col_w - 14, 11)
        svg.append(f'<rect x="30" y="{y}" width="{col_w}" height="{row_h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        if len(left_lines) == 1:
            svg.append(f'<text x="{30 + col_w//2}" y="{y + row_h//2 + 4}" text-anchor="middle" fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(left_lines[0])}</text>')
        else:
            svg.append(f'<text x="{30 + col_w//2}" y="{y + row_h//2 - 3}" text-anchor="middle" fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(left_lines[0])}</text>')
            svg.append(f'<text x="{30 + col_w//2}" y="{y + row_h//2 + 11}" text-anchor="middle" fill="var(--subtext)" font-size="10">{_escape_xml(left_lines[1])}</text>')
        svg.append(f'<rect x="{w - 30 - col_w}" y="{y}" width="{col_w}" height="{row_h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        if len(right_lines) == 1:
            svg.append(f'<text x="{w - 30 - col_w//2}" y="{y + row_h//2 + 4}" text-anchor="middle" fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(right_lines[0])}</text>')
        else:
            svg.append(f'<text x="{w - 30 - col_w//2}" y="{y + row_h//2 - 3}" text-anchor="middle" fill="var(--text)" font-size="11" font-weight="600">{_escape_xml(right_lines[0])}</text>')
            svg.append(f'<text x="{w - 30 - col_w//2}" y="{y + row_h//2 + 11}" text-anchor="middle" fill="var(--subtext)" font-size="10">{_escape_xml(right_lines[1])}</text>')
        svg.append(f'<text x="{w//2}" y="{y + row_h//2 + 4}" text-anchor="middle" fill="var(--muted)" font-size="14">\u2192</text>')
        y += row_h + gap

    svg.append("</svg>")
    return "\n".join(svg)
