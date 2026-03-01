"""Venn diagram renderer — 2-3 overlapping circles."""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


def render_venn_diagram(fields):
    """Render 2-3 overlapping circles with dark mode support.
    fields: [title, circle1_label;trait1;trait2, circle2_label;trait1;trait2, ...]
    """
    if len(fields) < 2:
        return None

    title = fields[0]
    circles = []
    for f in fields[1:4]:  # max 3 circles
        parts = [p.strip() for p in f.split(";")]
        name = parts[0] if parts else ""
        traits = parts[1:] if len(parts) > 1 else []
        circles.append((name, traits))

    n = len(circles)
    w = 600
    total_h = 380
    cy = 185
    r = 85
    circle_color_vars = ["var(--c0)", "var(--c1)", "var(--c2)"] if n == 3 else ["var(--c0)", "var(--c2)"]

    # Positions: spread circles based on count
    if n == 3:
        positions = [(185, cy), (w // 2, cy), (415, cy)]
        text_offsets = [(-30, 0), (0, 0), (30, 0)]  # offset text away from center
    elif n == 2:
        positions = [(220, cy), (380, cy)]
        text_offsets = [(-20, 0), (20, 0)]
    else:
        positions = [(w // 2, cy)]
        text_offsets = [(0, 0)]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{w//2}" y="35" text-anchor="middle" fill="var(--text)" font-size="16" font-weight="700">{_escape_xml(title)}</text>',
    ]

    for i, ((name, traits), (cx, cy_pos), (tx, ty)) in enumerate(zip(circles, positions, text_offsets)):
        color_var = circle_color_vars[i % len(circle_color_vars)]
        svg.append(f'<circle cx="{cx}" cy="{cy_pos}" r="{r}" fill="{color_var}" opacity="0.1" stroke="{color_var}" stroke-width="2"/>')
        text_x = cx + tx
        svg.append(f'<text x="{text_x}" y="{cy_pos - 10}" text-anchor="middle" fill="{color_var}" font-size="14" font-weight="700">{_escape_xml(name)}</text>')
        for j, trait in enumerate(traits[:3]):
            svg.append(f'<text x="{text_x}" y="{cy_pos + 8 + j * 14}" text-anchor="middle" fill="var(--subtext)" font-size="9">{_escape_xml(trait)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)
