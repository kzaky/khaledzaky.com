"""Shared theme constants and utilities for chart/diagram renderers."""

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

BG_COLOR = "#ffffff"
CARD_COLOR = "#f9fafb"  # gray-50
BORDER_COLOR = "#e5e7eb"  # gray-200
TEXT_COLOR = "#111827"  # gray-900
SUBTEXT_COLOR = "#6b7280"  # gray-500
MUTED_COLOR = "#9ca3af"  # gray-400
FONT_FAMILY = "Inter Variable, Inter, system-ui, -apple-system, sans-serif"

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
  }}
  .dark svg {{
    --bg: {BG_COLOR_DARK}; --card: {CARD_COLOR_DARK}; --border: {BORDER_COLOR_DARK};
    --text: {TEXT_COLOR_DARK}; --subtext: {SUBTEXT_COLOR_DARK}; --muted: {MUTED_COLOR_DARK};
    --c0: {COLORS_DARK[0]}; --c1: {COLORS_DARK[1]}; --c2: {COLORS_DARK[2]}; --c3: {COLORS_DARK[3]};
    --c4: {COLORS_DARK[4]}; --c5: {COLORS_DARK[5]}; --c6: {COLORS_DARK[6]}; --c7: {COLORS_DARK[7]};
    --on-primary: white; --detail: #7dd3fc; --item-bg: #0c4a6e;
  }}
</style>"""


def _escape_xml(text):
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
