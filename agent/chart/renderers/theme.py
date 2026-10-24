"""Shared theme constants and utilities for chart/diagram renderers."""

import os

# Palette selection. "classic" (default) is the eight-hue set below. "brand" keeps every
# accent slot inside the site's own primary (sky) scale plus slate greys, so figures read
# as part of khaledzaky.com instead of a generic chart kit (95c5bef restyled a post's
# diagrams by hand for exactly this). Every renderer takes colour only through the
# --c0..--c7 tokens below, so switching palettes changes colour and nothing else:
# geometry and text are identical. Set CHART_STYLE=brand on the Chart Lambda to opt in.
CHART_STYLE = os.environ.get("CHART_STYLE", "classic").strip().lower()

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

# Brand palette: primary-600/800/700, slate-600, primary-900, slate-500, primary-500,
# slate-700. Slots that carry white text (--c0, --c1 headers) stay dark enough for it.
BRAND_COLORS = ["#0284c7", "#075985", "#0369a1", "#475569", "#0c4a6e", "#64748b", "#0ea5e9", "#334155"]
# Dark: every slot is a light step, because renderers use the same tokens as TEXT and
# STROKE colours on dark cards (venn labels use --c1, convergence items --c0,
# architecture node outlines --c1/--c4/--c6). That mirrors the classic palette, whose
# dark slots are all 400-level tints; it also means white text on a header fill is
# low-contrast in dark mode, in both palettes alike.
BRAND_COLORS_DARK = ["#38bdf8", "#7dd3fc", "#0ea5e9", "#94a3b8", "#bae6fd", "#cbd5e1", "#0284c7", "#64748b"]

if CHART_STYLE == "brand":
    COLORS = BRAND_COLORS
    COLORS_DARK = BRAND_COLORS_DARK

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
    return f"""<style>
  :root {{
    --bg: {BG_COLOR}; --card: {CARD_COLOR}; --border: {BORDER_COLOR};
    --text: {TEXT_COLOR}; --subtext: {SUBTEXT_COLOR}; --muted: {MUTED_COLOR};
    --c0: {COLORS[0]}; --c1: {COLORS[1]}; --c2: {COLORS[2]}; --c3: {COLORS[3]};
    --c4: {COLORS[4]}; --c5: {COLORS[5]}; --c6: {COLORS[6]}; --c7: {COLORS[7]};
    --on-primary: white; --detail: #bfdbfe; --item-bg: #f0f9ff;
    --s1: #e0f2fe; --s2: #7dd3fc; --s3: #0ea5e9; --s4: #0369a1;
  }}
  .dark svg {{
    --bg: {BG_COLOR_DARK}; --card: {CARD_COLOR_DARK}; --border: {BORDER_COLOR_DARK};
    --text: {TEXT_COLOR_DARK}; --subtext: {SUBTEXT_COLOR_DARK}; --muted: {MUTED_COLOR_DARK};
    --c0: {COLORS_DARK[0]}; --c1: {COLORS_DARK[1]}; --c2: {COLORS_DARK[2]}; --c3: {COLORS_DARK[3]};
    --c4: {COLORS_DARK[4]}; --c5: {COLORS_DARK[5]}; --c6: {COLORS_DARK[6]}; --c7: {COLORS_DARK[7]};
    --on-primary: white; --detail: #7dd3fc; --item-bg: #0c4a6e;
    --s1: #082f49; --s2: #0c4a6e; --s3: #075985; --s4: #0369a1;
  }}
</style>"""


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
