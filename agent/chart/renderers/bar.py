"""Horizontal bar chart renderer — editorial style."""

import textwrap

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml


def _title_lines(title, max_chars=52):
    """Split a title into at most 2 lines without truncation."""
    if len(title) <= max_chars:
        return [title]
    mid = len(title) // 2
    split = title.rfind(" ", 0, mid + 20)
    if split == -1:
        split = mid
    return [title[:split].strip(), title[split:].strip()]


def render_bar_chart(values, title):
    """Render a horizontal bar chart as SVG — editorial style.

    Design principles:
    - Lora serif title, left-aligned with thin accent rule beneath
    - Tall bars (48px), single brand-blue color for all bars
    - Oversized bold value labels dominate the data story
    - No border box — chart sits cleanly on the page
    """
    max_val = max(v for _, v in values)
    num_bars = len(values)

    margin_left = 185
    margin_right = 90
    bar_height = 48
    bar_gap = 16
    title_area = 74
    bottom_margin = 24
    chart_height = title_area + num_bars * (bar_height + bar_gap) + bottom_margin
    chart_width = 700
    bar_area_width = chart_width - margin_left - margin_right

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_width} {chart_height}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{chart_width}" height="{chart_height}" fill="var(--bg)"/>',
    ]

    title_parts = _title_lines(title)
    if len(title_parts) == 1:
        svg_parts.append(
            f'<text x="30" y="30" text-anchor="start" fill="var(--text)" '
            f'font-size="20" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(title_parts[0])}</text>'
        )
        svg_parts.append(
            f'<line x1="30" y1="44" x2="{chart_width - 30}" y2="44" '
            f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
        )
    else:
        svg_parts.append(
            f'<text x="30" y="24" text-anchor="start" fill="var(--text)" '
            f'font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(title_parts[0])}</text>'
        )
        svg_parts.append(
            f'<text x="30" y="46" text-anchor="start" fill="var(--text)" '
            f'font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(title_parts[1])}</text>'
        )
        svg_parts.append(
            f'<line x1="30" y1="58" x2="{chart_width - 30}" y2="58" '
            f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
        )

    for i, (label, val) in enumerate(values):
        y = title_area + i * (bar_height + bar_gap)
        bar_width = (val / max_val) * bar_area_width if max_val > 0 else 0

        svg_parts.append(
            f'<text x="{margin_left - 14}" y="{y + bar_height // 2 + 5}" '
            f'text-anchor="end" fill="var(--subtext)" font-size="12">'
            f'{_escape_xml(textwrap.shorten(label, width=38))}</text>'
        )

        svg_parts.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_width:.1f}" '
            f'height="{bar_height}" fill="var(--c0)" rx="3"/>'
        )

        display_val = f"{val:.0f}" if val == int(val) else f"{val:.1f}"
        svg_parts.append(
            f'<text x="{margin_left + bar_width + 12}" y="{y + bar_height // 2 + 7}" '
            f'fill="var(--text)" font-size="18" font-weight="800" font-family="{FONT_FAMILY}">'
            f'{_escape_xml(display_val)}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
