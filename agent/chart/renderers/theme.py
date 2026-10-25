"""Shared theme constants and utilities for chart/diagram renderers."""

import os
import re

# Palette selection. "brand" (default) keeps every accent slot inside the site's own
# primary (sky) scale plus slate greys, so figures read as part of khaledzaky.com
# instead of a generic chart kit, and every text/fill pairing the renderers draw meets
# WCAG AA in light and dark (agent/tests/test_chart_fixes.py measures each one).
# "classic" is the older eight-hue set with its original colours, for anyone who opts
# back in (CHART_STYLE=classic); its headers fall below AA (white on sky-600 is 4.1:1, on the dark-mode 400 tints
# about 2:1). Every renderer takes colour only through the tokens below, so switching
# palettes changes colour and nothing else: geometry and text are identical.
CHART_STYLE = os.environ.get("CHART_STYLE", "brand").strip().lower()

# Site-matching color palette (primary-600 variants work in both light and dark)
COLORS = [
    "#0284c7",  # primary-600 (sky blue)
    "#d97706",  # amber-600
    "#059669",  # emerald-600
    "#dc2626",  # red-600
    "#7c3aed",  # violet-600
    "#db2777",  # pink-600
    "#0891b2",  # cyan-600
    "#ea580c",  # orange-600
]

# Dark mode variants (brighter for dark backgrounds)
COLORS_DARK = [
    "#38bdf8",  # primary-400 (sky blue)
    "#fbbf24",  # amber-400
    "#34d399",  # emerald-400
    "#f87171",  # red-400
    "#a78bfa",  # violet-400
    "#f472b6",  # pink-400
    "#22d3ee",  # cyan-400
    "#fb923c",  # orange-400
]

# Tokens other than the accents. Classic values are the originals.
TOKENS = {
    "light": {"subtext": "#6b7280", "on-primary": "white", "on-accent": "white", "detail": "#bfdbfe",
              "item-bg": "#f0f9ff", "s1": "#e0f2fe", "s2": "#7dd3fc", "s3": "#0ea5e9", "s4": "#0369a1"},
    "dark": {"subtext": "#9ca3af", "on-primary": "white", "on-accent": "white", "detail": "#7dd3fc",
             "item-bg": "#0c4a6e", "s1": "#082f49", "s2": "#0c4a6e", "s3": "#075985", "s4": "#0369a1"},
}
# Stack layers deepen down the primary scale; text on them is --on-primary / --detail.
STACK_SHADES = ["#0284c7", "#0369a1", "#075985", "#0c4a6e", "#082f49", "#051e34", "#031525"]

# Brand palette. Light: primary-700/800, slate-700, slate-600, primary-900, slate-500,
# primary-500, primary-600. --c0 is primary-700, not 600: it fills headers that carry
# white text (5.9:1; on 600 it is 4.1:1, below AA) and colours labels on pale-blue cards.
BRAND_COLORS = ["#0369a1", "#075985", "#334155", "#475569", "#0c4a6e", "#64748b", "#0ea5e9", "#0284c7"]
# Dark: every slot is a light step, because renderers use the same tokens as TEXT and
# STROKE colours on dark cards (venn labels use --c1, convergence items --c0,
# architecture node outlines --c1/--c4/--c6). Text drawn ON a --c0/--c1 fill therefore
# uses --on-accent, which is deep navy in dark mode instead of white.
BRAND_COLORS_DARK = ["#38bdf8", "#7dd3fc", "#0ea5e9", "#94a3b8", "#bae6fd", "#cbd5e1", "#0284c7", "#64748b"]
BRAND_TOKENS = {
    "light": {"subtext": "#4b5563", "on-primary": "white", "on-accent": "white", "detail": "#e0f2fe",
              "item-bg": "#f0f9ff", "s1": "#f0f9ff", "s2": "#e0f2fe", "s3": "#bae6fd", "s4": "#0369a1"},
    "dark": {"subtext": "#cbd5e1", "on-primary": "white", "on-accent": "#082f49", "detail": "#e0f2fe",
             "item-bg": "#082f49", "s1": "#082f49", "s2": "#0c4a6e", "s3": "#075985", "s4": "#0369a1"},
}
BRAND_STACK_SHADES = ["#0369a1", "#075985", "#0c4a6e", "#082f49", "#051e34", "#031525", "#020f1c"]

if CHART_STYLE == "brand":
    COLORS = BRAND_COLORS
    COLORS_DARK = BRAND_COLORS_DARK
    TOKENS = BRAND_TOKENS
    STACK_SHADES = BRAND_STACK_SHADES

BG_COLOR = "#ffffff"
CARD_COLOR = "#f9fafb"  # gray-50
BORDER_COLOR = "#e5e7eb"  # gray-200
TEXT_COLOR = "#111827"  # gray-900
SUBTEXT_COLOR = "#6b7280"  # gray-500
MUTED_COLOR = "#9ca3af"  # gray-400
FONT_FAMILY = "Inter Variable, Inter, system-ui, -apple-system, sans-serif"
FONT_FAMILY_TITLE = "Lora Variable, Lora, Georgia, serif"

