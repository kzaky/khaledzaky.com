"""Chart and diagram renderers for the blog agent."""

from .architecture import render_architecture_diagram
from .bar import render_bar_chart
from .comparison import render_comparison_diagram
from .convergence import render_convergence_diagram
from .pie import render_pie_chart
from .progression import render_progression_diagram
from .stack import render_stack_diagram
from .theme import COLORS, COLORS_DARK, FONT_FAMILY, _dark_mode_style, _escape_xml, _text_lines
from .timeline import render_timeline_diagram
from .venn import render_venn_diagram

__all__ = [
    "COLORS", "COLORS_DARK", "FONT_FAMILY",
    "_dark_mode_style", "_escape_xml", "_text_lines",
    "render_bar_chart", "render_pie_chart",
    "render_architecture_diagram", "render_comparison_diagram",
    "render_convergence_diagram", "render_progression_diagram",
    "render_stack_diagram", "render_timeline_diagram", "render_venn_diagram",
]
