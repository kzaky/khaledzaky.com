"""Horizontal bar chart renderer."""

import textwrap
from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml


def render_bar_chart(values, title):
    """Render a horizontal bar chart as SVG with dark mode support."""
    max_val = max(v for _, v in values)
    num_bars = len(values)

    # Dimensions
    margin_left = 160
    margin_right = 60
    margin_top = 60
    margin_bottom = 30
    bar_height = 36
    bar_gap = 12
    chart_height = margin_top + (bar_height + bar_gap) * num_bars + margin_bottom
    chart_width = 600
    bar_area_width = chart_width - margin_left - margin_right

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_width} {chart_height}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{chart_width}" height="{chart_height}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{chart_width // 2}" y="35" text-anchor="middle" '
        f'fill="var(--text)" font-size="15" font-weight="600">'
        f'{_escape_xml(textwrap.shorten(title, width=70))}</text>',
    ]

    for i, (label, val) in enumerate(values):
        y = margin_top + i * (bar_height + bar_gap)
        bar_width = (val / max_val) * bar_area_width if max_val > 0 else 0
        color_var = f"var(--c{i % 8})"

        svg_parts.append(
            f'<text x="{margin_left - 10}" y="{y + bar_height // 2 + 5}" '
            f'text-anchor="end" fill="var(--text)" font-size="12">'
            f'{_escape_xml(textwrap.shorten(label, width=20))}</text>'
        )

        svg_parts.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_width:.1f}" '
            f'height="{bar_height}" fill="{color_var}" rx="4"/>'
        )

        display_val = f"{val:.0f}" if val == int(val) else f"{val:.1f}"
        svg_parts.append(
            f'<text x="{margin_left + bar_width + 8}" y="{y + bar_height // 2 + 5}" '
            f'fill="var(--text)" font-size="12" font-weight="600">{display_val}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
