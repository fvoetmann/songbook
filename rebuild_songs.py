#!/usr/bin/env python3
"""Regenerate all song HTML files using the current template.

Useful after template changes (e.g. mobile CSS updates) to update
existing song files without needing the original UG source files.

Usage:
  python3 rebuild_songs.py
"""

import hashlib
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

sys.path.insert(0, str(Path(__file__).parent))
from add_song import make_song_html, load_songs, save_songs, rebuild_index, SONGS_DIR


def extract_title_artist(soup) -> tuple:
    h1 = soup.find("h1")
    artist_span = h1.find("span", class_="artist-inline")
    if artist_span:
        artist = re.sub(r"^–\s*", "", artist_span.get_text()).strip()
        title = h1.get_text()[: -len(artist_span.get_text())].strip()
        return title, artist
    # Old format: separate <h2> for artist
    h2 = soup.find("h2")
    return h1.get_text().strip(), (h2.get_text().strip() if h2 else "")


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
    title, artist = extract_title_artist(soup)
    key, capo, url = extract_meta(soup)
    blocks = [pre_to_ug(pre) for pre in soup.find_all("pre", class_="block")]
    content = "\n\n".join(b for b in blocks if b.strip())
    return title, artist, key, capo, url, content


def main():
    songs = load_songs()
    updated = 0
    for song in songs:
        filepath = SONGS_DIR / song["file"]
        if not filepath.exists():
            print(f"  Missing: {filepath}")
            continue

        title, artist, key, capo, url, content = html_to_content(filepath)
        new_html, layout = make_song_html(title, artist, key, capo, content, url)

        filepath.write_text(new_html, encoding="utf-8")
        new_hash = hashlib.sha256(new_html.encode("utf-8")).hexdigest()
        song["hash"] = new_hash

        layout_msg = {"single": "1 kolonne", "double": "2 kolonner", "multi": "flere sider"}
        print(f"  {artist} – {title}  ({layout_msg.get(layout, layout)})")
        updated += 1

    save_songs(songs)
    rebuild_index(songs)
    print(f"\nOpdateret {updated} sange. Indeks genopbygget.")


if __name__ == "__main__":
    main()