# Dark mode equivalents
BG_COLOR_DARK = "#030712"  # gray-950
CARD_COLOR_DARK = "#111827"  # gray-900
BORDER_COLOR_DARK = "#1f2937"  # gray-800
TEXT_COLOR_DARK = "#f9fafb"  # gray-50
SUBTEXT_COLOR_DARK = "#9ca3af"  # gray-400
MUTED_COLOR_DARK = "#6b7280"  # gray-500


def _dark_mode_style():
    """Generate a <style> block with CSS custom properties for dark mode support."""
    lt, dk = TOKENS["light"], TOKENS["dark"]
    return f"""<style>
  :root {{
    --bg: {BG_COLOR}; --card: {CARD_COLOR}; --border: {BORDER_COLOR};
    --text: {TEXT_COLOR}; --subtext: {lt["subtext"]}; --muted: {MUTED_COLOR};
    --c0: {COLORS[0]}; --c1: {COLORS[1]}; --c2: {COLORS[2]}; --c3: {COLORS[3]};
    --c4: {COLORS[4]}; --c5: {COLORS[5]}; --c6: {COLORS[6]}; --c7: {COLORS[7]};
    --on-primary: {lt["on-primary"]}; --on-accent: {lt["on-accent"]}; --detail: {lt["detail"]}; --item-bg: {lt["item-bg"]};
    --s1: {lt["s1"]}; --s2: {lt["s2"]}; --s3: {lt["s3"]}; --s4: {lt["s4"]};
  }}
  .dark svg {{
    --bg: {BG_COLOR_DARK}; --card: {CARD_COLOR_DARK}; --border: {BORDER_COLOR_DARK};
    --text: {TEXT_COLOR_DARK}; --subtext: {dk["subtext"]}; --muted: {MUTED_COLOR_DARK};
    --c0: {COLORS_DARK[0]}; --c1: {COLORS_DARK[1]}; --c2: {COLORS_DARK[2]}; --c3: {COLORS_DARK[3]};
    --c4: {COLORS_DARK[4]}; --c5: {COLORS_DARK[5]}; --c6: {COLORS_DARK[6]}; --c7: {COLORS_DARK[7]};
    --on-primary: {dk["on-primary"]}; --on-accent: {dk["on-accent"]}; --detail: {dk["detail"]}; --item-bg: {dk["item-bg"]};
    --s1: {dk["s1"]}; --s2: {dk["s2"]}; --s3: {dk["s3"]}; --s4: {dk["s4"]};
  }}
</style>"""


def scope_svg(svg):
    """Scope the figure's CSS variables to its own <svg> element.

    BlogPost.astro inlines every SVG into the page, so a ``:root { --c0: ... }`` rule in
    one figure set the colours of EVERY figure on the page, and the inline order (each
    figure is fetched asynchronously) decided which palette won. A content-hash class
    gives each figure its own selector: ``svg.kzc-<hash>`` and ``.dark svg.kzc-<hash>``."""
    import hashlib

    cls = "kzc-" + hashlib.sha1(svg.encode()).hexdigest()[:10]
    svg = svg.replace("<svg ", f'<svg class="{cls}" ', 1)
    svg = re.sub(r"(?m)^(\s*):root\s*\{", rf"\1svg.{cls} {{", svg)
    return re.sub(r"(?m)^(\s*)\.dark svg\s*\{", rf"\1.dark svg.{cls} {{", svg)


def _text_lines(text, box_width_px, font_size=12):
    """Split text into ≤2 lines that fit within box_width_px at font_size.
    Uses ~0.6 × font_size per character as a rough Inter estimate."""
    char_w = font_size * 0.6
    max_chars = max(int(box_width_px / char_w), 8)
    if len(text) <= max_chars:
        return [text]
    mid = len(text) // 2
    for delta in range(mid):
        if text[mid - delta] == " ":
            return [text[:mid - delta].strip(), text[mid - delta:].strip()]
        if mid + delta < len(text) and text[mid + delta] == " ":
            return [text[:mid + delta].strip(), text[mid + delta:].strip()]
    return [text[:max_chars], text[max_chars:]]


def _wrap_text(text, box_width_px, font_size=12, max_lines=4):
    """Greedy word-wrap: split text into lines that fit within box_width_px.
    Returns a list of at most max_lines strings. The last line is truncated
    with '…' if words remain after max_lines are filled."""
    char_w = font_size * 0.6
    max_chars = max(int(box_width_px / char_w), 8)
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines = []
    i = 0
    while i < len(words) and len(lines) < max_lines:
        line_words = []
        line_len = 0
        while i < len(words):
            w = words[i]
            candidate = line_len + (1 if line_words else 0) + len(w)
            if candidate <= max_chars:
                line_words.append(w)
                line_len = candidate
                i += 1
            else:
                break
        if not line_words:
            line_words = [words[i][:max_chars]]
            i += 1
        line = " ".join(line_words)
        if i < len(words) and len(lines) == max_lines - 1:
            line = (line[: max_chars - 1] + "…") if len(line) >= max_chars else line + "…"
        lines.append(line)
    return lines


def _escape_xml(text):
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
