"""Shared plotting helpers, styling, and HTML report generator."""

import os
import re
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from config import OUTPUT_DIR

# Patterns that identify per-video/per-window plots (collapsible)
_PER_VIDEO_PATTERNS = [
    re.compile(r"^timeline_"),
    re.compile(r"^odometry_"),
    re.compile(r"^head_pose_\d"),
    re.compile(r"^speed_\d"),
    re.compile(r"^route_"),
    re.compile(r"^gaze_timeline_"),
    re.compile(r"^lane_count_timeline_"),
]

# Plots to render at half width in a grid
_HALF_WIDTH_PATTERNS = [
    re.compile(r"^clips_"),
    re.compile(r"^event_"),
    re.compile(r"^events_per"),
    re.compile(r"^labeled_split"),
    re.compile(r"^safety_overall"),
    re.compile(r"^safety_by_"),
    re.compile(r"^gaze_distribution"),
    re.compile(r"^gaze_transitions"),
    re.compile(r"^lane_coverage"),
    re.compile(r"^speed_at_events"),
]


def _is_per_video(stem):
    return any(p.match(stem) for p in _PER_VIDEO_PATTERNS)


def _is_half_width(stem):
    return any(p.match(stem) for p in _HALF_WIDTH_PATTERNS)


def _group_per_video(items):
    """Group per-video items by prefix (e.g. timeline, odometry, head_pose)."""
    groups = {}
    for item in items:
        stem = item.stem
        # Extract prefix: everything before the first video ID pattern (YYYY_MMDD)
        m = re.match(r"^(.+?)_?\d{4}_\d{4}", stem)
        prefix = m.group(1) if m else stem
        # Clean up prefix for display
        prefix = prefix.rstrip("_").replace("_", " ").title()
        groups.setdefault(prefix, []).append(item)
    return groups


def setup_style():
    """Apply consistent matplotlib/seaborn style."""
    sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "figure.figsize": (10, 6),
        "axes.titlesize": 14,
        "axes.labelsize": 12,
    })


