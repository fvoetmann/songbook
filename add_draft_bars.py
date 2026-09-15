#!/usr/bin/env python3
"""
Indsæt en foreslået, men INAKTIV, [Bars draft]-sektion i alle sange der
endnu ikke har en [Bars]- eller [Bars draft]-sektion.

[Bars draft] bruger samme naive gæt som add_default_bars.py ("1 akkord = 1
takt", ingen gentagelser/pauser), men vises ikke i sang-visningen og
indgår ikke i taktstregs-matchning – den ændrer altså intet ved nogen
sang, før man selv går ind og redigerer den. For at aktivere en sang:

  python3 edit_song.py <søgeord>

ret evt. takterne til (gentagelser, pauser, akkorder der deler en takt) og
omdøb sektionens header fra "[Bars draft]" til "[Bars]" – gem, og den
almindelige takstregs-visning/validering tager over.

Brug:
  python3 add_draft_bars.py
"""

import hashlib

from songlib import (
    BARS_DRAFT_HEADER, generate_default_bars, is_bars_draft_section,
    is_bars_section, load_songs, make_song_html, parse_sections,
    rebuild_index, save_songs, SONGS_DIR,
)
from edit_song import html_to_content


def _headers(content: str):
    return [h for h, _ in parse_sections(content)]


def main():
    songs = load_songs()
    added = skipped = missing = 0

    for song in songs:
        filepath = SONGS_DIR / song["file"]
        if not filepath.exists():
            print(f"  Mangler: {filepath}")
            missing += 1
            continue

        title, artist, key, capo, url, tempo, content = html_to_content(filepath)
        headers = _headers(content)
        if any(is_bars_section(h) or is_bars_draft_section(h) for h in headers):
            skipped += 1
            continue

        draft = generate_default_bars(content, header=BARS_DRAFT_HEADER)
        if not draft:
            skipped += 1
            continue

        new_content = content.rstrip("\n") + "\n\n" + draft.rstrip("\n") + "\n"
        new_html, layout, has_bars = make_song_html(
            title, artist, key, capo, new_content, url, tempo
        )
        filepath.write_text(new_html, encoding="utf-8")
        song["hash"] = hashlib.sha256(new_html.encode("utf-8")).hexdigest()
        added += 1
        print(f"  {artist} – {title}: [Bars draft] tilføjet")

    save_songs(songs)
    rebuild_index(songs)
    print(
        f"\n{added} sange fik en [Bars draft]-sektion, {skipped} havde allerede "
        f"[Bars]/[Bars draft] eller ingen akkorder, {missing} filer manglede."
    )


if __name__ == "__main__":
    main()
