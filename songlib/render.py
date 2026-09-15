"""Rendering af sang-HTML (linjer, sektioner, sider og den fulde make_song_html)."""

import html
import json
import re

from .bars import (
    build_bar_timeline_json,
    extract_chord_sequence,
    find_label_for_header,
    is_bars_draft_section,
    is_bars_section,
    match_section,
    parse_bars_meta,
)
from .chords import extract_chord_names
from .layout import (
    LINES_PER_PAGE,
    count_lines,
    decide_layout,
    is_tab_section,
    paginate_sections,
    parse_sections,
    split_mixed,
)
from .templates import make_chord_diagram_html


def is_chord_only_line(line: str) -> bool:
    """True if line consists solely of [ch]...[/ch] chords and whitespace."""
    stripped = re.sub(r"\[ch\](.*?)\[/ch\]", "", line)
    return "[ch]" in line and not stripped.strip()


def is_chord_annotation_line(line: str) -> bool:
    """True if line is a chord row (at least two [ch] tags) carrying only a
    short non-lyric annotation alongside its chords - a bar divider ("|"),
    a repeat marker ("x2", "repeat"), a "(+F#)" passing-chord note, etc.
    Distinguishes an annotated chord row from a real lyric line that merely
    contains an embedded chord, so it can still be paired with the lyric
    line it precedes (see render_chord_lines)."""
    if line.count("[ch]") < 2:
        return False
    leftover = re.sub(r"\[ch\](.*?)\[/ch\]", "", line).strip()
    return bool(leftover) and len(leftover.split()) <= 3 and len(leftover) <= 24


def chord_positions_align(chord_line: str, lyric_line: str) -> bool:
    """True if chord_line's chords land on real word boundaries in
    lyric_line (position 0, or preceded by whitespace), with no more than
    two trailing chords past the end of the (shorter) lyric line. A
    chord-annotation line's character columns only mean anything relative
    to a lyric line when the two were actually written to align
    (per-syllable UG charts); a bar-measure/strumming-pattern chart ("| G
    Gsus4 G Gsus4 |") paired with an unrelated short lyric line either
    lands mid-word or - since parse_chord_positions's columns only ever
    increase - runs almost entirely past the end of that line, which is
    the signal used here to reject a bogus pairing (a chord or two
    trailing past the last word, as in an optional passing chord, is
    normal and allowed)."""
    overflow = 0
    for pos, _ in parse_chord_positions(chord_line):
        if pos == 0:
            continue
        if pos > len(lyric_line):
            overflow += 1
            continue
        if not lyric_line[pos - 1].isspace():
            return False
    return overflow <= 2


def group_lines(lines: list) -> list:
    """Group lines so a chord-only line stays together with the lyric lines
    that follow it, until the next chord-only line. This keeps each group
    intact when columns/pages break, so a column never starts mid-lyric."""
    groups = []
    current = []
    for line in lines:
        if is_chord_only_line(line) and current:
            groups.append(current)
            current = []
        current.append(line)
    if current:
        groups.append(current)
    return groups or [[]]


def parse_chord_positions(chord_line: str) -> list:
    """Extract (column, chord_name) pairs from a chord-only line, where
    column is the character position with [ch]/[/ch] tags stripped out."""
    chords = []
    col, i = 0, 0
    while i < len(chord_line):
        if chord_line[i:i + 4] == "[ch]":
            end = chord_line.find("[/ch]", i)
            if end != -1:
                name = chord_line[i + 4:end]
                chords.append((col, name))
                col += len(name)
                i = end + 5
                continue
        col += 1
        i += 1
    return chords


def _render_extra_bar(bar) -> str:
    """A synthesized rest/repeat bar with no [ch] occurrence of its own to
    anchor to. Rendered as a bare barline+mark pair (no "chord"/"lyr" class)
    so it can be dropped straight into a <span class="seg"> right after the
    chord it follows - it then rides along on the seg's chord row (see the
    ".seg"/".seg .lyr" flex-wrap rule) instead of dropping onto its own line,
    and edit_song.py's line_div_to_ug reconstruction (which only ever looks
    up the "chord"/"lyr" classes) skips it automatically."""
    cls = "rest" if bar.is_rest else "repeat"
    glyph = "·" if bar.is_rest else "%"
    return (
        '<span class="barline" data-derived="bars"></span>'
        f'<span class="barmark {cls}">{glyph}</span>'
    )


