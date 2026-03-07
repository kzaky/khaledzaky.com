"""Layered stack diagram renderer."""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


def render_stack_diagram(fields):
    """Render layered horizontal bars (top to bottom) with dark mode support.
    fields: [title, layer1_name;detail, layer2_name;detail, ...]
    """
    if len(fields) < 2:
        return None

    title = fields[0]
    layers = []
    for f in fields[1:]:
        parts = [p.strip() for p in f.split(";")]
        name = parts[0] if parts else ""
        detail = parts[1] if len(parts) > 1 else ""
        layers.append((name, detail))

    if not layers:
        return None

    w = 600
    layer_h = 44
    gap = 4
    top_margin = 75
    total_h = top_margin + len(layers) * (layer_h + gap) + 20

    # Deepening shades of primary blue
    blue_shades = ["#0284c7", "#0369a1", "#075985", "#0c4a6e", "#082f49", "#051e34", "#031525"]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{w//2}" y="35" text-anchor="middle" fill="var(--text)" font-size="16" font-weight="700">{_escape_xml(title)}</text>',
    ]

    for i, (name, detail) in enumerate(layers):
        y = top_margin + i * (layer_h + gap)
        shade = blue_shades[min(i, len(blue_shades) - 1)]
        svg.append(f'<rect x="60" y="{y}" width="480" height="{layer_h}" fill="{shade}" rx="6"/>')
        svg.append(f'<text x="80" y="{y + 27}" fill="var(--on-primary)" font-size="12" font-weight="700">{i + 1}</text>')
        svg.append(f'<text x="{w//2}" y="{y + 20}" text-anchor="middle" fill="var(--on-primary)" font-size="12" font-weight="600">{_escape_xml(name)}</text>')
        if detail:
            svg.append(f'<text x="{w//2}" y="{y + 35}" text-anchor="middle" fill="var(--detail)" font-size="9">{_escape_xml(detail)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)
