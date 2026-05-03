#!/usr/bin/env python3
"""
Sangbog – tilføj en sang fra Ultimate Guitar

Brug:
  python add_song.py                   # auto-scan downloads/ for nye sange
  python add_song.py <fil.html>        # tilføj specifik fil

Transponering: tilføj _+N eller _-N til filnavnet før .html
  fx: the-cure_boys-dont-cry_+3.html  → transponer op 3 halvtoner

Tip: Gem UG-siden manuelt med Ctrl+U → Ctrl+A → Ctrl+S i din browser.
"""
import sys
import json
import re
import html
from pathlib import Path
from datetime import date

import requests
from bs4 import BeautifulSoup

SONGS_DIR = Path("songs")

# Akkord-diagram tooltip (injiceres i hvert sang-HTML)
# Format i DB: [E6, A5, D4, G3, B2, e1]  (-1=muted/x, 0=åben, N=fretnummer)
CHORD_DIAGRAM_HTML = """  <style>
    #chord-tip {
      position: fixed; z-index: 9999;
      background: white; border: 1px solid #ccc;
      border-radius: 5px; padding: 5px 7px 4px;
      box-shadow: 0 2px 8px rgba(0,0,0,.2);
      pointer-events: none; text-align: center;
    }
    .tip-name { font-family: sans-serif; font-size: 9pt; font-weight: bold; color: #333; margin-bottom: 2px; }
    @media print { #chord-tip { display: none !important; } }
  </style>
  <script>
  (function() {
    var DB = {
      'C':[-1,3,2,0,1,0],'C#':[-1,4,6,6,6,4],'Db':[-1,4,6,6,6,4],
      'D':[-1,-1,0,2,3,2],'D#':[-1,-1,1,3,4,3],'Eb':[-1,-1,1,3,4,3],
      'E':[0,2,2,1,0,0],
      'F':[1,3,3,2,1,1],'F#':[2,4,4,3,2,2],'Gb':[2,4,4,3,2,2],
      'G':[3,2,0,0,0,3],'G#':[4,6,6,5,4,4],'Ab':[4,6,6,5,4,4],
      'A':[-1,0,2,2,2,0],'A#':[-1,1,3,3,3,1],'Bb':[-1,1,3,3,3,1],
      'B':[-1,2,4,4,4,2],
      'Am':[-1,0,2,2,1,0],'A#m':[-1,1,3,3,2,1],'Bbm':[-1,1,3,3,2,1],
      'Bm':[-1,2,4,4,3,2],
      'Cm':[-1,3,5,5,4,3],'C#m':[-1,4,6,6,5,4],'Dbm':[-1,4,6,6,5,4],
      'Dm':[-1,-1,0,2,3,1],'D#m':[-1,-1,1,3,4,2],'Ebm':[-1,-1,1,3,4,2],
      'Em':[0,2,2,0,0,0],'Fm':[1,3,3,1,1,1],'F#m':[2,4,4,2,2,2],'Gbm':[2,4,4,2,2,2],
      'Gm':[3,5,5,3,3,3],'G#m':[4,6,6,4,4,4],'Abm':[4,6,6,4,4,4],
      'A7':[-1,0,2,0,2,0],'B7':[-1,2,1,2,0,2],'C7':[-1,3,2,3,1,0],
      'D7':[-1,-1,0,2,1,2],'E7':[0,2,0,1,0,0],'F7':[1,3,1,2,1,1],
      'G7':[3,2,0,0,0,1],
      'Am7':[-1,0,2,0,1,0],'Bm7':[-1,2,4,2,3,2],
      'Cm7':[-1,3,5,3,4,3],'Dm7':[-1,-1,0,2,1,1],
      'Em7':[0,2,2,0,3,0],'Fm7':[1,3,1,1,1,1],
      'F#m7':[2,4,2,2,2,2],'Gm7':[3,5,3,3,3,3],
      'Cmaj7':[-1,3,2,0,0,0],'Dmaj7':[-1,-1,0,2,2,2],
      'Emaj7':[0,2,1,1,0,0],'Fmaj7':[-1,0,3,2,1,0],
      'Gmaj7':[3,2,0,0,0,2],'Amaj7':[-1,0,2,1,2,0],
      'Dsus2':[-1,-1,0,2,3,0],'Dsus4':[-1,-1,0,2,3,3],
      'Asus2':[-1,0,2,2,0,0],'Asus4':[-1,0,2,2,3,0],
      'Esus4':[0,2,2,2,0,0],
      'Cadd9':[-1,3,2,0,3,3],'Gadd9':[3,2,0,2,0,3],
      'D/F#':[2,-1,0,2,3,2],'G/B':[-1,2,0,0,3,3],
      'C/G':[3,3,2,0,1,0],'E/G#':[4,-1,2,1,0,0],
      'A/C#':[-1,4,2,2,2,0],'Am/E':[0,0,2,2,1,0]
    };
    function baseFret(f) {
      var pos = f.filter(function(x) { return x > 0; });
      if (!pos.length) return 1;
      var m = Math.min.apply(null, pos);
      return (f.some(function(x) { return x === 0; }) || m <= 2) ? 1 : m;
    }
    function makeSVG(frets) {
      var base = baseFret(frets), nF = 4, nS = 6, sw = 10, fh = 13;
      var gw = sw * (nS - 1), gh = fh * nF, ox = 12, oy = 20;
      var hasLbl = base > 2, nut = base <= 2 ? 3 : 0;
      var tw = gw + ox * 2 + (hasLbl ? 20 : 0), th = gh + oy + 6;
      var s = '<svg xmlns="http://www.w3.org/2000/svg" width="' + tw + '" height="' + th + '">';
      s += '<rect width="' + tw + '" height="' + th + '" fill="white"/>';
      for (var i = 0; i < nS; i++) {
        var x = ox + i * sw, fi = frets[i];
        if (fi === -1)
          s += '<text x="' + x + '" y="' + (oy-5) + '" text-anchor="middle" font-size="9" font-family="sans-serif" fill="#aaa">x</text>';
        else if (fi === 0)
          s += '<circle cx="' + x + '" cy="' + (oy-8) + '" r="3.5" fill="none" stroke="#aaa" stroke-width="1.2"/>';
      }
      if (nut)
        s += '<rect x="' + ox + '" y="' + oy + '" width="' + gw + '" height="' + nut + '" fill="#333" rx="1"/>';
      else
        s += '<text x="' + (ox+gw+4) + '" y="' + (oy+fh*0.75) + '" font-size="8" font-family="sans-serif" fill="#aaa">' + base + 'fr</text>';
      var y0 = oy + nut;
      for (var r = 0; r <= nF; r++) {
        var y = y0 + r * fh;
        s += '<line x1="' + ox + '" y1="' + y + '" x2="' + (ox+gw) + '" y2="' + y + '" stroke="#ddd" stroke-width="0.8"/>';
      }
      for (var j = 0; j < nS; j++) {
        var xs = ox + j * sw;
        s += '<line x1="' + xs + '" y1="' + y0 + '" x2="' + xs + '" y2="' + (y0+gh) + '" stroke="#ddd" stroke-width="0.8"/>';
      }
      for (var k = 0; k < nS; k++) {
        var fv = frets[k], row = fv - base;
        if (fv > 0 && row >= 0 && row < nF) {
          var cx = ox + k * sw, cy = y0 + row * fh + fh / 2;
          s += '<circle cx="' + cx + '" cy="' + cy + '" r="' + (fh*0.38) + '" fill="#b00020"/>';
        }
      }
      return s + '</svg>';
    }
    var tip = null;
    function lookup(name) {
      if (DB[name]) return DB[name];
      var sl = name.indexOf('/');
      return sl > 0 && DB[name.slice(0, sl)] ? DB[name.slice(0, sl)] : null;
    }
    function show(el, name) {
      var frets = lookup(name);
      if (!frets) return;
      hide();
      tip = document.createElement('div');
      tip.id = 'chord-tip';
      var lbl = document.createElement('div');
      lbl.className = 'tip-name';
      lbl.textContent = name;
      tip.appendChild(lbl);
      var d = document.createElement('div');
      d.innerHTML = makeSVG(frets);
      tip.appendChild(d);
      document.body.appendChild(tip);
      var rect = el.getBoundingClientRect(), tw2 = tip.offsetWidth, th2 = tip.offsetHeight;
      var left = rect.left + (rect.width - tw2) / 2, top = rect.top - th2 - 6;
      if (top < 4) top = rect.bottom + 6;
      left = Math.max(4, Math.min(left, window.innerWidth - tw2 - 4));
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    }
    function hide() { if (tip) { tip.remove(); tip = null; } }
    document.addEventListener('DOMContentLoaded', function() {
      document.querySelectorAll('.chord').forEach(function(el) {
        el.addEventListener('mouseenter', function() { show(el, el.textContent.trim()); });
        el.addEventListener('mouseleave', hide);
      });
    });
  })();
  </script>"""
