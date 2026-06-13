#!/usr/bin/env python3
"""
Rediger eller tilføj en sang i sangbogen.

Brug:
  python3 edit_song.py <søgeord>   # f.eks. "tender", "blur", "blur-tender"
  python3 edit_song.py --new       # opret en ny sang fra bunden

Format i editoren:
  Sektioner: [Verse 1], [Chorus], [Bridge]
  Akkorder:  [Am], [G], [C#m], [D/F#]
  Tab:       e|--0--, B|--2-- osv. (uændret)
"""

import sys
import os
import re
import tempfile
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

sys.path.insert(0, str(Path(__file__).parent))
from add_song import (
    make_song_html, parse_chord_name, load_songs, save_songs,
    rebuild_index, slugify,
)

SONGS_DIR = Path("songs")


def find_song(query: str):
    songs = load_songs()
    q = query.lower().strip()
    matches = [
        s for s in songs
        if q in s["file"].lower()
        or q in s["title"].lower()
        or q in s["artist"].lower()
    ]
    if not matches:
        sys.exit(f"Ingen sang fundet for '{query}'")
    if len(matches) > 1:
        print("Flere matches – vælg:")
        for i, s in enumerate(matches, 1):
            print(f"  {i}. {s['artist']} – {s['title']}")
        idx = int(input("Nummer: ")) - 1
        return matches[idx], SONGS_DIR / matches[idx]["file"]
    return matches[0], SONGS_DIR / matches[0]["file"]


def extract_meta(soup):
    meta = soup.find(class_="meta")
    key, capo, url = "", "", ""
    if not meta:
        return key, capo, url
    text = meta.get_text()
    m = re.search(r"Toneart:\s*(\S+)", text)
    if m:
        key = m.group(1).strip("·\xa0").strip()
    m = re.search(r"Capo:\s*(\S+)", text)
    if m:
        capo = m.group(1).strip("·\xa0").strip()
    a = meta.find("a")
    if a:
        url = a.get("href", "")
    return key, capo, url


def pre_to_ug(pre) -> str:
    parts = []
    for child in pre.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name == "span" and "section" in child.get("class", []):
            parts.append(child.get_text())
        elif child.name == "span" and "chord" in child.get("class", []):
            parts.append(f"[ch]{child.get_text()}[/ch]")
        else:
            parts.append(child.get_text())
    return "".join(parts).strip("\n")


