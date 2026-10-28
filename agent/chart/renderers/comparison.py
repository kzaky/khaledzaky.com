"""Two-column comparison diagram renderer."""

import re

from .theme import FONT_FAMILY, FONT_FAMILY_TITLE, _dark_mode_style, _escape_xml, _text_lines, _wrap_text, scope_svg


def _split_row(field):
    """Split a 'left:right' row. Cells may carry their own 'Label: value' colon, so a
    row like 'Jev: 91.0% accuracy:Jev: 68.1% accuracy' split on the FIRST colon put
    'Jev' on the left and the rest, run together, on the right (9df1876). The column
    separator is the first colon NOT followed by whitespace; with none, the first colon
    (the original behaviour for every single-colon row)."""
    for i, ch in enumerate(field):
        if ch == ":" and i + 1 < len(field) and not field[i + 1].isspace():
            return field[:i], field[i + 1:]
    left, right = field.split(":", 1)
    return left, right


class ComparisonSpecError(ValueError):
    """A comparison spec whose rows cannot be read without guessing. The Chart Lambda
    turns this into a reviewer warning and drops the placeholder instead of drawing it."""


# 'MAP: identify risks' -> ('MAP', 'identify risks'): a cell carrying its own label.
_LABELLED_CELL_RE = re.compile(r"^\s*([^:]{1,40}?)\s*:\s+(\S.*)$")


def _has_column_separator(field):
    """True when the field holds a 'left:right' separator: a colon NOT followed by
    whitespace (see _split_row)."""
    return any(ch == ":" and i + 1 < len(field) and not field[i + 1].isspace() for i, ch in enumerate(field))


def _separator_positions(field):
    """Indexes of the colons that separate cells: those NOT followed by whitespace."""
    return [i for i, ch in enumerate(field) if ch == ":" and i + 1 < len(field) and not field[i + 1].isspace()]


def _labelled_rows(items):
    """'Row label:Left cell:Right cell' rows, as (label, left, right), when EVERY row has
    that shape. A live draft (e2e-test-20261028-4) wrote 'Who reviews output:Every
    response...:Graduated from...': split at the first colon only, the right column held
    'left:right' run together and overflowed its box. Requiring every row to carry two
    separators keeps a lone ratio such as '1:10:100' in an ordinary row from triggering it."""
    if not items:
        return None
    rows = []
    for f in items:
        cuts = _separator_positions(f)
        if len(cuts) != 2:
            return None
        a, b = cuts
        label, left, right = f[:a].strip(), f[a + 1:b].strip(), f[b + 1:].strip()
        if not (label and left and right):
            return None
        rows.append((label, left, right))
    return rows


def _label_style(label):
    # First word only: the live NIST spec labelled one row 'MANAGE (residual risk)', and
    # judging the whole label put it in a different style from MAP/GOVERN/MEASURE.
    first = label.split()[0] if label.split() else label
    return "upper" if first.isupper() else "other"


def _paired_cells(items):
    """Detect one cell per field: 'MAP: identify risks | Shadow: observe real data | ...'.

    A live draft wrote each cell as its own 'Label: text' field, alternating left and
    right columns. Split at the colon, every field became a row of its own and the two
    columns were scrambled (MAP -> 'identify risks', then Shadow -> 'observe real data').

    Returns ('paired', [(left, right), ...]), ('broken', reason) when the fields clearly
    alternate between two columns but do not pair up, or (None, None) when the fields are
    ordinary 'Label: description' rows. The alternation is recognised when the labels of
    the even fields and the odd fields differ in kind: one column repeats one label
    ('Before: ... | After: ...') or the columns use different label styles (MAP/GOVERN in
    capitals against Shadow/Suggest). Labels of one uniform kind stay ordinary rows.
    """
    if len(items) < 2 or any(_has_column_separator(f) for f in items):
        return None, None
    matches = [_LABELLED_CELL_RE.match(f) for f in items]
    if not all(matches):
        return None, None
    labels = [m.group(1).strip() for m in matches]
    if any(len(lab.split()) > 4 for lab in labels):
        return None, None
    even, odd = labels[0::2], labels[1::2]
    if not odd or set(even) & set(odd):
        return None, None
    repeated = len(set(even)) == 1 and len(set(odd)) == 1 and len(even) > 1
    even_styles = {_label_style(lab) for lab in even}
    odd_styles = {_label_style(lab) for lab in odd}
    styled = len(even_styles) == 1 and len(odd_styles) == 1 and even_styles != odd_styles
    if not (repeated or styled):
        return None, None
    if len(items) % 2:
        return "broken", (
            f"comparison has {len(items)} 'Label: text' cells alternating between the two columns; "
            "an odd count cannot pair into rows. Write each row as one field, 'Left cell:Right cell'"
        )
    return "paired", [(items[i].strip(), items[i + 1].strip()) for i in range(0, len(items), 2)]


def parse_comparison_rows(fields):
    """Rows of a comparison spec as (left, right) cell pairs, or (label, left, right)
    triples when every row is written 'Row label:Left cell:Right cell'.

    fields: [left_header, right_header, row, row, ...] where each row is ONE field,
    'Left cell:Right cell' (the separator is the first colon not followed by a space, so a
    cell may carry its own 'Label: text'). Raises ComparisonSpecError when the rows are
    recognisably malformed rather than guessing.
    """
    if len(fields) < 3:
        return []
    rows = []
    if len(fields) == 3 and ";" in fields[2] and ":" not in fields[2]:
        # 'left_header | right_header | item1;item2;...': single column fallback
        lefts = [x.strip() for x in fields[2].split(";") if x.strip()]
        rows = [(item, item) for item in lefts]
    elif len(fields) >= 4 and ";" in fields[2]:
        # Format: 'left_header | right_header | left1;left2;left3 | right1;right2;right3'
        lefts = [x.strip() for x in fields[2].split(";") if x.strip()]
        rights = [x.strip() for x in fields[3].split(";") if x.strip()]
        rows = list(zip(lefts, rights, strict=False))
    else:
        items = [f for f in fields[2:] if ":" in f]
        kind, value = _paired_cells(items)
        if kind == "broken":
            raise ComparisonSpecError(value)
        if kind == "paired":
            return value
        labelled = _labelled_rows(items)
        if labelled:
            return labelled
        # Original format: 'left_header | right_header | left:right | left:right | ...'
        for f in items:
            left, right = _split_row(f)
            rows.append((left.strip(), right.strip()))
    return rows


