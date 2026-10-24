"""Pie/donut chart renderer."""

import math

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml


def _wrap_title(title, max_chars=42, max_lines=3):
    """Word-wrap title into at most max_lines lines of at most max_chars characters.
    A title longer still ends in an ellipsis; the words used to be dropped silently.
    Returns (lines, truncated)."""
    lines, current = [], ""
    for word in title.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "\u2026"
    return lines, truncated


def title_warnings(title):
    """Review-email warnings for a pie title (empty when it fits in three lines)."""
    if _wrap_title(title)[1]:
        return [f"chart title is {len(title)} characters and was cut to three lines; use a short title, not a sentence"]
    return []


def render_pie_chart(values, title):
    """Render a pie/donut chart as SVG with dark mode support."""
    total = sum(v for _, v in values)
    if total == 0:
        return ""

    chart_width = 400
    radius = 120
    inner_radius = 60  # donut style

    title_lines, _ = _wrap_title(title)
    title_top = 12
    title_line_h = 20
    sep_y = title_top + len(title_lines) * title_line_h + 10
    title_area = sep_y + 12

    cx = chart_width // 2
    cy = title_area + radius + 10

    legend_item_h = 22
    legend_lx = 60
    legend_y_start = cy + radius + 20
    total_height = legend_y_start + len(values) * legend_item_h + 16

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_width} {total_height}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{chart_width}" height="{total_height}" fill="var(--bg)"/>',
    ]

    for i, line in enumerate(title_lines):
        y = title_top + 14 + i * title_line_h
        svg_parts.append(
            f'<text x="{chart_width // 2}" y="{y}" text-anchor="middle" '
            f'fill="var(--text)" font-size="14" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(line)}</text>'
        )
    svg_parts.append(
        f'<line x1="40" y1="{sep_y}" x2="{chart_width - 40}" y2="{sep_y}" '
        f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
    )

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

    for i, (label, val) in enumerate(values):
        pct = (val / total) * 100
        ly = legend_y_start + i * legend_item_h
        color_var = f"var(--c{i % 8})"

        svg_parts.append(
            f'<rect x="{legend_lx}" y="{ly}" width="12" height="12" fill="{color_var}" rx="3"/>'
        )
        svg_parts.append(
            f'<text x="{legend_lx + 20}" y="{ly + 11}" fill="var(--text)" font-size="13" font-weight="600">'
            f'{_escape_xml(label)} <tspan fill="var(--subtext)" font-weight="400">({pct:.0f}%)</tspan></text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