def render_chord_lyric_line(
    chord_line: str, lyric_line: str, bar_match=None, start_idx: int = 0, chord_idx_base: int = 0
) -> tuple:
    """Render a chord-only line paired with the lyric line it aligns to as
    a sequence of <span class="seg"> stacks (chord above the exact lyric
    slice it precedes), so alignment works under a proportional font.

    Returns (html, next_idx) where next_idx is start_idx plus the number of
    chord occurrences consumed, so callers can keep a running occurrence
    index across a whole section for bar_match lookups."""
    chords = parse_chord_positions(chord_line)
    parts = []
    if chords[0][0] > 0:
        parts.append((None, lyric_line[:chords[0][0]], None))
    for idx, (pos, name) in enumerate(chords):
        end = chords[idx + 1][0] if idx + 1 < len(chords) else len(lyric_line)
        end = max(end, pos)
        text = lyric_line[pos:end] if pos < len(lyric_line) else ""
        parts.append((name, text, start_idx + idx))

    pieces = []
    for name, text, occ in parts:
        prefix = ""
        extra = ""
        if bar_match is not None and occ is not None:
            if occ in bar_match.bar_starts:
                prefix = '<span class="barline" data-derived="bars"></span>'
            for bar in bar_match.extra_after.get(occ, []):
                extra += _render_extra_bar(bar)
        idx_attr = f' data-idx="{chord_idx_base + occ}"' if (bar_match is not None and occ is not None) else ""
        chord_html = f'<span class="chord"{idx_attr}>{html.escape(name)}</span>' if name else ""
        lyr_html = f'<span class="lyr">{html.escape(text)}</span>' if (text or name) else ""
        # extra (repeat/rest marks) sits between chord and lyr so it rides on
        # the chord row (right after the chord it repeats) rather than after
        # the full lyric text - see the ".seg"/".seg .lyr" flex-wrap rule.
        pieces.append(f'{prefix}<span class="seg">{chord_html}{extra}{lyr_html}</span>')
    return f'<div class="line">{"".join(pieces)}</div>', start_idx + len(chords)


def render_chord_lines(lines: list, bar_match=None, start_idx: int = 0, chord_idx_base: int = 0) -> tuple:
    """Render a group's lines: pair each chord-only (or chord+annotation)
    line with the plain lyric line directly below it (position-anchored),
    render standalone chord-only lines (no lyric to align to) as a simple
    chord row, and plain lines as-is.

    Returns (html, next_idx): next_idx is the running chord-occurrence index
    after this group, so render_section can chain it across groups within a
    section (bar_match's occurrence indices are section-global)."""
    out = []
    idx = start_idx
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if is_chord_only_line(line) and nxt.strip() and not is_chord_only_line(nxt) and "[ch]" not in nxt:
            rendered, idx = render_chord_lyric_line(line, nxt, bar_match, idx, chord_idx_base)
            out.append(rendered)
            i += 2
            continue
        if (
            is_chord_annotation_line(line)
            and nxt.strip()
            and "[ch]" not in nxt
            and len(nxt.split()) >= 2
            and chord_positions_align(line, nxt)
        ):
            rendered, idx = render_chord_lyric_line(line, nxt, bar_match, idx, chord_idx_base)
            out.append(rendered)
            i += 2
            continue
        if is_chord_only_line(line):
            positions = parse_chord_positions(line)
            spans = []
            for local_i, (_, name) in enumerate(positions):
                occ = idx + local_i
                if bar_match is not None and occ in bar_match.bar_starts:
                    spans.append('<span class="barline" data-derived="bars"></span>')
                idx_attr = f' data-idx="{chord_idx_base + occ}"' if bar_match is not None else ""
                spans.append(f'<span class="chord"{idx_attr}>{html.escape(name)}</span>')
                if bar_match is not None:
                    for extra in bar_match.extra_after.get(occ, []):
                        spans.append(_render_extra_bar(extra))
            out.append(f'<div class="line chords-only">{"".join(spans)}</div>')
            idx += len(positions)
        else:
            counter = [idx]

            def _sub(m):
                occ = counter[0]
                counter[0] += 1
                idx_attr = f' data-idx="{chord_idx_base + occ}"' if bar_match is not None else ""
                return f'<span class="chord"{idx_attr}>{m.group(1)}</span>'

            styled = re.sub(r"\[ch\](.*?)\[/ch\]", _sub, html.escape(line))
            out.append(f'<div class="line"><span class="seg"><span class="lyr">{styled}</span></span></div>')
            idx = counter[0]
        i += 1
    return "\n".join(out), idx


