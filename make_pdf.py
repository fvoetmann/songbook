#!/usr/bin/env python3
"""Generate a PDF songbook with a table of contents and page numbers."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pypdf

SONGS_DIR = Path(__file__).parent / "songs"
SONGS_JSON = Path(__file__).parent / "songs.json"
OUTPUT_PDF = Path(__file__).parent / "songbook.pdf"


def find_weasyprint() -> str:
    wp = shutil.which("weasyprint")
    if not wp:
        sys.exit("weasyprint not found in PATH")
    return wp


def render_html_to_pdf(weasyprint: str, html_path: Path, pdf_path: Path):
    result = subprocess.run(
        [weasyprint, str(html_path), str(pdf_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(f"weasyprint failed on {html_path}")


def count_pages(pdf_path: Path) -> int:
    return len(pypdf.PdfReader(str(pdf_path)).pages)


COMBINED_CSS_OVERRIDES = """
<style>
pre.block { break-inside: auto !important; }
.tab-section { break-before: auto !important; }
</style>"""


def inject_overrides(html: str) -> str:
    """Inject the same CSS overrides used in the combined render, for accurate page counting."""
    return html.replace("</head>", COMBINED_CSS_OVERRIDES + "\n</head>", 1)


def extract_first_style(html: str) -> str:
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>", start)
    css = html[start:end]
    # Replace the body-scoped font-small selector so it works on a div in the combined doc
    css = css.replace("body.font-small ", ".font-small ")
    return css


def extract_body_content(html: str) -> str:
    """Return the inner HTML of <body>, with the body class moved to .page div."""
    m = re.search(r"<body([^>]*)>", html)
    body_class = ""
    if m:
        cm = re.search(r'class="([^"]*)"', m.group(1))
        if cm:
            body_class = cm.group(1)
    start = html.index(">", html.index("<body")) + 1
    end = html.rindex("</body>")
    content = html[start:end].strip()
    # Inject the body class onto the .page div so per-song font sizes are preserved
    if body_class:
        content = content.replace('<div class="page">', f'<div class="page {body_class}">', 1)
    return content


def make_toc_body(entries: list[dict]) -> str:
    rows = []
    current_artist = None
    for e in entries:
        if e["artist"] != current_artist:
            current_artist = e["artist"]
            first = "first-artist" if not rows else ""
            rows.append(
                f'<tr class="artist-row {first}"><td colspan="2">{current_artist}</td></tr>'
            )
        rows.append(
            f'<tr><td class="title">{e["title"]}</td>'
            f'<td class="pgnum">{e["page"]}</td></tr>'
        )
    rows_html = "\n".join(rows)
    return f'  <h1>Indholdsfortegnelse</h1>\n  <table>\n{rows_html}\n  </table>'


def make_toc_html_standalone(entries: list[dict]) -> str:
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: sans-serif; background: white; }}
    h1 {{ font-size: 18pt; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
    .artist-row td {{
      font-weight: bold; font-size: 11pt; color: #b00020;
      padding: 9px 0 2px; border-top: 1px solid #ddd;
    }}
    .first-artist td {{ border-top: none; padding-top: 0; }}
    td.title {{ padding: 1px 0 1px 12px; }}
    td.pgnum {{ text-align: right; color: #666; white-space: nowrap; }}
    @media print {{ @page {{ size: A4; margin: 12mm 14mm; }} }}
  </style>
</head>
<body>
{make_toc_body(entries)}
</body>
</html>"""


