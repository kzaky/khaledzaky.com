"""Layered stack diagram renderer."""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _text_lines


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
    layer_h = 54  # increased from 44 to accommodate two-line detail text
    gap = 4
    top_margin = 75
    title_lines = _text_lines(title, w - 60, 20)
    title_block_h = 16 if len(title_lines) == 1 else 34
    top_margin = 55 + title_block_h
    total_h = top_margin + len(layers) * (layer_h + gap) + 20

    # Deepening shades of primary blue
    blue_shades = ["#0284c7", "#0369a1", "#075985", "#0c4a6e", "#082f49", "#051e34", "#031525"]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)"/>',
    ]
    if len(title_lines) == 1:
        svg.append(f'<text x="{w//2}" y="34" text-anchor="middle" fill="var(--text)" font-size="20" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[0])}</text>')
        svg.append(f'<line x1="30" y1="46" x2="{w - 30}" y2="46" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>')
    else:
        svg.append(f'<text x="{w//2}" y="24" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[0])}</text>')
        svg.append(f'<text x="{w//2}" y="44" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[1])}</text>')
        svg.append(f'<line x1="30" y1="56" x2="{w - 30}" y2="56" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>')

    for i, (name, detail) in enumerate(layers):
        y = top_margin + i * (layer_h + gap)
        shade = blue_shades[min(i, len(blue_shades) - 1)]
        svg.append(f'<rect x="60" y="{y}" width="480" height="{layer_h}" fill="{shade}" rx="6"/>')
        svg.append(f'<text x="80" y="{y + 30}" fill="var(--on-primary)" font-size="12" font-weight="700">{i + 1}</text>')
        if detail:
            svg.append(f'<text x="{w//2}" y="{y + 20}" text-anchor="middle" fill="var(--on-primary)" font-size="12" font-weight="600">{_escape_xml(name)}</text>')
            detail_lines = _text_lines(detail, 460, 9)
            if len(detail_lines) == 1:
                svg.append(f'<text x="{w//2}" y="{y + 37}" text-anchor="middle" fill="var(--detail)" font-size="9">{_escape_xml(detail_lines[0])}</text>')
            else:
                svg.append(f'<text x="{w//2}" y="{y + 33}" text-anchor="middle" fill="var(--detail)" font-size="9"><tspan x="{w//2}" dy="0">{_escape_xml(detail_lines[0])}</tspan><tspan x="{w//2}" dy="11">{_escape_xml(detail_lines[1])}</tspan></text>')
        else:
            svg.append(f'<text x="{w//2}" y="{y + 30}" text-anchor="middle" fill="var(--on-primary)" font-size="12" font-weight="600">{_escape_xml(name)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)
