"""Ascending staircase progression diagram renderer."""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _wrap_text, scope_svg


def render_progression_diagram(fields):
    """Render ascending staircase stages with dark mode support.
    fields: [title, stage1_name;detail1;detail2, stage2_name;detail1, ..., "axis: label"]

    The axis under the stairs is labelled only when a field says what it measures
    ("axis: Increasing disruption"). It used to read "Increasing platform maturity" on
    every figure, including a failure taxonomy and a pen-test methodology.
    """
    if len(fields) < 2:
        return None

    title = fields[0]
    axis = next((f.split(":", 1)[1].strip() for f in fields[1:] if f.strip().lower().startswith("axis:")), "")
    stages = []
    for f in fields[1:]:
        if f.strip().lower().startswith("axis:"):
            continue
        parts = [p.strip() for p in f.split(";")]
        name = parts[0] if parts else ""
        details = parts[1:] if len(parts) > 1 else []
        stages.append((name, details))

    if not stages:
        return None

    n = len(stages)
    w = 700
    # Boxes shrink to fit the stage count with a 12px gap: at a fixed 140px, five or
    # more stages overlapped and each box covered the next one's text.
    stage_w = min(140, int((w - 40 - (n - 1) * 12) / n))
    inner_w = stage_w - 8
    # Each stage is 70px taller than the one before; the first is tall enough that no
    # stage has to drop a detail line (narrower boxes wrap details onto more lines).
    wrapped = [(_wrap_text(name, inner_w, font_size=11, max_lines=3),
                [ln for d in details[:3] for ln in _wrap_text(d, inner_w, font_size=8, max_lines=6)])
               for name, details in stages]
    need = [54 + 13 * (len(nl) - 1) + 12 * len(dl) for nl, dl in wrapped]
    base_h = max([70] + [need[i] - i * 70 for i in range(n)])
    max_h = base_h + (n - 1) * 70
    top_margin = 70
    bottom_margin = 40
    total_h = top_margin + max_h + bottom_margin
    gap = (w - 40 - n * stage_w) / max(n - 1, 1) if n > 1 else 0

    # Stage fill colors — CSS variables so dark mode overrides them correctly.
    # Light mode: light→medium blues. Dark mode: dark blues (see theme.py --s1–--s4).
    stage_vars = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)"/>',
        f'<text x="{w//2}" y="34" text-anchor="middle" fill="var(--text)" font-size="20" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title)}</text>',
        f'<line x1="30" y1="46" x2="{w - 30}" y2="46" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>',
    ]

    for i in range(n):
        x = 40 + i * (stage_w + gap)
        h = base_h + i * 70
        y = top_margin + (max_h - h)
        is_last = (i == n - 1)
        fill = "var(--s4)" if is_last else stage_vars[min(i, len(stage_vars) - 1)]
        # --s4 is the deep stage fill; with five or more stages it is not only the last
        # one, and dark text on it was 1.3 to 3:1. Any stage on it takes the light text.
        deep = fill == "var(--s4)"
        text_fill = "var(--on-primary)" if deep else "var(--text)"
        detail_fill = "var(--detail)" if deep else "var(--subtext)"

        stroke = "var(--border)"
        svg.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{stage_w}" height="{h:.0f}" fill="{fill}" rx="6" stroke="{stroke}" stroke-width="1"/>')
        svg.append(f'<text x="{x + stage_w//2:.0f}" y="{y + 22:.0f}" text-anchor="middle" fill="{text_fill}" font-size="13" font-weight="700">Stage {i+1}</text>')
        name_lines, detail_lines = wrapped[i]
        for k, line in enumerate(name_lines):
            svg.append(f'<text x="{x + stage_w//2:.0f}" y="{y + 38 + 13 * k:.0f}" text-anchor="middle" fill="{text_fill}" font-size="11">{_escape_xml(line)}</text>')
        # Detail lines: wrap to box width and clamp to box bottom so nothing overflows.
        cursor_y = y + 54 + 13 * (len(name_lines) - 1)
        for line in detail_lines:
            svg.append(f'<text x="{x + stage_w//2:.0f}" y="{cursor_y:.0f}" text-anchor="middle" fill="{detail_fill}" font-size="8">{_escape_xml(line)}</text>')
            cursor_y += 12

    # Arrow along bottom
    arrow_y = total_h - 18
    svg.append(f'<line x1="60" y1="{arrow_y}" x2="{w - 60}" y2="{arrow_y}" stroke="var(--muted)" stroke-width="1.5"/>')
    svg.append(f'<polygon points="{w - 60},{arrow_y} {w - 68},{arrow_y - 4} {w - 68},{arrow_y + 4}" fill="var(--muted)"/>')
    if axis:
        svg.append(f'<text x="{w//2}" y="{total_h - 5}" text-anchor="middle" fill="var(--subtext)" font-size="9">{_escape_xml(axis)}</text>')

    svg.append("</svg>")
    return scope_svg("\n".join(svg))
