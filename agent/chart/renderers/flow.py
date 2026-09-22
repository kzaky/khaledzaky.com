"""Vertical flow diagram renderer.

Spec format (pipe-delimited):
  flow | Title | Node A | Node B | ...

A node may declare side branches with '+label>target', repeated:
  flow | Title | Deterministic controls +violation>Block | Apply policy

'--' as a node starts a new chain: a vertical gap with no connecting arrow, for
showing two separate paths in one figure.

The existing renderers cover ascending sequences (progression), layered stacks
(stack) and two-sided opposition (comparison). A plain top-to-bottom flow had no
renderer, so ASCII pipe-and-caret diagrams stayed in <pre> blocks. Styling follows
the other renderers exactly: Lora serif title with an accent rule, Inter body text,
rounded var(--card) boxes, and CSS variables so dark mode works after BlogPost.astro
inlines the SVG.
"""

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _wrap_text

_BREAK = "__break__"


def _parse_node(raw):
    """Split 'Label +branch>target +branch2>target2' into (label, [(branch, target)])."""
    parts = raw.split("+")
    label = parts[0].strip()
    branches = []
    for p in parts[1:]:
        if ">" in p:
            b_label, b_target = p.split(">", 1)
            if b_target.strip():
                branches.append((b_label.strip(), b_target.strip()))
    return label, branches


def _arrow_down(svg, x, y1, y2):
    svg.append(
        f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 7}" '
        f'stroke="var(--subtext)" stroke-width="1.5"/>'
    )
    svg.append(
        f'<polygon points="{x},{y2} {x - 4},{y2 - 7} {x + 4},{y2 - 7}" fill="var(--subtext)"/>'
    )


def _box(svg, x, y, w, h, label, font_size=12, weight="600",
         fill="var(--item-bg)", stroke="var(--c0)", stroke_width="2"):
    svg.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" rx="6" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )
    lines = _wrap_text(label, w - 20, font_size, max_lines=2)
    if len(lines) == 1:
        svg.append(
            f'<text x="{x + w // 2}" y="{y + h // 2 + 4}" text-anchor="middle" '
            f'fill="var(--text)" font-size="{font_size}" font-weight="{weight}">'
            f'{_escape_xml(lines[0])}</text>'
        )
    else:
        svg.append(
            f'<text x="{x + w // 2}" y="{y + h // 2 - 3}" text-anchor="middle" '
            f'fill="var(--text)" font-size="{font_size}" font-weight="{weight}">'
            f'{_escape_xml(lines[0])}</text>'
        )
        svg.append(
            f'<text x="{x + w // 2}" y="{y + h // 2 + 12}" text-anchor="middle" '
            f'fill="var(--text)" font-size="{font_size}" font-weight="{weight}">'
            f'{_escape_xml(lines[1])}</text>'
        )


def render_flow_diagram(fields):
    """Render a top-to-bottom flow with optional side branches."""
    if len(fields) < 2:
        return None

    title = fields[0]
    nodes = []
    for f in fields[1:]:
        f = f.strip()
        if not f:
            continue
        if f == "--":
            nodes.append((_BREAK, []))
            continue
        nodes.append(_parse_node(f))

    if not [n for n, _ in nodes if n != _BREAK]:
        return None

    w = 700
    has_branches = any(br for _, br in nodes)
    box_w = 300 if has_branches else 360
    box_x = 40 if has_branches else (w - box_w) // 2
    branch_w = 240
    branch_x = w - 40 - branch_w
    node_h = 52
    branch_h = 40
    branch_gap = 8
    arrow_h = 32
    break_h = 24

    title_lines = _wrap_text(title, w - 60, 20, max_lines=2)
    rule_y = 30 + (len(title_lines) - 1) * 22 + 12
    top = rule_y + 28

    # --- measure first so the viewBox height is exact (no clipping, no dead space) ---
    laid_out = []
    y = top
    prev_real = False
    for label, branches in nodes:
        if label == _BREAK:
            y += break_h
            prev_real = False
            continue
        if prev_real:
            y += arrow_h
        stack_h = len(branches) * branch_h + max(0, len(branches) - 1) * branch_gap
        h = max(node_h, stack_h)
        laid_out.append((label, branches, y, h))
        y += h
        prev_real = True
    total_h = y + 22

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" '
        f'font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)"/>',
    ]
    for i, line in enumerate(title_lines):
        fs = 20 if len(title_lines) == 1 else 18
        svg.append(
            f'<text x="30" y="{30 + i * 22}" text-anchor="start" fill="var(--text)" '
            f'font-size="{fs}" font-weight="700" font-family="{FONT_FAMILY_TITLE}">'
            f'{_escape_xml(line)}</text>'
        )
    svg.append(
        f'<line x1="30" y1="{rule_y}" x2="{w - 30}" y2="{rule_y}" '
        f'stroke="var(--c0)" stroke-width="2" opacity="0.35"/>'
    )

    cx = box_x + box_w // 2
    for idx, (label, branches, ny, h) in enumerate(laid_out):
        box_y = ny + (h - node_h) // 2
        _box(svg, box_x, box_y, box_w, node_h, label)

        # Arrow to the next node only when the chain continues (a '--' break ends it).
        if idx + 1 < len(laid_out):
            next_y = laid_out[idx + 1][2]
            next_h = laid_out[idx + 1][3]
            next_box_y = next_y + (next_h - node_h) // 2
            if next_y - (ny + h) >= arrow_h:
                _arrow_down(svg, cx, box_y + node_h, next_box_y)

        for b_i, (b_label, b_target) in enumerate(branches):
            by = ny + b_i * (branch_h + branch_gap)
            mid_y = by + branch_h // 2
            svg.append(
                f'<path d="M {box_x + box_w} {box_y + node_h // 2} '
                f'H {box_x + box_w + 26} V {mid_y} H {branch_x - 8}" '
                f'fill="none" stroke="var(--subtext)" stroke-width="1.5"/>'
            )
            svg.append(
                f'<polygon points="{branch_x},{mid_y} {branch_x - 7},{mid_y - 4} '
                f'{branch_x - 7},{mid_y + 4}" fill="var(--subtext)"/>'
            )
            if b_label:
                svg.append(
                    f'<text x="{box_x + box_w + 30}" y="{mid_y - 6}" '
                    f'fill="var(--subtext)" font-size="10">{_escape_xml(b_label)}</text>'
                )
            # Branch outcomes take the secondary accent, the same way architecture
            # distinguishes node classes by stroke colour rather than by layout.
            _box(svg, branch_x, by, branch_w, branch_h, b_target, font_size=11,
                 weight="600", fill="var(--card)", stroke="var(--c1)")

    svg.append("</svg>")
    return "\n".join(svg)
