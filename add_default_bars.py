#!/usr/bin/env python3
"""
Indsæt en naiv [Bars]-sektion ("1 akkord = 1 takt") i en eksisterende sang,
som udgangspunkt for manuel rettelse (gentagelser, pauser, akkorder der
holder i flere takter).

Brug:
  python3 add_default_bars.py <søgeord>   # f.eks. "wooden ships"

Åbner sangen i $EDITOR med den foreslåede [Bars]-sektion indsat, klar til
at rette til, før den gemmes via den normale edit_song.py-gemme-vej.

Har sangen allerede en [Bars]- (eller [Bars draft]-) sektion, tilføjes kun
linjer for sektions-headere (fx et nyt [Bridge]) der endnu ikke har en
matchende label; eksisterende linjer røres ikke.
"""

import sys

from songlib import (
    add_missing_bars, generate_default_bars, is_bars_draft_section, is_bars_section, load_songs,
    make_song_html, parse_sections, rebuild_index, save_songs, slugify,
    transpose_chord, transpose_content, validate_bars,
)

from edit_song import (
    build_header, edit_to_ug, find_song, html_to_content, open_editor,
    parse_header, ug_to_edit,
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    song, html_path = find_song(query)

    if not html_path.exists():
        sys.exit(f"Filen findes ikke: {html_path}")

    title, artist, key, capo, url, tempo, ug_content = html_to_content(html_path)

    headers = _headers(ug_content)
    has_bars = any(is_bars_section(h) for h in headers)
    has_draft = any(is_bars_draft_section(h) for h in headers)

    if has_bars or has_draft:
        # Eksisterende takt-sektion: tilføj kun linjer for nye sektions-headere
        # der endnu ikke har en matchende label.
        section_name = "[Bars]" if has_bars else "[Bars draft]"
        new_ug_content, added = add_missing_bars(ug_content, draft=not has_bars)
        if not added:
            sys.exit(
                f"'{song['artist']} – {song['title']}' har allerede en {section_name}-sektion, "
                f"og alle sektioner med akkorder er dækket. Redigér den i stedet med: "
                f"python3 edit_song.py {query!r}"
            )
        print(f"Tilføjer {len(added)} ny(e) linje(r) til {section_name}:")
        for line in added:
            print(f"  {line}")
        intro = (
            f"# Nye sektioner er tilføjet til {section_name} nedenfor ('1 akkord = 1 takt'):\n"
            + "".join(f"#   {line}\n" for line in added)
            + "# Ret gentagelser (%), pauser (.) og akkorder der holder flere takter manuelt.\n"
        )
        if not has_bars:
            intro += "# Omdøb [Bars draft] til [Bars] for at aktivere takterne.\n"
    else:
        default_bars = generate_default_bars(ug_content)
        if not default_bars:
            sys.exit("Ingen akkorder fundet at generere takter ud fra.")
        new_ug_content = ug_content.rstrip("\n") + "\n\n" + default_bars.rstrip("\n") + "\n"
        intro = (
            "# Foreslåede takter er indsat nedenfor ('1 akkord = 1 takt') – ret\n"
            "# gentagelser (%), pauser (.) og akkorder der holder flere takter manuelt.\n"
        )

    edit_text = (
        build_header(title, artist, key, capo, tempo)
        + intro
        + "# Gem og luk editoren for at gemme. Slet ALT indhold for at annullere.\n"
        + "#\n"
        + ug_to_edit(new_ug_content)
    )

    edited = open_editor(edit_text)

    header = parse_header(edited)
    new_title = header.get("titel", title) or title
    new_artist = header.get("artist", artist) or artist
    new_key = header.get("toneart", key)
    new_capo = header.get("capo", capo)
    new_tempo = header.get("tempo", tempo) or "120"

    transpose_str = header.get("transponer", "0").strip()
    try:
        semitones = int(transpose_str) if transpose_str else 0
    except ValueError:
        sys.exit(f"Ugyldig Transponer-værdi: '{transpose_str}' – brug fx +2 eller -1")

    content_lines = [l for l in edited.splitlines() if not l.startswith("#")]
    new_content = "\n".join(content_lines).strip()

    if not new_content:
        print("Tom fil – ingen ændringer gemt.")
        return

    new_ug = edit_to_ug(edited)
    if semitones:
        new_ug = transpose_content(new_ug, semitones)
        if new_key:
            new_key = transpose_chord(new_key, semitones)

    for warning in validate_bars(new_ug):
        print(f"ADVARSEL: {warning}")

    new_html, layout, has_bars = make_song_html(new_title, new_artist, new_key, new_capo, new_ug, url, new_tempo)

    new_filename = f"{slugify(new_artist)}-{slugify(new_title)}.html"
    new_path = html_path.parent / new_filename
    if new_filename != song["file"]:
        if new_path.exists():
            sys.exit(f"Kan ikke omdøbe – filen findes allerede: {new_path}")
        html_path.unlink()
        html_path = new_path

    html_path.write_text(new_html, encoding="utf-8")

    songs = load_songs()
    for s in songs:
        if s["file"] == song["file"]:
            s["title"] = new_title
            s["artist"] = new_artist
            s["file"] = new_filename
            s.pop("bars", None)
            if has_bars:
                s["bars"] = True
            break
    save_songs(songs)
    rebuild_index(songs)

    print(f"Gemt: {html_path}  (bars: {'ja' if has_bars else 'nej – tjek advarsler ovenfor'})")


def _headers(content: str):
    return [h for h, _ in parse_sections(content)]


if __name__ == "__main__":
    main()
