"""Chart fixes for defects that shipped: a comparison row split on the wrong colon
(1a9052d), bar titles clipped by the canvas (22 published figures), and a two-model
title over one model's bars (1a9052d)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "chart"))

from renderers import bar, comparison  # noqa: E402

VALUES = [("Direct", 23.1), ("Reconstructed", 44.4), ("Hard routing", 33.9)]


def _texts(svg):
    return [t for t in re.findall(r">([^<>]+)</text>", svg)]


# --- comparison: the column separator is the colon not followed by a space ---------

def test_row_with_labelled_cells_splits_between_the_cells():
    assert comparison._split_row("Jev: 91.0% accuracy:Jev: 68.1% accuracy") == ("Jev: 91.0% accuracy", "Jev: 68.1% accuracy")


def test_single_colon_rows_split_exactly_as_before():
    for row in ("One call over all labels:Category call + per-category calls", "left: right", "a:b"):
        assert comparison._split_row(row) == tuple(row.split(":", 1))


def test_rendered_comparison_keeps_each_cell_whole():
    svg = comparison.render_comparison_diagram(["Asked directly", "Asked in two steps",
                                                "Jev: 91.0% accuracy:Jev: 68.1% accuracy"])
    texts = _texts(svg)
    assert "Jev: 91.0% accuracy" in texts and "Jev: 68.1% accuracy" in texts
    assert not any("accuracy:Jev" in t for t in texts)


def test_published_iam_comparison_rows_keep_before_and_after_apart():
    """pen-test-iam-comparison.svg shipped with 'all permissions:Ingest: S3 read ...'
    in the After column; the same rows now split into Before and After cells."""
    svg = comparison.render_comparison_diagram([
        "Shared Role (Before)", "Per-Function Role (After)",
        "Ingest: all permissions:Ingest: S3 read (inbound) + SFN start",
        "Approve: all permissions:Approve: SFN task tokens only",
    ])
    texts = _texts(svg)
    assert {"Ingest: all permissions", "Ingest: S3 read (inbound) + SFN start",
            "Approve: all permissions", "Approve: SFN task tokens only"} <= set(texts)
    assert not any("permissions:" in t for t in texts)


# --- bar titles -------------------------------------------------------------------------

def test_titles_the_old_layout_fits_are_unchanged():
    for title in ("Jev and Laya accuracy on CLINC150", "Agent identity is generally available"):
        assert bar.title_warnings(title) == []
        svg = bar.render_bar_chart(VALUES, title)
        assert svg.count('font-family="Lora') >= 1 and 'viewBox="0 0 700 ' in svg


def test_long_title_wraps_to_lines_that_fit():
    title = ("Bar chart showing software testing as percentage of total development budget: "
             "Low-complexity (25%), Regulated/complex (35%), Safety-critical (50%+). Source: Idealink Tech")
    svg = bar.render_bar_chart(VALUES, title)
    lines = [t for t in _texts(svg) if t not in {"Direct", "Reconstructed", "Hard routing", "23.1", "44.4", "33.9"}]
    assert 2 <= len(lines) <= 3 and all(len(t) <= bar._TITLE_LINE_MAX for t in lines)
    assert bar.title_warnings(title)


def test_title_area_grows_with_the_third_line():
    two = bar.render_bar_chart(VALUES, "A" * 0 + " ".join(["word"] * 20))
    three = bar.render_bar_chart(VALUES, " ".join(["word"] * 30))
    h = lambda s: int(re.search(r'viewBox="0 0 700 (\d+)"', s).group(1))  # noqa: E731
    assert h(three) > h(two)


def test_over_long_title_is_cut_with_an_ellipsis_and_warned():
    title = " ".join(["sentence"] * 40)
    lines, truncated = bar._wrapped_title(title)
    assert truncated and len(lines) == bar._TITLE_MAX_LINES and lines[-1].endswith("…")
    assert "cut to 4 lines" in bar.title_warnings(title)[0]


def test_every_published_title_length_fits_without_an_ellipsis():
    """The longest title the pipeline has published is 188 characters."""
    title = ("Bar chart showing software testing as percentage of total development budget: "
             "Low-complexity (12.5%), Standard (25%), Regulated/complex (35%), "
             "Safety-critical (50%+). Source: Idealink Tech")
    lines, truncated = bar._wrapped_title(title)
    assert not truncated and " ".join(lines) == title


# --- pie titles -------------------------------------------------------------------------

def test_pie_title_keeps_every_word_or_says_it_did_not():
    from renderers import pie
    fits = "ML models reaching production vs. never reaching production due to operational challenges"
    lines, truncated = pie._wrap_title(fits)
    assert not truncated and " ".join(lines) == fits and pie.title_warnings(fits) == []
    long = " ".join(["sentence"] * 30)
    lines, truncated = pie._wrap_title(long)
    assert truncated and len(lines) == 3 and lines[-1].endswith("…")
    assert pie.title_warnings(long)


# --- series vs title --------------------------------------------------------------------

def _chart_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("chart_index_for_tests", ROOT / "agent" / "chart" / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_two_entity_title_over_one_entitys_bars_is_flagged():
    chart = _chart_module()
    w = chart._chart_warnings({"values": VALUES, "chart_type": "bar"},
                              "Jev and Laya accuracy by formulation on CLINC150")
    assert any("Jev and Laya" in x for x in w)


def test_bars_that_name_both_entities_are_fine():
    chart = _chart_module()
    vals = [("Jev, direct", 91.0), ("Laya, direct", 23.1)]
    assert chart._chart_warnings({"values": vals, "chart_type": "bar"}, "Jev and Laya accuracy on CLINC150") == []


def test_lowercase_comparisons_are_not_entity_pairs():
    chart = _chart_module()
    assert chart._chart_warnings({"values": VALUES, "chart_type": "bar"}, "AI adoption vs governance maturity") == []


# --- CHART_STYLE=brand -------------------------------------------------------------------

_SKY = {"#e0f2fe", "#bae6fd", "#7dd3fc", "#38bdf8", "#0ea5e9", "#0284c7", "#0369a1", "#075985", "#0c4a6e", "#082f49"}
_SLATE = {"#cbd5e1", "#94a3b8", "#64748b", "#475569", "#334155"}


def _theme(monkeypatch, style):
    import importlib

    from renderers import theme
    if style is None:
        monkeypatch.delenv("CHART_STYLE", raising=False)
    else:
        monkeypatch.setenv("CHART_STYLE", style)
    return importlib.reload(theme)


def test_brand_is_the_default(monkeypatch):
    theme = _theme(monkeypatch, None)
    assert theme.CHART_STYLE == "brand" and theme.COLORS == theme.BRAND_COLORS


def test_classic_palette_keeps_its_original_colours(monkeypatch):
    theme = _theme(monkeypatch, "classic")
    try:
        assert theme.COLORS[:3] == ["#0284c7", "#d97706", "#059669"]
        assert theme.TOKENS["light"]["subtext"] == "#6b7280" and theme.TOKENS["dark"]["on-accent"] == "white"
        assert theme.STACK_SHADES[0] == "#0284c7"
    finally:
        _theme(monkeypatch, None)


def _contrast(a, b):
    """WCAG 2 contrast ratio of two #rrggbb (or 'white') colours."""
    def lum(c):
        c = "#ffffff" if c == "white" else c
        ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        ch = [u / 12.92 if u <= 0.03928 else ((u + 0.055) / 1.055) ** 2.4 for u in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_brand_text_meets_wcag_aa_in_both_modes(monkeypatch):
    """Every text-on-fill pairing the renderers draw, at the 4.5:1 AA bar for body text.
    (A browser audit of all eleven renderers, measuring what is actually painted under
    each label, found 0 of 214 texts below AA in brand; classic has 48.)"""
    theme = _theme(monkeypatch, "brand")
    try:
        fails = []
        for mode, colors, page in (("light", theme.COLORS, (theme.BG_COLOR, theme.CARD_COLOR)),
                                   ("dark", theme.COLORS_DARK, (theme.BG_COLOR_DARK, theme.CARD_COLOR_DARK))):
            t = theme.TOKENS[mode]
            text = theme.TEXT_COLOR if mode == "light" else theme.TEXT_COLOR_DARK
            pairs = [("on-accent", t["on-accent"], f"c{i}", colors[i]) for i in (0, 1)]            # headers, tiles
            shades = {theme.stack_shade(i, n) for n in range(1, 8) for i in range(n)}
            pairs += [("on-primary", t["on-primary"], "stack", s) for s in sorted(shades)]
            pairs += [("detail", t["detail"], "stack", s) for s in sorted(shades)]
            if mode == "dark":  # layers must stay visible on the dark page (3:1 non-text)
                fails += [f"dark: stack layer {s} on page = {_contrast(s, page[0]):.2f}:1"
                          for s in sorted(shades) if _contrast(s, page[0]) < 1.9]
            pairs += [("on-primary", t["on-primary"], "s4", t["s4"]), ("detail", t["detail"], "s4", t["s4"])]
            for fill_name in ("item-bg", "s1", "s2", "s3"):
                pairs += [("subtext", t["subtext"], fill_name, t[fill_name]), ("text", text, fill_name, t[fill_name])]
            pairs += [("subtext", t["subtext"], "page", c) for c in page]
            pairs += [("c0", colors[0], "item-bg", t["item-bg"])] + [("c0", colors[0], "page", c) for c in page]
            for fg_name, fg, bg_name, bg in pairs:
                r = _contrast(fg, bg)
                if r < 4.5:
                    fails.append(f"{mode}: {fg_name} {fg} on {bg_name} {bg} = {r:.2f}:1")
        assert fails == []
    finally:
        _theme(monkeypatch, None)


def test_brand_palette_stays_inside_the_site_scale(monkeypatch):
    theme = _theme(monkeypatch, "brand")
    try:
        assert set(theme.COLORS) <= _SKY | _SLATE and set(theme.COLORS_DARK) <= _SKY | _SLATE
        assert "#d97706" not in theme._dark_mode_style() and "#7c3aed" not in theme._dark_mode_style()
    finally:
        _theme(monkeypatch, None)


def test_brand_changes_colour_and_nothing_else(monkeypatch):
    import importlib

    import renderers.comparison as comp
    spec = ["Traditional Software", "AI Agents", "Deterministic:Probabilistic", "Static Permissions:Dynamic Authority"]
    _theme(monkeypatch, "classic"); importlib.reload(comp)  # noqa: E702
    classic = comp.render_comparison_diagram(spec)
    _theme(monkeypatch, "brand"); importlib.reload(comp)  # noqa: E702
    brand = comp.render_comparison_diagram(spec)
    _theme(monkeypatch, None); importlib.reload(comp)  # noqa: E702
    strip = lambda s: re.sub(r"#[0-9a-f]{6}|\bwhite\b|kzc-[0-9a-f]{10}", "#C", s)  # noqa: E731
    assert classic != brand and strip(classic) == strip(brand)


# --- colour variables are scoped to each figure ---------------------------------------

def test_every_renderer_scopes_its_variables_to_its_own_svg():
    """BlogPost.astro inlines every SVG into one page; a :root rule in one figure
    recoloured all the others (a brand figure turned a classic header from amber to
    navy). Each figure must declare its variables on its own class."""
    import sys
    import types
    sys.modules.setdefault("boto3", types.SimpleNamespace(client=lambda *a, **k: None))
    sys.path.insert(0, str(ROOT / "agent" / "chart"))
    import index as chart
    specs = [
        "comparison | A | B | x:y", "flow | T | One | Two", "stack | T | One;a | Two;b",
        "framework | T | Who;q | What;q", "convergence | C | A;a | B;b", "venn | T | A;a | B;b | C;c",
        "progression | T | S1;a | S2;b", "timeline | T | A;a | B;b",
        "architecture | T | inputs: A | steps: B;C | outputs: D",
    ]
    svgs = [chart._render_diagram(s) for s in specs]
    svgs += [chart._render_chart({"values": [("a", 1), ("b", 2)], "chart_type": t}, "T") for t in ("bar", "pie")]
    classes = set()
    for svg in svgs:
        assert svg and ":root" not in svg and "\n  .dark svg {" not in svg
        cls = re.match(r'<svg class="(kzc-[0-9a-f]{10})"', svg).group(1)
        assert f"svg.{cls} {{" in svg and f".dark svg.{cls} {{" in svg
        classes.add(cls)
    assert len(classes) == len(svgs)


def test_brand_pie_slices_separate_from_their_neighbours(monkeypatch):
    """Brand accents --c0/--c1 are two deep blues (3.6:1 would be needed to tell a
    two-slice donut apart); pies use --p0..--p7, which alternate dark and light."""
    theme = _theme(monkeypatch, "brand")
    try:
        for pal in (theme.PIE_COLORS, theme.PIE_COLORS_DARK):
            pairs = [(pal[i], pal[(i + 1) % len(pal)]) for i in range(len(pal))]
            assert min(_contrast(a, b) for a, b in pairs) >= 2.5
        style = theme._dark_mode_style()
        assert "--p0: #0369a1;" in style and "--p1: #075985;" in style
    finally:
        _theme(monkeypatch, None)


def test_classic_pie_keeps_its_original_slice_colours(monkeypatch):
    theme = _theme(monkeypatch, "classic")
    try:
        assert theme.PIE_COLORS[:2] == ["#0284c7", "#d97706"]
    finally:
        _theme(monkeypatch, None)
