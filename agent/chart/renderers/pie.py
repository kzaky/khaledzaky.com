"""Pie/donut chart renderer."""

import math
import textwrap

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


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
        f'<rect width="{chart_size}" height="{chart_size + 80}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{chart_size // 2}" y="35" text-anchor="middle" '
        f'fill="var(--text)" font-size="15" font-weight="600">'
        f'{_escape_xml(textwrap.shorten(title, width=50))}</text>',
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

        svg_parts.append(f'<rect x="{lx}" y="{ly - 8}" width="10" height="10" fill="{color_var}" rx="2"/>')
        svg_parts.append(
            f'<text x="{lx + 16}" y="{ly}" fill="var(--text)" font-size="11">'
            f'{_escape_xml(label)} ({pct:.0f}%)</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