DOWNLOADS_DIR = Path("downloads")
INDEX_FILE = Path("index.html")
SONGS_DATA = Path("songs.json")

# Transponering
SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


def shift_note(note: str, semitones: int) -> str:
    scale = FLATS if 'b' in note else SHARPS
    try:
        idx = scale.index(note)
    except ValueError:
        return note
    return scale[(idx + semitones) % 12]


def transpose_chord(chord_str: str, semitones: int) -> str:
    m = re.match(r'^([A-G][#b]?)(.*?)(/([A-G][#b]?))?$', chord_str)
    if not m:
        return chord_str
    root, quality, bass = m.group(1), m.group(2), m.group(4)
    result = shift_note(root, semitones) + (quality or '')
    if bass:
        result += '/' + shift_note(bass, semitones)
    return result


def transpose_content(content: str, semitones: int) -> str:
    if semitones == 0:
        return content
    return re.sub(
        r'\[ch\](.*?)\[/ch\]',
        lambda m: f'[ch]{transpose_chord(m.group(1), semitones)}[/ch]',
        content,
    )


def parse_transpose(filename: str) -> int:
    m = re.search(r'_([+-]\d+)\.html$', filename)
    return int(m.group(1)) if m else 0


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def unwrap_view_source(html_text: str) -> str:
    """Hvis filen er gemt fra browserens view-source visning, udpak den rå HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    cells = soup.find_all("td", class_="line-content")
    if not cells:
        return html_text
    return "\n".join(cell.get_text() for cell in cells)


def extract_ug_data(html_text: str) -> dict:
    html_text = unwrap_view_source(html_text)
    soup = BeautifulSoup(html_text, "html.parser")

    # Nuværende format: JSON i data-content på .js-store
    el = soup.find(class_="js-store")
    if el and el.get("data-content"):
        return json.loads(el["data-content"])

    # Ældre format: window.UGAPP_DATA i script-tag
    for script in soup.find_all("script"):
        text = script.string or ""
        if "window.UGAPP_DATA" in text:
            m = re.search(r"window\.UGAPP_DATA\s*=\s*(\{.+\})\s*;", text, re.DOTALL)
            if m:
                return json.loads(m.group(1))

    raise ValueError(
        "Kunne ikke finde sangdata. Er det en Ultimate Guitar akkord-side?"
    )


def get_song_info(data: dict) -> tuple:
    # Nuværende format: data -> store -> page -> data
    page_data = (
        data.get("store", {}).get("page", {}).get("data")
        or data.get("data")
        or {}
    )

    tab = page_data.get("tab", {})
    tab_view = page_data.get("tab_view", {})

    title = tab.get("song_name", "Ukendt sang")
    artist = tab.get("artist_name", "Ukendt artist")
    key = tab.get("tonality_name", "") or ""
    capo = str(tab.get("capo", "") or "")

    content = (
        (tab_view.get("wiki_tab") or {}).get("content")
        or tab.get("content")
        or ""
    )
    return title, artist, key, capo, content


def parse_sections(content: str) -> list:
    """Split content into [(header, body)] pairs with blank lines removed."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"\[/?tab\]", "", content)
    parts = re.split(r"(\[[A-Z][^\]]*\])", content)
    sections = []
    current_header = ""
    for part in parts:
        if re.match(r"^\[[A-Z][^\]]*\]$", part):
            current_header = part
        else:
            body = part.strip("\n")
            if body.strip():
                sections.append((current_header, body))
            current_header = ""
    return sections


