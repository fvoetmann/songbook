"""Persistens og filbehandling: songs.json, index.html, sange-filer.

Indeholder load_songs/save_songs/rebuild_index samt process_file, der læser en
UG-side og skriver/opdaterer sang-HTML'en, songs.json og index.html.
"""

import hashlib
import html
import json
import re
from pathlib import Path

from .chords import parse_transpose, transpose_content
from .render import make_song_html
from .ug import extract_ug_data, get_song_info

SONGS_DIR = Path("songs")
DOWNLOADS_DIR = Path("downloads")
INDEX_FILE = Path("index.html")
SONGS_DATA = Path("songs.json")


def artist_sort_key(artist: str) -> str:
    """Sort key that ignores a leading 'The ' so e.g. 'The Beatles' sorts under B."""
    return re.sub(r"^the\s+", "", artist, flags=re.IGNORECASE).lower()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[æ]", "ae", text)
    text = re.sub(r"[ø]", "oe", text)
    text = re.sub(r"[å]", "aa", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_songs() -> list:
    if SONGS_DATA.exists():
        return json.loads(SONGS_DATA.read_text(encoding="utf-8"))
    return []


def save_songs(songs: list) -> None:
    SONGS_DATA.write_text(json.dumps(songs, ensure_ascii=False, indent=2))


def processed_sources() -> set:
    return {s["source"] for s in load_songs() if "source" in s}


def rebuild_index(songs: list) -> None:
    from itertools import groupby

    sorted_songs = sorted(songs, key=lambda s: (artist_sort_key(s["artist"]), s["title"].lower()))

    groups_html = []
    for artist, group in groupby(sorted_songs, key=lambda s: s["artist"]):
        group_songs = list(group)
        song_items = "\n      ".join(
            f'<li><a href="songs/{s["file"]}">{html.escape(s["title"])}</a></li>'
            for s in group_songs
        )
        groups_html.append(
            f'  <section>\n'
            f'    <h2>{html.escape(artist)}</h2>\n'
            f'    <ul>\n      {song_items}\n    </ul>\n'
            f'  </section>'
        )

    index_html = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sangbog</title>
  <style>
    body {{ font-family: sans-serif; max-width: 560px; margin: 48px auto; padding: 0 20px; color: #222; }}
    @media (max-width: 640px) {{ body {{ margin: 24px auto; }} }}
    h1 {{ font-size: 28pt; margin-bottom: 8px; }}
    #search {{
      display: block; width: 100%; padding: 8px 10px; margin-bottom: 28px;
      font-size: 11pt; font-family: sans-serif;
      border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;
    }}
    section {{ margin-bottom: 20px; }}
    h2 {{ font-size: 11pt; color: #999; font-weight: normal; margin-bottom: 2px; padding-bottom: 3px; border-bottom: 1px solid #eee; }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{ border-bottom: 1px solid #f5f5f5; }}
    a {{ display: block; padding: 7px 4px; text-decoration: none; color: #222; font-size: 11pt; }}
    a:hover {{ color: #b00020; }}
    section.hidden {{ display: none; }}
  </style>
</head>
<body>
  <h1>Sangbog</h1>
  <input id="search" type="search" placeholder="Søg efter sang eller kunstner…" autocomplete="off">
{chr(10).join(groups_html)}
  <script>
    var input = document.getElementById('search');
    input.addEventListener('input', function() {{
      var q = this.value.toLowerCase();
      document.querySelectorAll('section').forEach(function(sec) {{
        var artist = sec.querySelector('h2').textContent.toLowerCase();
        var matched = false;
        sec.querySelectorAll('li').forEach(function(li) {{
          var title = li.textContent.toLowerCase();
          var show = !q || title.includes(q) || artist.includes(q);
          li.style.display = show ? '' : 'none';
          if (show) matched = true;
        }});
        sec.classList.toggle('hidden', !matched);
      }});
    }});
  </script>
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
    new_hash = hashlib.sha256(song_html.encode("utf-8")).hexdigest()
    layout_msg = {"single": "1 kolonne", "double": "2 kolonner", "multi": "flere sider"}

    songs = load_songs()
    existing = next((s for s in songs if s["file"] == filename), None)

    if filepath.exists() and existing and existing.get("hash"):
        current_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        if current_hash != existing["hash"]:
            new_path = SONGS_DIR / f"{filepath.stem}_UGversion.html"
            new_path.write_text(song_html, encoding="utf-8")
            print(f"  ADVARSEL: {filepath} er redigeret manuelt siden sidst.")
            print(f"  Den nye version er gemt som {new_path} i stedet for at overskrive.")
            print(f"  Filen indgår IKKE i songs.json/index.html og kan ikke redigeres via edit_song.py.")
            print(f"  For at bruge den nye version: slet {filepath.name}, omdøb {new_path.name} til {filepath.name}, og kør scriptet igen.")
            print(f"  Ellers kan {new_path.name} bare slettes for at beholde den manuelt redigerede version.")
            print(f"  Layout:  {layout_msg[layout]}")
            return

    filepath.write_text(song_html, encoding="utf-8")
    print(f"  Layout:  {layout_msg[layout]}")
    print(f"  Gemt:    {filepath}")

    entry = {"title": title, "artist": artist, "file": filename, "source": ug_path.name, "hash": new_hash}
    if existing:
        existing.update(entry)
    else:
        songs.append(entry)
    save_songs(songs)
    rebuild_index(songs)