def render_comparison_diagram(fields):
    """Render a two-column comparison diagram with dark mode support.
    fields: [left_header, right_header, row1_left:row1_right, ...]
    Raises ComparisonSpecError for a spec whose rows cannot be read unambiguously.
    """
    if len(fields) < 3:
        return None

    left_header = fields[0]
    right_header = fields[1]
    rows = parse_comparison_rows(fields)

    if not rows:
        return None

    labelled = len(rows[0]) == 3
    if not labelled:
        rows = [(None, left, right) for left, right in rows]

    w = 700
    gap = 10
    header_h = 32
    line_h = 14
    label_w = 150 if labelled else 0
    arrow_w = 40
    col_w = (w - 60 - label_w - (gap if labelled else 0) - arrow_w) // 2
    x_left = 30 + label_w + (gap if labelled else 0)
    x_right = w - 30 - col_w

    # Wrap every cell (up to 4 lines) and size each row to its tallest cell, so long text
    # grows the row instead of being cut at two lines or running past the box.
    laid_out = []
    for label, left, right in rows:
        ll = _wrap_text(left, col_w - 16, 11, max_lines=4)
        rl = _wrap_text(right, col_w - 16, 11, max_lines=4)
        lab = _wrap_text(label, label_w - 12, 11, max_lines=3) if label else []
        n = max(len(ll), len(rl), len(lab), 1)
        laid_out.append((lab, ll, rl, max(48, 20 + n * line_h)))

    title_str = f"{left_header} vs {right_header}"
    title_lines = _text_lines(title_str, w - 60, 20)
    title_block_h = 16 if len(title_lines) == 1 else 34
    top = 50 + title_block_h  # push content down if title wraps
    total_h = top + header_h + gap + sum(h + gap for *_, h in laid_out) + 20

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" font-family="{FONT_FAMILY}">',
        _dark_mode_style(),
        f'<rect width="{w}" height="{total_h}" fill="var(--bg)"/>',
    ]
    if len(title_lines) == 1:
        svg.append(f'<text x="{w//2}" y="30" text-anchor="middle" fill="var(--text)" font-size="20" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[0])}</text>')
        svg.append(f'<line x1="30" y1="42" x2="{w - 30}" y2="42" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>')
    else:
        svg.append(f'<text x="{w//2}" y="22" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[0])}</text>')
        svg.append(f'<text x="{w//2}" y="42" text-anchor="middle" fill="var(--text)" font-size="18" font-weight="700" font-family="{FONT_FAMILY_TITLE}">{_escape_xml(title_lines[1])}</text>')
        svg.append(f'<line x1="30" y1="54" x2="{w - 30}" y2="54" stroke="var(--c0)" stroke-width="2" opacity="0.35"/>')
    arrow_x = (x_left + col_w + x_right) // 2
    svg += [
        # Headers
        f'<rect x="{x_left}" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c0)" rx="6"/>',
        f'<text x="{x_left + col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-accent)" font-size="12" font-weight="600">{_escape_xml(left_header)}</text>',
        f'<rect x="{x_right}" y="{top - 5}" width="{col_w}" height="{header_h}" fill="var(--c1)" rx="6"/>',
        f'<text x="{x_right + col_w//2}" y="{top + 16}" text-anchor="middle" fill="var(--on-accent)" font-size="12" font-weight="600">{_escape_xml(right_header)}</text>',
        f'<text x="{arrow_x}" y="{top + 16}" text-anchor="middle" fill="var(--muted)" font-size="16">\u2192</text>',
    ]

    def _cell_text(x_center, y_top, h, lines, weight, fill, anchor="middle"):
        first = y_top + h // 2 - (len(lines) - 1) * line_h // 2 + 4
        for k, line in enumerate(lines):
            svg.append(f'<text x="{x_center}" y="{first + k * line_h}" text-anchor="{anchor}" fill="{fill}" font-size="11" font-weight="{weight}">{_escape_xml(line)}</text>')

    y = top + header_h + gap
    for lab, ll, rl, h in laid_out:
        if lab:
            _cell_text(30 + label_w - 6, y, h, lab, "600", "var(--subtext)", anchor="end")
        svg.append(f'<rect x="{x_left}" y="{y}" width="{col_w}" height="{h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        _cell_text(x_left + col_w // 2, y, h, ll, "600" if not labelled else "500", "var(--text)")
        svg.append(f'<rect x="{x_right}" y="{y}" width="{col_w}" height="{h}" fill="var(--card)" rx="6" stroke="var(--border)" stroke-width="1"/>')
        _cell_text(x_right + col_w // 2, y, h, rl, "600" if not labelled else "500", "var(--text)")
        svg.append(f'<text x="{arrow_x}" y="{y + h//2 + 4}" text-anchor="middle" fill="var(--muted)" font-size="14">\u2192</text>')
        y += h + gap

    svg.append("</svg>")
    return scope_svg("\n".join(svg))