def is_tab_section(body: str) -> bool:
    """True if body contains guitar string notation (e|, B|, etc.)."""
    return bool(re.search(r"^[eBGDAE]\|", body, re.MULTILINE))


def split_mixed(header: str, body: str) -> list:
    """Split a section that mixes chord+lyric and guitar tab into two parts."""
    lines = body.split("\n")
    tab_start = next(
        (i for i, l in enumerate(lines) if re.match(r"^[eBGDAE]\|", l)), None
    )
    if tab_start is None:
        return [(header, body)]
    # Include any preceding blank/label lines with the tab block
    while tab_start > 0 and not re.search(r"\[ch\]", lines[tab_start - 1]):
        tab_start -= 1
    chord_part = "\n".join(lines[:tab_start]).strip()
    tab_part = "\n".join(lines[tab_start:]).strip()
    result = []
    if chord_part:
        result.append((header, chord_part))
    if tab_part:
        result.append(("", tab_part))
    return result


def count_lines(sections: list) -> tuple:
    """Return (total_non_blank_lines, max_line_width) ignoring tab sections."""
    total, max_width = 0, 0
    for header, body in sections:
        if is_tab_section(body):
            continue
        if header:
            total += 1
        for line in body.split("\n"):
            if line.strip():
                total += 1
                if "[ch]" in line:  # kun akkordlinjer tæller for bredde
                    clean = re.sub(r"\[ch\](.*?)\[/ch\]", r"\1", line)
                    max_width = max(max_width, len(clean))
    return total, max_width


