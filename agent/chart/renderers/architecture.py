"""Conceptual architecture flow diagram renderer.

Spec format (pipe-delimited):
  architecture | Title | inputs: A;B | steps: S1;S2;S3;S4 | outputs: O1;O2;O3
  Optional trailing field: footer: Some observability / infra note

Node shape vocabulary — append [type] to any node name:
  [model]    — AI/ML model  (violet border, blue-tinted fill)
  [storage]  — Data/S3/DB   (amber border)
  [function] — Lambda/compute (cyan border)
  [service]  — External API  (blue border, tinted fill)
  (no tag)   — default process box

Renders: input boxes -> converging arrows -> dashed processing container
         with step boxes -> fan-out arrows -> output boxes.
All colors use CSS variables so dark mode works after BlogPost.astro inlining.
"""

from .theme import FONT_FAMILY, _dark_mode_style, _escape_xml, _text_lines

_NODE_FILL = {
    "default":  "var(--bg)",
    "model":    "var(--item-bg)",
    "storage":  "var(--card)",
    "function": "var(--card)",
    "service":  "var(--item-bg)",
}
_NODE_STROKE = {
    "default":  "var(--border)",
    "model":    "var(--c4)",
    "storage":  "var(--c1)",
    "function": "var(--c6)",
    "service":  "var(--c0)",
}
_NODE_STROKE_W = {
    "default":  "1",
    "model":    "2",
    "storage":  "2",
    "function": "2",
    "service":  "2",
}


def _parse_node(spec):
    """Parse 'Node Name[type]' -> (name, node_type)."""
    spec = spec.strip()
    if spec.endswith("]") and "[" in spec:
        name, _, ntype = spec[:-1].rpartition("[")
        return name.strip(), ntype.strip().lower()
    return spec, "default"


def _cell(svg, text, cx, box_y, box_w, box_h, fsize, fill, bold=False):
    """Render text centered in a box, splitting to 2 lines if needed."""
    fw = "600" if bold else "400"
    lines = _text_lines(text, box_w - 10, fsize)
    if len(lines) == 1:
        ty = box_y + box_h // 2 + fsize // 3
        svg.append(
            f'<text x="{cx}" y="{ty}" text-anchor="middle" fill="{fill}" '
            f'font-size="{fsize}" font-weight="{fw}">{_escape_xml(lines[0])}</text>'
        )
    else:
        ty1 = box_y + box_h // 2 - 2
        ty2 = ty1 + fsize + 2
        svg.append(
            f'<text x="{cx}" y="{ty1}" text-anchor="middle" fill="{fill}" '
            f'font-size="{fsize}" font-weight="{fw}">{_escape_xml(lines[0])}</text>'
        )
        svg.append(
            f'<text x="{cx}" y="{ty2}" text-anchor="middle" fill="{fill}" '
            f'font-size="{fsize - 1}">{_escape_xml(lines[1])}</text>'
        )


