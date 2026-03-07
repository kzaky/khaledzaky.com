"""Convergence diagram renderer — items flowing into a central block."""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


def render_convergence_diagram(fields):
    """Render items converging into a central block with dark mode support.
    fields: [center_label, item1;detail, item2;detail, ...]
    """
    if len(fields) < 2:
        return None

    center_label = fields[0]
    items = []
    for f in fields[1:]:
        parts = [p.strip() for p in f.split(";")]
        name = parts[0] if parts else ""
        detail = parts[1] if len(parts) > 1 else ""
        items.append((name, detail))

    if not items:
        return None

    w = 700
    item_w = 200
    item_h = 38
    gap = 12
    n = len(items)
    left_count = (n + 1) // 2
    right_count = n - left_count
    col_height = max(left_count, right_count) * (item_h + gap)
    center_y = 80 + col_height
    total_h = center_y + 90

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{w//2}" y="35" text-anchor="middle" fill="var(--text)" font-size="16" font-weight="700">{_escape_xml(center_label)}</text>',
    ]

    # Left column items
    for i in range(left_count):
        name, detail = items[i]
        x = 40
        y = 70 + i * (item_h + gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{item_w}" height="{item_h}" fill="var(--item-bg)" rx="6" stroke="var(--c0)" stroke-width="1.5"/>')
        svg.append(f'<text x="{x + item_w//2}" y="{y + 16}" text-anchor="middle" fill="var(--c0)" font-size="11" font-weight="600">{_escape_xml(name)}</text>')
        if detail:
            svg.append(f'<text x="{x + item_w//2}" y="{y + 30}" text-anchor="middle" fill="var(--subtext)" font-size="8">{_escape_xml(detail)}</text>')
        # Dashed line to center
        svg.append(f'<line x1="{x + item_w}" y1="{y + item_h//2}" x2="{w//2 - 100}" y2="{center_y}" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4,3"/>')

    # Right column items
    for i in range(right_count):
        name, detail = items[left_count + i]
        x = w - 40 - item_w
        y = 70 + i * (item_h + gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{item_w}" height="{item_h}" fill="var(--item-bg)" rx="6" stroke="var(--c0)" stroke-width="1.5"/>')
        svg.append(f'<text x="{x + item_w//2}" y="{y + 16}" text-anchor="middle" fill="var(--c0)" font-size="11" font-weight="600">{_escape_xml(name)}</text>')
        if detail:
            svg.append(f'<text x="{x + item_w//2}" y="{y + 30}" text-anchor="middle" fill="var(--subtext)" font-size="8">{_escape_xml(detail)}</text>')
        svg.append(f'<line x1="{x}" y1="{y + item_h//2}" x2="{w//2 + 100}" y2="{center_y}" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4,3"/>')

    # Center target
    svg.append(f'<rect x="{w//2 - 100}" y="{center_y - 25}" width="200" height="50" fill="var(--c0)" rx="8"/>')
    svg.append(f'<text x="{w//2}" y="{center_y + 5}" text-anchor="middle" fill="var(--on-primary)" font-size="13" font-weight="700">{_escape_xml(center_label)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)