def render_section(
    header: str,
    body: str,
    remove_blank_lines: bool = False,
    is_tab: bool = False,
    bar_match=None,
    chord_idx_base: int = 0,
) -> tuple:
    """Returns (html, chord_count) where chord_count is the number of real
    chord occurrences rendered (0 for tab sections) - callers with a
    bar_match use it to advance their running global chord-index counter
    (see content_to_html), which the embedded data-idx attributes rely on
    to stay in sync with the JS-side bass/highlight playback."""
    if remove_blank_lines:
        body = re.sub(r"\n[ \t]*\n", "\n", body)
    groups = group_lines(body.lstrip("\n").split("\n"))

    blocks = []
    idx = 0
    for i, group in enumerate(groups):
        cls = "block line-group" + (" line-group-last" if i == len(groups) - 1 else "")
        if is_tab:
            escaped = html.escape("\n".join(group))
            styled = re.sub(r"\[ch\](.*?)\[/ch\]", r'<span class="chord">\1</span>', escaped)
            header_html = f'<span class="section">{html.escape(header)}</span>\n' if i == 0 and header else ""
            blocks.append(f'<pre class="{cls}">{header_html}{styled}</pre>')
        else:
            header_div = (
                f'<div class="line section-line"><span class="section">{html.escape(header)}</span></div>'
                if i == 0 and header else ""
            )
            group_html, idx = render_chord_lines(
                group, bar_match=bar_match, start_idx=idx, chord_idx_base=chord_idx_base
            )
            blocks.append(f'<div class="{cls}">{header_div}{group_html}</div>')
    return "\n".join(blocks), (0 if is_tab else idx)