def render_architecture_diagram(fields):
    """Render an architecture flow: inputs -> processing steps -> outputs.

    fields: [title, "inputs: A;B", "steps: S1;S2;S3;S4", "outputs: O1;O2;O3"]
    Optional last field: "footer: some note"
    """
    if len(fields) < 4:
        return None

    title = fields[0]
    inputs, steps, outputs, footer = [], [], [], ""

    for f in fields[1:]:
        key, _, val = f.partition(":")
        key = key.strip().lower()
        val = val.strip()
        items = [x.strip() for x in val.split(";") if x.strip()]
        if key == "inputs":
            inputs = [_parse_node(x) for x in items]
        elif key == "steps":
            steps = [_parse_node(x) for x in items]
        elif key == "outputs":
            outputs = [_parse_node(x) for x in items]
        elif key == "footer":
            footer = val

    if not inputs or not steps or not outputs:
        return None

    W, PAD = 700, 30
    CX = W // 2

    # Input row
    IN_H = 50
    in_n = len(inputs)
    in_gap = 10
    in_bw = min(170, (W - 2 * PAD - (in_n - 1) * in_gap) // in_n)
    in_x0 = (W - (in_n * in_bw + (in_n - 1) * in_gap)) // 2
    IN_Y = 44

    # Converge point
    CONV_Y = IN_Y + IN_H + 20

    # Steps dashed box
    STEPS_Y = CONV_Y
    per_row = min(4, len(steps))
    step_rows = -(-len(steps) // per_row)
    step_bw = min(135, (W - 2 * PAD - 20 - (per_row - 1) * 8) // per_row)
    step_bh = 36
    STEPS_H = 18 + step_rows * step_bh + (step_rows - 1) * 8 + 10
    STEPS_BOTTOM = STEPS_Y + STEPS_H

    # Fan-out to outputs
    FAN_Y = STEPS_BOTTOM + 18
    OUT_Y = FAN_Y + 14
    OUT_H = 58
    out_n = len(outputs)
    out_gap = 10
    out_bw = min(195, (W - 2 * PAD - (out_n - 1) * out_gap) // out_n)
    out_x0 = (W - (out_n * out_bw + (out_n - 1) * out_gap)) // 2

    footer_y = OUT_Y + OUT_H + 24
    total_h = footer_y + (14 if footer else 0)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{W}" height="{total_h}" fill="var(--bg)" rx="8" stroke="var(--border)" stroke-width="1"/>',
        f'<text x="{CX}" y="28" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="600">{_escape_xml(title)}</text>',
    ]

    # --- INPUTS ---
    for i, (inp_name, inp_type) in enumerate(inputs):
        x = in_x0 + i * (in_bw + in_gap)
        cx = x + in_bw // 2
        nfill = _NODE_FILL.get(inp_type, _NODE_FILL["default"])
        nstroke = _NODE_STROKE.get(inp_type, _NODE_STROKE["default"])
        nsw = _NODE_STROKE_W.get(inp_type, "1.5")
        svg.append(
            f'<rect x="{x}" y="{IN_Y}" width="{in_bw}" height="{IN_H}" rx="6" '
            f'fill="{nfill}" stroke="{nstroke}" stroke-width="{nsw}">'
            f'<title>{_escape_xml(inp_name)}</title></rect>'
        )
        _cell(svg, inp_name, cx, IN_Y, in_bw, IN_H, 11, "var(--text)", bold=True)
        mid_y = IN_Y + IN_H + 10
        svg.append(
            f'<polyline points="{cx},{IN_Y + IN_H} {cx},{mid_y} {CX},{CONV_Y}" '
            f'fill="none" stroke="var(--muted)" stroke-width="1.5"/>'
        )
    svg.append(
        f'<polygon points="{CX},{CONV_Y} {CX - 4},{CONV_Y - 7} {CX + 4},{CONV_Y - 7}" fill="var(--muted)"/>'
    )

    # --- STEPS DASHED CONTAINER ---
    svg.append(
        f'<rect x="{PAD}" y="{STEPS_Y}" width="{W - 2 * PAD}" height="{STEPS_H}" rx="8" '
        f'fill="var(--card)" stroke="var(--muted)" stroke-width="1.5" stroke-dasharray="6,3"/>'
    )
    for i, (step_name, step_type) in enumerate(steps):
        row = i // per_row
        col = i % per_row
        n_in_row = per_row if row < step_rows - 1 else (len(steps) - (step_rows - 1) * per_row)
        rw = n_in_row * step_bw + (n_in_row - 1) * 8
        rx0 = (W - rw) // 2
        sx = rx0 + col * (step_bw + 8)
        sy = STEPS_Y + 18 + row * (step_bh + 8)
        scx = sx + step_bw // 2
        sfill = _NODE_FILL.get(step_type, _NODE_FILL["default"])
        sstroke = _NODE_STROKE.get(step_type, _NODE_STROKE["default"])
        ssw = _NODE_STROKE_W.get(step_type, "1")
        svg.append(
            f'<rect x="{sx}" y="{sy}" width="{step_bw}" height="{step_bh}" rx="5" '
            f'fill="{sfill}" stroke="{sstroke}" stroke-width="{ssw}">'
            f'<title>{_escape_xml(step_name)}</title></rect>'
        )
        _cell(svg, step_name, scx, sy, step_bw, step_bh, 10, "var(--text)")

    # --- ARROW FROM STEPS TO FAN ---
    svg.append(
        f'<line x1="{CX}" y1="{STEPS_BOTTOM}" x2="{CX}" y2="{FAN_Y}" '
        f'stroke="var(--muted)" stroke-width="1.5"/>'
    )

    # --- FAN-OUT BAR + DROP ARROWS ---
    left_cx = out_x0 + out_bw // 2
    right_cx = out_x0 + (out_n - 1) * (out_bw + out_gap) + out_bw // 2
    if out_n > 1:
        svg.append(
            f'<line x1="{left_cx}" y1="{FAN_Y}" x2="{right_cx}" y2="{FAN_Y}" '
            f'stroke="var(--muted)" stroke-width="1.5"/>'
        )
    for i in range(out_n):
        ox = out_x0 + i * (out_bw + out_gap) + out_bw // 2
        svg.append(
            f'<line x1="{ox}" y1="{FAN_Y}" x2="{ox}" y2="{OUT_Y}" '
            f'stroke="var(--muted)" stroke-width="1.5"/>'
        )
        svg.append(
            f'<polygon points="{ox},{OUT_Y} {ox - 4},{OUT_Y - 7} {ox + 4},{OUT_Y - 7}" fill="var(--muted)"/>'
        )

    # --- OUTPUTS ---
    for i, (out_name, out_type) in enumerate(outputs):
        x = out_x0 + i * (out_bw + out_gap)
        cx = x + out_bw // 2
        ofill = _NODE_FILL.get(out_type, "var(--card)")
        ostroke = _NODE_STROKE.get(out_type, "var(--c2)")
        osw = _NODE_STROKE_W.get(out_type, "1.5")
        svg.append(
            f'<rect x="{x}" y="{OUT_Y}" width="{out_bw}" height="{OUT_H}" rx="6" '
            f'fill="{ofill}" stroke="{ostroke}" stroke-width="{osw}">'
            f'<title>{_escape_xml(out_name)}</title></rect>'
        )
        text_color = _NODE_STROKE.get(out_type, "var(--c2)")
        _cell(svg, out_name, cx, OUT_Y, out_bw, OUT_H, 11, text_color, bold=True)

    if footer:
        svg.append(
            f'<text x="{CX}" y="{footer_y}" text-anchor="middle" fill="var(--muted)" '
            f'font-size="9.5">{_escape_xml(footer)}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)
