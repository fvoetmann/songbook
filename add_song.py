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
DOWNLOADS_DIR = Path("downloads")

# ── Instrumentkonfigurationer ────────────────────────────────────────────────
# strings: MIDI-notenumre fra tykkeste til tyndeste streng
# Ukulele: re-entrant G (G4=67 er højere end C4=60)
# Mandolin: GDAE ligesom violin
STRING_OPEN = [40, 45, 50, 55, 59, 64]  # beholdes for bagudkompatibilitet
MAX_FRET = 9

INSTRUMENTS = {
    'guitar':   {'strings': [40, 45, 50, 55, 59, 64], 'max_fret': 9, 'min_play': 4, 'span': 2},
    'ukulele':  {'strings': [67, 60, 64, 69],          'max_fret': 7, 'min_play': 4, 'span': 3, 'reentrant': True},
    'mandolin': {'strings': [55, 62, 69, 76],          'max_fret': 7, 'min_play': 3, 'span': 3},
}

NOTE_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
ACCIDENTAL = {'#': 1, 'b': -1}

# Akkordtype-suffixer → intervaller fra rod (sorteret på længde, længst først)
CHORD_TYPES = sorted([
    ('mmaj7',   [0, 3, 7, 11]),
    ('m(maj7)', [0, 3, 7, 11]),
    ('maj7',    [0, 4, 7, 11]),
    ('maj9',    [0, 2, 4, 7, 11]),
    ('7sus4',   [0, 5, 7, 10]),
    ('dim7',    [0, 3, 6, 9]),
    ('sus2',    [0, 2, 7]),
    ('sus4',    [0, 5, 7]),
    ('add9',    [0, 2, 4, 7]),
    ('aug',     [0, 4, 8]),
    ('dim',     [0, 3, 6]),
    ('m7',      [0, 3, 7, 10]),
    ('m6',      [0, 3, 7, 9]),
    ('m9',      [0, 2, 3, 7, 10]),
    ('maj',     [0, 4, 7]),
    ('m',       [0, 3, 7]),
    ('7',       [0, 4, 7, 10]),
    ('6',       [0, 4, 7, 9]),
    ('9',       [0, 2, 4, 7, 10]),
    ('5',       [0, 7]),
    ('',        [0, 4, 7]),
], key=lambda x: -len(x[0]))


def parse_chord_name(name: str):
    """Returnér (rod_semi, intervaller, bas_semi|None) eller None."""
    bass_semi = None
    slash = name.find('/')
    if slash > 0:
        b = name[slash + 1:]
        if b and b[0] in NOTE_SEMI:
            bass_semi = NOTE_SEMI[b[0]]
            if len(b) > 1 and b[1] in ACCIDENTAL:
                bass_semi = (bass_semi + ACCIDENTAL[b[1]]) % 12
        name = name[:slash]

    if not name or name[0] not in NOTE_SEMI:
        return None
    root = NOTE_SEMI[name[0]]
    i = 1
    if i < len(name) and name[i] in ACCIDENTAL:
        root = (root + ACCIDENTAL[name[i]]) % 12
        i += 1

    suffix = name[i:]
    for suf, ivs in CHORD_TYPES:
        if suffix == suf:
            return root, ivs, bass_semi
    return None