def content_to_html(content: str) -> tuple:
    sections = parse_sections(content)
    # Split mixed sections (chord+lyric + tab) into separate parts
    split = []
    for h, b in sections:
        split.extend(split_mixed(h, b))

    bars_sections = [(h, b) for h, b in split if is_bars_section(h)]
    draft_sections = [(h, b) for h, b in split if is_bars_draft_section(h)]
    rest = [
        (h, b) for h, b in split
        if not is_bars_section(h) and not is_bars_draft_section(h)
    ]

    chord_sections = [(h, b) for h, b in rest if not is_tab_section(b)]
    tab_sections = [(h, b) for h, b in rest if is_tab_section(b)]

    bars_meta = {}
    for _, b in bars_sections:
        bars_meta.update(parse_bars_meta(b))

    # bar_matches keyed by chord_sections index, so it survives pagination
    # (which reorders sections into page buckets but preserves overall order).
    bar_matches = {}
    if bars_meta:
        for i, (h, b) in enumerate(chord_sections):
            label = find_label_for_header(h, bars_meta.keys())
            if label is None:
                continue
            result = match_section(bars_meta[label], extract_chord_sequence(b), h)
            if result is not None:
                bar_matches[i] = result

    has_bars = bool(bar_matches)
    # Preserve each [Bars]/[Bars draft] section as a verbatim, hidden <pre>,
    # header included (mirroring how tab sections embed their own header as
    # a <span class="section">) so edit_song.py's round-trip reconstructs the
    # exact "[Bars]\nLabel: ..." text rather than dropping the header line.
    # [Bars draft] sections are preserved the same way but never matched
    # above, so they stay inactive (no barlines) until renamed to [Bars].
    bars_source_html = "\n".join(
        f'<pre class="block bars-source" hidden><span class="section">{html.escape(h)}</span>\n{html.escape(b)}</pre>'
        for h, b in bars_sections + draft_sections if b.strip()
    )
    timeline = (
        build_bar_timeline_json(bar_matches.values())
        if bar_matches else None
    )

    total_lines, max_chord_width, max_text_width = count_lines(chord_sections)
    layout = decide_layout(total_lines, max_chord_width)
    use_columns = layout == "double" or (layout == "multi" and max_chord_width <= 65)
    auto_small_font = use_columns and max_text_width > 60

    if layout == "multi":
        lines_per_page = LINES_PER_PAGE * 2 if use_columns else LINES_PER_PAGE
        page_buckets = paginate_sections(chord_sections, lines_per_page=lines_per_page)
    else:
        page_buckets = [chord_sections]

    pages = []
    idx = 0
    chord_idx_counter = 0
    for bucket in page_buckets:
        rendered = []
        for h, b in bucket:
            match = bar_matches.get(idx)
            section_html, chord_count = render_section(
                h, b, remove_blank_lines=True, bar_match=match, chord_idx_base=chord_idx_counter
            )
            if match is not None:
                chord_idx_counter += chord_count
            rendered.append(section_html)
            idx += 1
        pages.append("\n".join(rendered))

    tab_blocks = "\n".join(
        render_section(h, b, remove_blank_lines=False, is_tab=True)[0] for h, b in tab_sections
    )

    return pages, tab_blocks, layout, auto_small_font, use_columns, has_bars, bars_source_html, timeline


