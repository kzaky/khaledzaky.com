"""Pie/donut chart renderer."""

import math

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml


def render_pie_chart(values, title):
    """Render a pie/donut chart as SVG with dark mode support."""
    total = sum(v for _, v in values)
    if total == 0:
        return ""

    chart_size = 400
    cx, cy = chart_size // 2, chart_size // 2 + 20
    radius = 120
    inner_radius = 60  # donut style

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_size} {chart_size + 80}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{chart_size}" height="{chart_size + 80}" fill="var(--bg)"/>',
        f'<text x="{chart_size // 2}" y="32" text-anchor="middle" '
        f'fill="var(--text)" font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
        f'{_escape_xml(title)}</text>',
        f'<line x1="40" y1="44" x2="{chart_size - 40}" y2="44" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>',
    ]

    start_angle = -90  # Start from top

    for i, (_label, val) in enumerate(values):
        pct = val / total
        end_angle = start_angle + pct * 360
        color_var = f"var(--c{i % 8})"

        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        x1 = cx + radius * math.cos(start_rad)
        y1 = cy + radius * math.sin(start_rad)
        x2 = cx + radius * math.cos(end_rad)
        y2 = cy + radius * math.sin(end_rad)

        ix1 = cx + inner_radius * math.cos(end_rad)
        iy1 = cy + inner_radius * math.sin(end_rad)
        ix2 = cx + inner_radius * math.cos(start_rad)
        iy2 = cy + inner_radius * math.sin(start_rad)

        large_arc = 1 if pct > 0.5 else 0

        path = (
            f"M {x1:.1f} {y1:.1f} "
            f"A {radius} {radius} 0 {large_arc} 1 {x2:.1f} {y2:.1f} "
            f"L {ix1:.1f} {iy1:.1f} "
            f"A {inner_radius} {inner_radius} 0 {large_arc} 0 {ix2:.1f} {iy2:.1f} Z"
        )

        svg_parts.append(f'<path d="{path}" fill="{color_var}"/>')
        start_angle = end_angle

    legend_y = cy + radius + 30
    for i, (label, val) in enumerate(values):
        pct = (val / total) * 100
        lx = 40 + (i % 2) * (chart_size // 2)
        ly = legend_y + (i // 2) * 22
        color_var = f"var(--c{i % 8})"

        svg_parts.append(f'<rect x="{lx}" y="{ly - 9}" width="12" height="12" fill="{color_var}" rx="3"/>')
        svg_parts.append(
            f'<text x="{lx + 20}" y="{ly}" fill="var(--text)" font-size="13" font-weight="600">'
            f'{_escape_xml(label)} <tspan fill="var(--subtext)" font-weight="400">({pct:.0f}%)</tspan></text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