def generate_voicings(root: int, ivs: list, bass=None, n: int = 6, instr: dict = None) -> list:
    """Top-n spillbare greb som liste af frets (-1=muted, 0=åben, N=fret)."""
    from itertools import product as iproduct

    if instr is None:
        instr = INSTRUMENTS['guitar']
    string_open = instr['strings']
    n_str = len(string_open)
    max_fret = instr['max_fret']
    min_play = instr['min_play']
    max_span = instr['span']

    tones = {(root + i) % 12 for i in ivs}

    opts = []
    for s in range(n_str):
        o = {-1}
        for t in tones:
            diff = (t - string_open[s]) % 12
            if diff <= max_fret:
                o.add(diff)
        opts.append(sorted(o))

    valid = []
    for combo in iproduct(*opts):
        fs = list(combo)
        playing = [f for f in fs if f >= 0]

        if len(playing) < min_play:
            continue

        pressed = [f for f in fs if f > 0]
        if pressed and max(pressed) - min(pressed) > max_span:
            continue

        played = {(string_open[s] + fs[s]) % 12 for s in range(n_str) if fs[s] >= 0}

        if root % 12 not in played:
            continue
        if len(ivs) > 1 and (root + ivs[1]) % 12 not in played:
            continue

        if bass is not None:
            # Laveste absolutte tonehøjde skal være basnoden (virker med re-entrant tuning)
            lo_abs = min(string_open[s] + fs[s] for s in range(n_str) if fs[s] >= 0)
            if lo_abs % 12 != bass % 12:
                continue

        valid.append(fs)

    if not valid:
        return []

    def score(fs):
        played = {(string_open[s] + fs[s]) % 12 for s in range(n_str) if fs[s] >= 0}
        pressed = [f for f in fs if f > 0]
        first = next((i for i in range(n_str) if fs[i] >= 0), n_str)
        last = next((i for i in range(n_str - 1, -1, -1) if fs[i] >= 0), -1)
        gaps = sum(1 for i in range(first, last + 1) if fs[i] == -1)
        if instr.get('reentrant') or bass is not None:
            inv = 0
        else:
            lo_abs = min(string_open[s] + fs[s] for s in range(n_str) if fs[s] >= 0)
            inv = 0 if lo_abs % 12 == root % 12 else 1
        n_play = sum(1 for f in fs if f >= 0)
        position = min(pressed) if pressed else 0
        return (
            -len(played & tones) / len(tones),
            gaps,
            inv,
            position,
            -n_play,
            sum(f for f in fs if f >= 0),
        )

    valid.sort(key=score)

    seen, result = set(), []
    for v in valid:
        k = tuple(v)
        if k not in seen:
            seen.add(k)
            result.append(v)
            if len(result) == n:
                break
    return result


def extract_chord_names(content: str) -> list:
    """Unikke akkordnavne i førstegangs-rækkefølge."""
    seen, result = set(), []
    for m in re.finditer(r'\[ch\](.*?)\[/ch\]', content):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def build_voicings_db(chord_names: list, instr: dict = None) -> dict:
    """{akkordnavn: [[frets], ...]} for alle akkorder i sangen."""
    db = {}
    for name in chord_names:
        parsed = parse_chord_name(name)
        if parsed is None:
            continue
        voicings = generate_voicings(*parsed, instr=instr)
        if voicings:
            db[name] = voicings
    return db


def build_all_voicings_dbs(chord_names: list) -> dict:
    """{instrument: {akkordnavn: [[frets], ...]}} for alle instrumenter."""
    return {name: build_voicings_db(chord_names, instr=cfg) for name, cfg in INSTRUMENTS.items()}


# ── Akkord-diagram HTML/JS (injiceres i hvert sang-HTML) ────────────────────
CHORD_DIAGRAM_STYLE = """  <style>
    #chord-tip {
      position: fixed; z-index: 9999;
      background: white; border: 1px solid #ccc;
      border-radius: 5px; padding: 5px 7px 4px;
      box-shadow: 0 2px 8px rgba(0,0,0,.2);
      pointer-events: none; text-align: center;
    }
    .tip-name { font-family: sans-serif; font-size: 9pt; font-weight: bold; color: #333; margin-bottom: 2px; }
    #inst-bar {
      position: fixed; bottom: 16px; right: 16px; z-index: 9998;
      background: white; border: 1px solid #ccc; border-radius: 5px;
      padding: 4px 8px; box-shadow: 0 2px 6px rgba(0,0,0,.15);
      font-family: sans-serif; font-size: 8pt;
      display: flex; gap: 2px; align-items: center;
    }
    #inst-bar span { color: #aaa; margin-right: 4px; }
    .inst-btn {
      border: none; background: none; cursor: pointer;
      padding: 2px 6px; font-size: 8pt; font-family: sans-serif;
      border-radius: 3px; color: #555;
    }
    .inst-btn.active { font-weight: bold; color: #b00020; }
    @media print { #chord-tip { display: none !important; } #inst-bar { display: none !important; } }
  </style>"""

