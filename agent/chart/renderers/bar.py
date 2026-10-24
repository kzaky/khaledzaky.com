"""Horizontal bar chart renderer — editorial style."""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _text_lines


def _title_lines(title, max_chars=52):
    """Split a title into at most 2 lines without truncation."""
    if len(title) <= max_chars:
        return [title]
    mid = len(title) // 2
    split = title.rfind(" ", 0, mid + 20)
    if split == -1:
        split = mid
    return [title[:split].strip(), title[split:].strip()]


# Lora 18 bold averages ~10px a character; 60 characters is the most a line can hold
# inside the 640px title band. The old two-way split let lines run to ~75 characters,
# which is how sentence-length titles were clipped by the canvas edge (22 overflows in
# 16 published figures, since re-rendered). Four lines hold 240 characters,
# more than any title the pipeline has published (the longest is 188).
_TITLE_LINE_MAX = 60
_TITLE_MAX_LINES = 4


def _wrapped_title(title):
    """Greedy wrap to _TITLE_LINE_MAX, at most _TITLE_MAX_LINES; the last line is cut
    with an ellipsis when the title is longer still. Returns (lines, truncated)."""
    lines, current = [], ""
    for word in title.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= _TITLE_LINE_MAX or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    truncated = len(lines) > _TITLE_MAX_LINES
    if truncated:
        lines = lines[:_TITLE_MAX_LINES]
        lines[-1] = lines[-1][: _TITLE_LINE_MAX - 1].rstrip() + "\u2026"
    return lines, truncated


def title_warnings(title):
    """Review-email warnings for a chart title (empty when the title fits)."""
    parts = _title_lines(title)
    if all(len(p) <= _TITLE_LINE_MAX for p in parts):
        return []
    lines, truncated = _wrapped_title(title)
    if truncated:
        return [f"chart title is {len(title)} characters and was cut to {_TITLE_MAX_LINES} lines; use a short title, not a sentence"]
    return [f"chart title is {len(title)} characters and wraps to {len(lines)} lines; a short title reads better"]


def render_bar_chart(values, title):
    """Render a horizontal bar chart as SVG — editorial style.

    Design principles:
    - Lora serif title, left-aligned with thin accent rule beneath
    - Tall bars (48px), single brand-blue color for all bars
    - Oversized bold value labels dominate the data story
    - No border box — chart sits cleanly on the page

    values: [(label, number)] or [(label, number, display)]. The default formatter
    rounds to one decimal, which silently misreports small magnitudes such as a
    $0.0384 unit cost, so a caller may supply the exact label to print.
    """
    values = [(v[0], v[1], v[2] if len(v) > 2 else None) for v in values]
    max_val = max(v for _, v, _ in values)
    num_bars = len(values)

    margin_left = 220
    margin_right = 90
    bar_height = 48
    bar_gap = 16
    title_area = 74

    # Titles the original two-line layout fits render exactly as before; only a title
    # with a line it would overflow takes the wrapped layout (one more 22px line).
    title_parts = _title_lines(title)
    wrapped = any(len(p) > _TITLE_LINE_MAX for p in title_parts)
    if wrapped:
        title_parts, _ = _wrapped_title(title)
        title_area = 74 + 22 * max(len(title_parts) - 2, 0)
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

    if wrapped:
        for n, part in enumerate(title_parts):
            svg_parts.append(
                f'<text x="30" y="{24 + 22 * n}" text-anchor="start" fill="var(--text)" '
                f'font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
                f'{_escape_xml(part)}</text>'
            )
        rule_y = 24 + 22 * (len(title_parts) - 1) + 12
        svg_parts.append(
            f'<line x1="30" y1="{rule_y}" x2="{chart_width - 30}" y2="{rule_y}" '
            f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
        )
    elif len(title_parts) == 1:
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

    for i, (label, val, explicit) in enumerate(values):
        y = title_area + i * (bar_height + bar_gap)
        bar_width = (val / max_val) * bar_area_width if max_val > 0 else 0

        label_lines = _text_lines(label, margin_left - 44, font_size=11)
        if len(label_lines) == 1:
            svg_parts.append(
                f'<text x="{margin_left - 14}" y="{y + bar_height // 2 + 5}" '
                f'text-anchor="end" fill="var(--subtext)" font-size="11">'
                f'{_escape_xml(label_lines[0])}</text>'
            )
        else:
            svg_parts.append(
                f'<text x="{margin_left - 14}" y="{y + bar_height // 2 - 3}" '
                f'text-anchor="end" fill="var(--subtext)" font-size="11">'
                f'{_escape_xml(label_lines[0])}</text>'
            )
            svg_parts.append(
                f'<text x="{margin_left - 14}" y="{y + bar_height // 2 + 12}" '
                f'text-anchor="end" fill="var(--subtext)" font-size="11">'
                f'{_escape_xml(label_lines[1])}</text>'
            )

        svg_parts.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_width:.1f}" '
            f'height="{bar_height}" fill="var(--c0)" rx="3"/>'
        )

        display_val = explicit if explicit else (f"{val:.0f}" if val == int(val) else f"{val:.1f}")
        svg_parts.append(
            f'<text x="{margin_left + bar_width + 12}" y="{y + bar_height // 2 + 7}" '
            f'fill="var(--text)" font-size="18" font-weight="800" font-family="{FONT_FAMILY}">'
            f'{_escape_xml(display_val)}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
