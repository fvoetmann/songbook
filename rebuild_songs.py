#!/usr/bin/env python3
"""Regenerate all song HTML files using the current template.

Useful after template changes (e.g. mobile CSS updates) to update
existing song files without needing the original UG source files.

Usage:
  python3 rebuild_songs.py
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from add_song import make_song_html, load_songs, save_songs, rebuild_index, SONGS_DIR
from edit_song import html_to_content


def main():
    songs = load_songs()
    updated = 0
    for song in songs:
        filepath = SONGS_DIR / song["file"]
        if not filepath.exists():
            print(f"  Missing: {filepath}")
            continue

        title, artist, key, capo, url, tempo, content = html_to_content(filepath)
        new_html, layout = make_song_html(title, artist, key, capo, content, url, tempo)

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