CHORD_DIAGRAM_JS = """  <script>
  (function() {
    var DBS = %s;
    var inst = 'guitar';
    var shown = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
    function baseFret(f) {
      var pos = f.filter(function(x) { return x > 0; });
      if (!pos.length) return 1;
      var m = Math.min.apply(null, pos);
      return (f.some(function(x) { return x === 0; }) || m <= 2) ? 1 : m;
    }
    function makeSVG(frets) {
      var nS = frets.length, sw = nS <= 4 ? 14 : 10;
      var base = baseFret(frets), nF = 4, fh = 13;
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
        else
          s += '<circle cx="' + x + '" cy="' + (oy-8) + '" r="2.5" fill="#b00020"/>';
      }
      if (nut)
        s += '<rect x="' + ox + '" y="' + oy + '" width="' + gw + '" height="' + nut + '" fill="#333" rx="1"/>';
      else
        s += '<text x="' + (ox+gw+4) + '" y="' + (oy+fh*0.75) + '" font-size="8" font-family="sans-serif" font-weight="bold" fill="#555">' + base + 'fr</text>';
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
    function dist(a, b) {
      var d = 0;
      for (var i = 0; i < a.length; i++) {
        if (a[i] >= 0 && b[i] >= 0) d += Math.abs(a[i] - b[i]);
        else if (a[i] !== b[i]) d += 2;
      }
      return d;
    }
    function best(vs, prev) {
      if (!prev || vs.length === 1) return vs[0];
      var pick = vs[0], d = dist(pick, prev);
      for (var i = 1; i < vs.length; i++) {
        var di = dist(vs[i], prev);
        if (di < d) { pick = vs[i]; d = di; }
      }
      return pick;
    }
    function lookup(name) {
      var db = DBS[inst] || {};
      if (db[name]) return db[name];
      var sl = name.indexOf('/');
      return (sl > 0 && db[name.slice(0,sl)]) ? db[name.slice(0,sl)] : null;
    }
    function prevEl(el) {
      var block = el.closest('pre.block');
      if (!block) return null;
      var all = Array.from(block.querySelectorAll('.chord'));
      var i = all.indexOf(el);
      return i > 0 ? all[i - 1] : null;
    }
    var tip = null;
    function show(el, name) {
      var vs = lookup(name);
      if (!vs) return;
      var prev = prevEl(el);
      var prevF = (prev && shown) ? shown.get(prev) : null;
      var frets = best(vs, prevF || null);
      if (shown) shown.set(el, frets);
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
      var r = el.getBoundingClientRect(), tw2 = tip.offsetWidth, th2 = tip.offsetHeight;
      var left = r.left + (r.width - tw2) / 2, top = r.top - th2 - 6;
      if (top < 4) top = r.bottom + 6;
      left = Math.max(4, Math.min(left, window.innerWidth - tw2 - 4));
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    }
    function hide() { if (tip) { tip.remove(); tip = null; } }
    function setInst(name) {
      inst = name;
      if (shown) shown = new WeakMap();
      hide();
      document.querySelectorAll('.inst-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.inst === name);
      });
    }
    document.addEventListener('DOMContentLoaded', function() {
      var bar = document.createElement('div');
      bar.id = 'inst-bar';
      var lbl = document.createElement('span');
      lbl.textContent = 'Instrument:';
      bar.appendChild(lbl);
      [['guitar','Guitar'],['ukulele','Ukulele'],['mandolin','Mandolin']].forEach(function(p) {
        var b = document.createElement('button');
        b.textContent = p[1]; b.dataset.inst = p[0]; b.className = 'inst-btn';
        b.addEventListener('click', function() { setInst(p[0]); });
        bar.appendChild(b);
      });
      document.body.appendChild(bar);
      setInst('guitar');
      document.querySelectorAll('.chord').forEach(function(el) {
        el.addEventListener('mouseenter', function() { show(el, el.textContent.trim()); });
        el.addEventListener('mouseleave', hide);
      });
    });
  })();
  </script>"""


def make_chord_diagram_html(chord_names: list) -> str:
    all_dbs = build_all_voicings_dbs(chord_names)
    return CHORD_DIAGRAM_STYLE + "\n" + (CHORD_DIAGRAM_JS % json.dumps(all_dbs, separators=(',', ':')))
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
    diagram_html = make_chord_diagram_html(extract_chord_names(content))

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
    return page.replace("</head>", diagram_html + "\n</head>", 1), layout


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