def decide_layout(total_lines: int, max_width: int) -> str:
    if total_lines <= 65:
        return "single"
    elif total_lines <= 120 and max_width <= 65:
        return "double"
    else:
        return "multi"


def render_section(header: str, body: str, remove_blank_lines: bool = False) -> str:
    if remove_blank_lines:
        body = re.sub(r"\n[ \t]*\n", "\n", body)
    escaped_body = html.escape(body.lstrip("\n"))
    styled = re.sub(r"\[ch\](.*?)\[/ch\]", r'<span class="chord">\1</span>', escaped_body)
    header_html = f'<span class="section">{html.escape(header)}</span>\n' if header else ""
    return f'<pre class="block">{header_html}{styled}</pre>'


def content_to_html(content: str) -> tuple:
    sections = parse_sections(content)
    # Split mixed sections (chord+lyric + tab) into separate parts
    split = []
    for h, b in sections:
        split.extend(split_mixed(h, b))

    chord_sections = [(h, b) for h, b in split if not is_tab_section(b)]
    tab_sections = [(h, b) for h, b in split if is_tab_section(b)]

    total_lines, max_width = count_lines(chord_sections)
    layout = decide_layout(total_lines, max_width)

    chord_blocks = "\n".join(render_section(h, b, remove_blank_lines=True) for h, b in chord_sections)
    tab_blocks = "\n".join(render_section(h, b, remove_blank_lines=False) for h, b in tab_sections)

    return chord_blocks, tab_blocks, layout