def html_to_content(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    title = soup.find("h1").get_text()
    artist = soup.find("h2").get_text()
    key, capo, url = extract_meta(soup)
    blocks = [pre_to_ug(pre) for pre in soup.find_all("pre", class_="block")]
    content = "\n\n".join(b for b in blocks if b.strip())
    return title, artist, key, capo, url, content


def ug_to_edit(content: str) -> str:
    return re.sub(r"\[ch\](.*?)\[/ch\]", r"[\1]", content)


def split_inline_chords(line: str) -> list:
    """Convert a line with inline [chord]ord markers into separate chord+lyric
    lines, with chords positioned above the column they precede. Lines that
    contain only chord markers (already-aligned chord lines) are left as-is."""
    plain = []
    chord_positions = []
    i = 0
    while i < len(line):
        if line[i] == "[":
            end = line.find("]", i)
            if end != -1:
                name = line[i + 1:end]
                if parse_chord_name(name) is not None:
                    chord_positions.append((len(plain), name))
                    i = end + 1
                    continue
        plain.append(line[i])
        i += 1

    if not chord_positions:
        return [line]

    plain_text = "".join(plain)
    if not plain_text.strip():
        # Chord-only line (already aligned) – just tag the chords in place
        def replace(m):
            inner = m.group(1)
            if parse_chord_name(inner) is not None:
                return f"[ch]{inner}[/ch]"
            return m.group(0)
        return [re.sub(r"\[([^\]]+)\]", replace, line)]

    segments = []
    col = 0
    for pos, name in chord_positions:
        if pos > col:
            segments.append(" " * (pos - col))
            col = pos
        elif pos < col:
            segments.append(" ")
            col += 1
        segments.append(f"[ch]{name}[/ch]")
        col += len(name)

    return ["".join(segments), plain_text]


def edit_to_ug(text: str) -> str:
    lines = [l for l in text.splitlines() if not l.startswith("#")]

    out = []
    for line in lines:
        out.extend(split_inline_chords(line))

    return "\n".join(out)


def open_editor(text: str) -> str:
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="sangbog_edit_",
        delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        fname = f.name
    try:
        subprocess.run([editor, fname], check=True)
        return Path(fname).read_text(encoding="utf-8")
    finally:
        Path(fname).unlink(missing_ok=True)


def create_new_song():
    title = input("Titel: ").strip()
    artist = input("Artist: ").strip()
    if not title or not artist:
        sys.exit("Titel og artist skal udfyldes.")
    key = input("Toneart (kan være tom): ").strip()
    capo = input("Capo (kan være tom): ").strip()

    filename = f"{slugify(artist)}-{slugify(title)}.html"
    filepath = SONGS_DIR / filename
    if filepath.exists():
        sys.exit(f"Filen findes allerede: {filepath} — brug 'edit_song.py <søgeord>' til at redigere den.")

    template = (
        f"# === {artist} – {title} ===\n"
        f"# Sektioner: [Verse 1], [Chorus]  ·  Akkorder: [Am], [G/B]\n"
        f"# Skriv akkorder direkte i teksten, fx: [Am]Her er linjen\n"
        f"# Gem og luk editoren for at gemme. Tom fil annullerer.\n"
        f"#\n"
        f"[Verse 1]\n"
    )

    edited = open_editor(template)
    content_lines = [l for l in edited.splitlines() if not l.startswith("#")]
    new_content = "\n".join(content_lines).strip()

    if not new_content:
        print("Tom fil – ny sang annulleret.")
        return

    new_ug = edit_to_ug(new_content)
    new_html, layout = make_song_html(title, artist, key, capo, new_ug, "")

    SONGS_DIR.mkdir(exist_ok=True)
    filepath.write_text(new_html, encoding="utf-8")

    songs = load_songs()
    songs.append({"title": title, "artist": artist, "file": filename, "source": "manuel"})
    save_songs(songs)
    rebuild_index(songs)

    layout_msg = {"single": "1 kolonne", "double": "2 kolonner", "multi": "flere sider"}
    print(f"Gemt: {filepath}  (layout: {layout_msg[layout]})")
    print("Indeks opdateret.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--new":
        create_new_song()
        return

    query = " ".join(sys.argv[1:])
    song, html_path = find_song(query)

    if not html_path.exists():
        sys.exit(f"Filen findes ikke: {html_path}")

    print(f"Redigerer: {song['artist']} – {song['title']}")

    title, artist, key, capo, url, ug_content = html_to_content(html_path)
    original_edit = ug_to_edit(ug_content)

    edit_text = (
        f"# === {artist} – {title} ===\n"
        f"# Sektioner: [Verse 1], [Chorus]  ·  Akkorder: [Am], [G/B]\n"
        f"# Gem og luk editoren for at gemme. Slet ALT indhold for at annullere.\n"
        f"#\n"
        + original_edit
    )

    edited = open_editor(edit_text)

    content_lines = [l for l in edited.splitlines() if not l.startswith("#")]
    new_content = "\n".join(content_lines).strip()

    if not new_content:
        print("Tom fil – ingen ændringer gemt.")
        return

    if new_content == original_edit.strip():
        print("Ingen ændringer.")
        return

    new_ug = edit_to_ug(edited)
    new_html, layout = make_song_html(title, artist, key, capo, new_ug, url)
    html_path.write_text(new_html, encoding="utf-8")

    layout_msg = {"single": "1 kolonne", "double": "2 kolonner", "multi": "flere sider"}
    print(f"Gemt: {html_path}  (layout: {layout_msg[layout]})")


if __name__ == "__main__":
    main()