def make_combined_html(entries: list[dict], song_bodies: list[str], shared_css: str) -> str:
    toc = make_toc_body(entries)
    songs_html = "\n".join(song_bodies)
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <title>Sangbog</title>
  <style>
{shared_css}
    /* Page numbers */
    @page {{
      @bottom-center {{
        content: counter(page);
        font-family: sans-serif;
        font-size: 8pt;
        color: #888;
      }}
    }}
    /* TOC */
    #toc h1 {{ font-size: 18pt; margin-bottom: 14px; font-family: sans-serif; }}
    #toc table {{ width: 100%; border-collapse: collapse; font-size: 10pt; font-family: sans-serif; }}
    #toc .artist-row td {{
      font-weight: bold; font-size: 11pt; color: #b00020;
      padding: 9px 0 2px; border-top: 1px solid #ddd;
    }}
    #toc .first-artist td {{ border-top: none; padding-top: 0; }}
    #toc td.title {{ padding: 1px 0 1px 12px; }}
    #toc td.pgnum {{ text-align: right; color: #666; white-space: nowrap; }}
    /* Two-column layout (only applies when .chords wrapper is present) */
    .chords {{ column-count: 2; column-gap: 8mm; }}
    /* Each song starts on a new page */
    .page {{ break-before: page; }}
    /* Allow large pre blocks to split across pages rather than being pushed to the next page whole */
    pre.block {{ break-inside: auto; }}
    /* Allow tab sections to flow naturally rather than always forcing a page break */
    .tab-section {{ break-before: auto; }}
  </style>
</head>
<body>
<div id="toc">
{toc}
</div>
{songs_html}
</body>
</html>"""


def assign_pages(song_pdfs: list[dict], toc_pages: int) -> list[dict]:
    result = []
    page = toc_pages + 1
    for s in song_pdfs:
        result.append({**s, "page": page})
        page += s["n_pages"]
    return result


def main():
    weasyprint = find_weasyprint()

    with open(SONGS_JSON, encoding="utf-8") as f:
        songs = json.load(f)

    songs = sorted(songs, key=lambda s: (s["artist"].lower(), s["title"].lower()))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Render each song to a temp PDF to count pages, and extract HTML content
        song_pdfs = []
        shared_css = None
        for i, song in enumerate(songs):
            html_path = SONGS_DIR / song["file"]
            if not html_path.exists():
                print(f"Warning: missing {song['file']}, skipping")
                continue
            html = html_path.read_text(encoding="utf-8")
            if shared_css is None:
                shared_css = extract_first_style(html)
            pdf_path = tmp / f"song_{i:04d}.pdf"
            print(f"  {song['artist']} – {song['title']}")
            modified_html_path = tmp / f"song_{i:04d}.html"
            modified_html_path.write_text(inject_overrides(html), encoding="utf-8")
            render_html_to_pdf(weasyprint, modified_html_path, pdf_path)
            song_pdfs.append({
                "title": song["title"],
                "artist": song["artist"],
                "body": extract_body_content(html),
                "n_pages": count_pages(pdf_path),
            })

        # Two-pass TOC: measure TOC page count, then finalize page numbers
        toc_pages = 1
        for _ in range(2):
            entries = assign_pages(song_pdfs, toc_pages)
            toc_html = make_toc_html_standalone(entries)
            toc_html_path = tmp / "toc.html"
            toc_pdf_path = tmp / "toc.pdf"
            toc_html_path.write_text(toc_html, encoding="utf-8")
            render_html_to_pdf(weasyprint, toc_html_path, toc_pdf_path)
            measured = count_pages(toc_pdf_path)
            if measured == toc_pages:
                break
            toc_pages = measured

        # Render combined document (TOC + all songs) in one pass for page numbers
        song_bodies = [s["body"] for s in song_pdfs]
        combined_html = make_combined_html(entries, song_bodies, shared_css)
        combined_html_path = tmp / "combined.html"
        combined_html_path.write_text(combined_html, encoding="utf-8")
        print("\nRendering final PDF...")
        render_html_to_pdf(weasyprint, combined_html_path, OUTPUT_PDF)

    total_pages = toc_pages + sum(s["n_pages"] for s in song_pdfs)
    print(f"Gemt: {OUTPUT_PDF}  ({total_pages} sider)")


if __name__ == "__main__":
    main()