def make_song_html(
    title: str, artist: str, key: str, capo: str, content: str, url: str
) -> tuple:
    chord_blocks, tab_blocks, layout = content_to_html(content)

    meta_parts = []
    if key:
        meta_parts.append(f"Toneart: {key}")
    if capo:
        meta_parts.append(f"Capo: {capo}")
    if url:
        meta_parts.append(
            f'Kilde: <a href="{url}">{html.escape(url[:70])}{"..." if len(url) > 70 else ""}</a>'
        )
    meta_parts.append(f"Tilføjet: {date.today().strftime('%d.%m.%Y')}")
    meta_html = " &nbsp;·&nbsp; ".join(meta_parts)

    double_css = ""
    wrap_open, wrap_close = "", ""
    if layout == "double":
        double_css = "\n    .chords { column-count: 2; column-gap: 8mm; }"
        wrap_open = '<div class="chords">'
        wrap_close = "</div>"

    tab_html = ""
    if tab_blocks.strip():
        tab_html = f'<div class="tab-section">{tab_blocks}</div>'

    page = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(title)} – {html.escape(artist)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: monospace; background: #ddd; padding: 24px; }}
    .page {{
      background: white;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 12mm 14mm;
    }}
    h1 {{ font-size: 15pt; font-family: sans-serif; margin-bottom: 3px; }}
    h2 {{ font-size: 10pt; font-family: sans-serif; font-weight: normal; color: #555; margin-bottom: 8px; }}
    .meta {{
      font-size: 7.5pt; font-family: sans-serif; color: #999;
      border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-bottom: 10px;
    }}
    .meta a {{ color: #999; }}
    pre.block {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 9pt; line-height: 1.45;
      white-space: pre-wrap; word-break: break-word;
      margin-bottom: 6px;
    }}{double_css}
    .tab-section {{ margin-top: 8mm; }}
    .chord {{ color: #b00020; font-weight: bold; cursor: help; }}
    .section {{ color: #777; font-style: italic; font-weight: bold; }}
    @media print {{
      body {{ background: white; padding: 0; }}
      .page {{ width: auto; min-height: auto; padding: 0; margin: 0; box-shadow: none; }}
      @page {{ size: A4; margin: 12mm 14mm; }}
      pre.block {{ break-inside: avoid; }}
      .tab-section {{ break-before: page; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>{html.escape(title)}</h1>
    <h2>{html.escape(artist)}</h2>
    <div class="meta">{meta_html}</div>
    {wrap_open}
    {chord_blocks}
    {wrap_close}
    {tab_html}
  </div>
</body>
</html>"""
    return page.replace("</head>", CHORD_DIAGRAM_HTML + "\n</head>", 1), layout


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[æ]", "ae", text)
    text = re.sub(r"[ø]", "oe", text)
    text = re.sub(r"[å]", "aa", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_songs() -> list:
    if SONGS_DATA.exists():
        return json.loads(SONGS_DATA.read_text())
    return []


def save_songs(songs: list) -> None:
    SONGS_DATA.write_text(json.dumps(songs, ensure_ascii=False, indent=2))


def processed_sources() -> set:
    return {s["source"] for s in load_songs() if "source" in s}


def rebuild_index(songs: list) -> None:
    items = "\n    ".join(
        f'<li><a href="songs/{s["file"]}">{html.escape(s["artist"])} – {html.escape(s["title"])}</a></li>'
        for s in sorted(songs, key=lambda s: (s["artist"].lower(), s["title"].lower()))
    )
    index_html = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <title>Sangbog</title>
  <style>
    body {{ font-family: sans-serif; max-width: 560px; margin: 48px auto; padding: 0 20px; color: #222; }}
    h1 {{ font-size: 28pt; margin-bottom: 24px; }}
    ul {{ list-style: none; padding: 0; }}
    li {{ border-bottom: 1px solid #eee; }}
    a {{ display: block; padding: 10px 4px; text-decoration: none; color: #222; font-size: 11pt; }}
    a:hover {{ color: #b00020; }}
  </style>
</head>
<body>
  <h1>Sangbog</h1>
  <ul>
    {items}
  </ul>
</body>
</html>"""
    INDEX_FILE.write_text(index_html, encoding="utf-8")


def process_file(ug_path: Path, url: str = "") -> None:
    page_html = ug_path.read_text(encoding="utf-8", errors="replace")
    data = extract_ug_data(page_html)
    title, artist, key, capo, content = get_song_info(data)

    semitones = parse_transpose(ug_path.name)
    if semitones:
        content = transpose_content(content, semitones)
        print(f"  Fundet:  {artist} – {title} (transponeret {semitones:+d} halvtoner)")
    else:
        print(f"  Fundet:  {artist} – {title}")

    SONGS_DIR.mkdir(exist_ok=True)
    filename = f"{slugify(artist)}-{slugify(title)}.html"
    filepath = SONGS_DIR / filename

    song_html, layout = make_song_html(title, artist, key, capo, content, url)
    filepath.write_text(song_html, encoding="utf-8")
    layout_msg = {"single": "1 kolonne", "double": "2 kolonner", "multi": "flere sider"}
    print(f"  Layout:  {layout_msg[layout]}")
    print(f"  Gemt:    {filepath}")

    songs = load_songs()
    existing = next((s for s in songs if s["file"] == filename), None)
    entry = {"title": title, "artist": artist, "file": filename, "source": ug_path.name}
    if existing:
        existing.update(entry)
    else:
        songs.append(entry)
    save_songs(songs)
    rebuild_index(songs)


def main():
    DOWNLOADS_DIR.mkdir(exist_ok=True)

    if len(sys.argv) == 1:
        # Auto-scan downloads/ for nye filer
        done = processed_sources()
        new_files = [f for f in sorted(DOWNLOADS_DIR.glob("*.html")) if f.name not in done]
        if not new_files:
            print("Ingen nye sange i downloads/ — sangbogen er opdateret.")
            return
        print(f"Fandt {len(new_files)} ny(e) sang(e) i downloads/:")
        for f in new_files:
            print(f"\n→ {f.name}")
            process_file(f)
        print(f"\nIndeks opdateret: {INDEX_FILE}")

    elif len(sys.argv) == 2:
        arg = sys.argv[1]
        if Path(arg).exists():
            print(f"→ {arg}")
            process_file(Path(arg))
            print(f"Indeks opdateret: {INDEX_FILE}")
        else:
            url = arg
            print(f"Henter {url} ...")
            page_html = fetch_page(url)
            tmp = Path("_tmp_ug.html")
            tmp.write_text(page_html, encoding="utf-8")
            process_file(tmp)
            tmp.unlink()
            print(f"Indeks opdateret: {INDEX_FILE}")

    elif len(sys.argv) == 3:
        print(f"→ {sys.argv[1]}")
        process_file(Path(sys.argv[1]), url=sys.argv[2])
        print(f"Indeks opdateret: {INDEX_FILE}")

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
