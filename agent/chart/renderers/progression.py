"""Ascending staircase progression diagram renderer."""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml


def render_progression_diagram(fields):
    """Render ascending staircase stages with dark mode support.
    fields: [title, stage1_name;detail1;detail2, stage2_name;detail1, ...]
    """
    if len(fields) < 2:
        return None

    title = fields[0]
    stages = []
    for f in fields[1:]:
        parts = [p.strip() for p in f.split(";")]
        name = parts[0] if parts else ""
        details = parts[1:] if len(parts) > 1 else []
        stages.append((name, details))

    if not stages:
        return None

    n = len(stages)
    w = 700
    stage_w = 140
    base_h = 70
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

    for i, (name, details) in enumerate(stages):
        x = 40 + i * (stage_w + gap)
        h = base_h + i * 70
        y = top_margin + (max_h - h)
        fill = stage_vars[min(i, len(stage_vars) - 1)]
        is_last = (i == n - 1)
        text_fill = "var(--on-primary)" if is_last else "var(--text)"
        detail_fill = "var(--detail)" if is_last else "var(--subtext)"
        if is_last:
            fill = "var(--s4)"

        stroke = "var(--border)"
        svg.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{stage_w}" height="{h:.0f}" fill="{fill}" rx="6" stroke="{stroke}" stroke-width="1"/>')
        svg.append(f'<text x="{x + stage_w//2:.0f}" y="{y + 22:.0f}" text-anchor="middle" fill="{text_fill}" font-size="13" font-weight="700">Stage {i+1}</text>')
        svg.append(f'<text x="{x + stage_w//2:.0f}" y="{y + 38:.0f}" text-anchor="middle" fill="{text_fill}" font-size="11">{_escape_xml(name)}</text>')
        for j, detail in enumerate(details[:3]):
            svg.append(f'<text x="{x + stage_w//2:.0f}" y="{y + 56 + j * 14:.0f}" text-anchor="middle" fill="{detail_fill}" font-size="8">{_escape_xml(detail)}</text>')

    # Arrow along bottom
    arrow_y = total_h - 18
    svg.append(f'<line x1="60" y1="{arrow_y}" x2="{w - 60}" y2="{arrow_y}" stroke="var(--muted)" stroke-width="1.5"/>')
    svg.append(f'<polygon points="{w - 60},{arrow_y} {w - 68},{arrow_y - 4} {w - 68},{arrow_y + 4}" fill="var(--muted)"/>')
    svg.append(f'<text x="{w//2}" y="{total_h - 5}" text-anchor="middle" fill="var(--subtext)" font-size="9">Increasing platform maturity</text>')

    svg.append("</svg>")
    return "\n".join(svg)