def make_song_html(
    title: str, artist: str, key: str, capo: str, content: str, url: str, tempo: str = "120"
) -> tuple:
    tempo = (tempo or "").strip() or "120"
    pages, tab_blocks, layout, auto_small_font, use_columns, has_bars, bars_source_html, timeline = content_to_html(content)
    diagram_html = make_chord_diagram_html(extract_chord_names(content))

    meta_parts = []
    if key:
        meta_parts.append(f"Toneart: {key}")
    if capo:
        meta_parts.append(f"Capo: {capo}")
    if url:
        meta_parts.append(
            f'Kilde: <a href="{html.escape(url, quote=True)}">{html.escape(url[:70])}{"..." if len(url) > 70 else ""}</a>'
        )
    meta_html = " &nbsp;·&nbsp; ".join(meta_parts)
    meta_div = f'<div class="meta">{meta_html}</div>' if meta_html else ""

    double_css = ""
    wrap_open, wrap_close = "", ""
    if use_columns:
        double_css = (
            "\n    .chords { column-count: 2; column-gap: 8mm; }"
            "\n    @media (max-width: 640px), (max-height: 500px) and (orientation: landscape) {"
            " .chords { column-count: 1; } }"
        )
        wrap_open = '<div class="chords">'
        wrap_close = "</div>"

    tab_html = ""
    if tab_blocks.strip():
        tab_html = f'<div class="tab-section">{tab_blocks}</div>'

    bars_css = ""
    bars_extra_html = ""
    if has_bars:
        bars_css = (
            "\n    .barline { display: inline-block; align-self: flex-start; width: 1px; height: 1.1em;"
            " background: #ccc; margin: 0 5px; vertical-align: baseline; }"
            "\n    .barmark { color: #b00020; font-weight: bold; opacity: .6; font-size: 0.85em; line-height: 1.3; }"
            "\n    .barmark.rest { font-style: italic; }"
        )
    if bars_source_html:
        bars_extra_html += f"\n    {bars_source_html}"
    if timeline:
        bars_extra_html += (
            f'\n    <script type="application/json" id="bar-data">'
            f'{json.dumps(timeline, ensure_ascii=False)}</script>'
        )

    page_divs = []
    for i, page_content in enumerate(pages):
        is_first, is_last = i == 0, i == len(pages) - 1
        header_html = (
            f'<h1>{html.escape(title)} <span class="artist-inline">– {html.escape(artist)}</span></h1>\n    {meta_div}'
            if is_first else ""
        )
        page_divs.append(
            f'<div class="page">\n    {header_html}\n    {wrap_open}\n    {page_content}\n    {wrap_close}'
            f'\n    {tab_html if is_last else ""}\n  </div>'
        )
    pages_html = "\n".join(page_divs)

    page = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="tempo" content="{tempo}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;700&display=swap" rel="stylesheet">
  <title>{html.escape(title)} – {html.escape(artist)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Source Sans 3', sans-serif; background: #ddd; padding: 24px; }}
    .pages-wrap {{ display: flex; flex-direction: column; align-items: center; }}
    .page {{
      background: white;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 12mm 14mm 56px;
    }}
    @media screen and (min-width: 460mm) {{
      .pages-wrap {{ flex-direction: row; flex-wrap: wrap; justify-content: center; gap: 10mm; }}
      .page {{ margin: 0; box-shadow: 0 2px 10px rgba(0, 0, 0, .18); }}
    }}
    h1 {{ font-size: 15pt; font-family: sans-serif; margin-bottom: 6px; }}
    h1 .artist-inline {{ font-size: 10pt; font-weight: normal; color: #555; }}
    .meta {{
      font-size: 7.5pt; font-family: sans-serif; color: #999;
      border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-bottom: 10px;
    }}
    .meta a {{ color: #999; }}
    .block {{
      font-size: 9pt; line-height: 1.5;
      margin-bottom: 6px;
    }}
    .block.line-group {{ break-inside: avoid; margin-bottom: 0; }}
    .block.line-group-last {{ margin-bottom: 6px; }}
    body.font-small .block {{ font-size: 8pt; }}{double_css}{bars_css}
    pre.block {{
      font-family: ui-monospace, 'Courier New', Courier, monospace;
      white-space: pre-wrap; word-break: break-word;
    }}
    div.block {{ font-family: 'Source Sans 3', sans-serif; }}
    .line {{ display: flex; flex-wrap: wrap; align-items: flex-end; }}
    .line.chords-only .chord {{ margin-right: 1.4em; }}
    .seg {{ display: inline-block; }}
    .seg .lyr {{ display: block; white-space: pre; }}
    .seg .lyr:empty::before {{ content: "\\00a0"; }}
    .seg .chord {{ font-size: 0.85em; line-height: 1.3; }}
    .tab-section {{ margin-top: 8mm; }}
    .chord {{ color: #b00020; font-weight: bold; cursor: help; }}
    .chord.now-playing {{ background: #ffe98a; border-radius: 3px; box-shadow: 0 0 0 2px #ffe98a; }}
    .chord.start-marker {{ border-radius: 3px; box-shadow: 0 0 0 2px #1a73e8; }}
    .section {{ color: #777; font-style: italic; font-weight: bold; }}
    @media (max-width: 640px) {{
      body {{ background: white; padding: 0; }}
      .page {{ width: 100%; min-height: auto; padding: 12px 14px; }}
    }}
    @media print {{
      body {{ background: white; padding: 0; }}
      .pages-wrap {{ display: block; gap: 0; }}
      .page {{ width: auto; min-height: auto; padding: 0; margin: 0; box-shadow: none; }}
      .page + .page {{ break-before: page; }}
      @page {{ size: A4; margin: 12mm 14mm; }}
      .block {{ break-inside: avoid; }}
      .tab-section {{ break-before: page; }}
      .chord.now-playing {{ background: none; box-shadow: none; }}
      .chord.start-marker {{ box-shadow: none; }}
    }}
  </style>
</head>
<body{' class="font-small"' if auto_small_font else ''}>
  <div class="pages-wrap">
    {pages_html}{bars_extra_html}
  </div>
</body>
</html>"""
    return page.replace("</head>", diagram_html + "\n</head>", 1), layout, has_bars