def save_figure(fig, name, subdir=None):
    """Save a matplotlib figure to OUTPUT_DIR (or a subdir) as PNG."""
    out = OUTPUT_DIR / subdir if subdir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def generate_html_report(title, sections, output_path=None):
    """
    Generate a compact HTML report with collapsible per-video sections.

    Parameters
    ----------
    title : str
        Page title.
    sections : list[dict]
        Each dict has keys: "heading" (str), "items" (list of Path),
        optionally "html_content" (str).
    output_path : Path, optional
        Defaults to OUTPUT_DIR / "index.html".
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "<!DOCTYPE html>",
        "<html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{title}</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
        f"<p class='timestamp'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    ]

    # Navigation
    lines.append("<nav class='nav'>")
    for sec in sections:
        anchor = sec["heading"].lower().replace(" ", "-")
        lines.append(f"<a href='#{anchor}'>{sec['heading']}</a>")
    lines.append("</nav>")

    for sec in sections:
        anchor = sec["heading"].lower().replace(" ", "-")
        lines.append(f"<h2 id='{anchor}'>{sec['heading']}</h2>")

        items = [Path(p) for p in sec.get("items", [])]

        # Separate key plots from per-video plots
        key_items = [p for p in items if not _is_per_video(p.stem)]
        per_video_items = [p for p in items if _is_per_video(p.stem)]

        # Render key plots — half-width grid where applicable
        if key_items:
            _render_key_items(lines, key_items)

        # Inline HTML content (tables etc.)
        if "html_content" in sec and sec["html_content"]:
            lines.append("<div class='html-content'>")
            lines.append(sec["html_content"])
            lines.append("</div>")

        # Render per-video plots in collapsible groups
        if per_video_items:
            groups = _group_per_video(per_video_items)
            for group_name, group_items in groups.items():
                lines.append(
                    f"<details class='per-video'>"
                    f"<summary>{group_name} ({len(group_items)} videos)</summary>"
                    f"<div class='per-video-grid'>"
                )
                for item in sorted(group_items, key=lambda p: p.stem):
                    rel = _rel_path(item)
                    if item.suffix.lower() == ".png":
                        lines.append(
                            f"<div class='per-video-card'>"
                            f"<div class='card-label'>{_short_label(item.stem)}</div>"
                            f"<img src='{rel}' alt='{item.stem}' loading='lazy'>"
                            f"</div>"
                        )
                    elif item.suffix.lower() == ".html":
                        lines.append(
                            f"<div class='per-video-card'>"
                            f"<a href='{rel}'>{_short_label(item.stem)}</a>"
                            f"</div>"
                        )
                lines.append("</div></details>")

    lines.append("</body></html>")
    output_path.write_text("\n".join(lines))
    return output_path


def _render_key_items(lines, items):
    """Render key (non-per-video) items, using grid for half-width items."""
    # Collect consecutive half-width items into grid batches
    in_grid = False
    for item in items:
        is_half = _is_half_width(item.stem)
        rel = _rel_path(item)

        if is_half and not in_grid:
            lines.append("<div class='grid-2'>")
            in_grid = True
        elif not is_half and in_grid:
            lines.append("</div>")
            in_grid = False

        if item.suffix.lower() == ".png":
            css = "img-half" if is_half else "img-full"
            lines.append(
                f"<div class='{css}'>"
                f"<div class='fig-label'>{_pretty_name(item.stem)}</div>"
                f"<img src='{rel}' alt='{item.stem}'>"
                f"</div>"
            )
        elif item.suffix.lower() == ".html":
            lines.append(f"<p><a href='{rel}'>{_pretty_name(item.stem)}</a> (interactive map)</p>")
        else:
            lines.append(f"<p><a href='{rel}'>{item.name}</a></p>")

    if in_grid:
        lines.append("</div>")


def _rel_path(item):
    try:
        return item.relative_to(OUTPUT_DIR)
    except ValueError:
        return item


def _pretty_name(stem):
    """Convert stem like 'prf1_bar' to 'Prf1 Bar'."""
    return stem.replace("_", " ").title()


def _short_label(stem):
    """Extract just the video ID from stems like 'timeline_2025_0902_153636_004649F'."""
    m = re.search(r"(\d{4}_\d{4}_\d{6}_\d{6}F?)", stem)
    return m.group(1) if m else stem.replace("_", " ").title()


_CSS = """
  * { box-sizing: border-box; }
  body {
    font-family: system-ui, -apple-system, sans-serif;
    max-width: 1400px; margin: 0 auto; padding: 20px;
    background: #f8f9fa; color: #222;
  }
  h1 { border-bottom: 2px solid #333; padding-bottom: 8px; font-size: 1.6em; }
  h2 { margin-top: 36px; color: #333; font-size: 1.3em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  .timestamp { color: #888; font-size: 0.85em; margin-top: -8px; }
  a { color: #0366d6; }

  .nav {
    background: #fff; padding: 10px 14px; border: 1px solid #ddd;
    border-radius: 6px; margin-bottom: 20px; position: sticky; top: 0; z-index: 10;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }
  .nav a { margin-right: 16px; font-weight: 500; font-size: 0.95em; white-space: nowrap; }

  img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; display: block; }
  .fig-label { font-size: 0.85em; font-weight: 600; color: #555; margin-bottom: 2px; }

  /* Grid for half-width key plots */
  .grid-2 {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    margin: 8px 0;
  }
  .img-half { }
  .img-full { margin: 10px 0; max-width: 900px; }

  /* HTML content (tables etc.) */
  .html-content { margin: 12px 0; overflow-x: auto; }
  .html-content table { font-size: 0.85em; }

  /* Collapsible per-video sections */
  details.per-video {
    margin: 10px 0; border: 1px solid #ddd; border-radius: 6px;
    background: #fff;
  }
  details.per-video summary {
    padding: 8px 14px; cursor: pointer; font-weight: 600;
    font-size: 0.95em; color: #444; user-select: none;
    background: #f0f2f5; border-radius: 6px;
  }
  details.per-video[open] summary {
    border-bottom: 1px solid #ddd; border-radius: 6px 6px 0 0;
  }
  .per-video-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 10px; padding: 10px;
  }
  .per-video-card {
    border: 1px solid #eee; border-radius: 4px; padding: 6px;
    background: #fafafa;
  }
  .per-video-card img { width: 100%; }
  .card-label { font-size: 0.8em; font-weight: 600; color: #666; margin-bottom: 2px; font-family: monospace; }

  @media (max-width: 800px) {
    .grid-2 { grid-template-columns: 1fr; }
    .per-video-grid { grid-template-columns: 1fr; }
  }
"""
