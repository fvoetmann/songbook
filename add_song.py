#!/usr/bin/env python3
"""
Sangbog – tilføj en sang fra Ultimate Guitar

Brug:
  python add_song.py                   # auto-scan downloads/ for nye sange
  python add_song.py <fil.html>        # tilføj specifik fil

Transponering: tilføj _+N eller _-N til filnavnet før .html
  fx: the-cure_boys-dont-cry_+3.html  → transponer op 3 halvtoner

Tip: Gem UG-siden manuelt med Ctrl+U → Ctrl+A → Ctrl+S i din browser.

Dette er en tynd wrapper om songlib-pakken (se songlib/). API'et re-eksporteres
så eksisterende importers (edit_song.py, make_pdf.py, rebuild_songs.py, tests)
forbliver uændrede.
"""

import sys

from songlib import (  # noqa: E402
    ACCIDENTAL,
    CHORD_DIAGRAM_JS,
    CHORD_DIAGRAM_STYLE,
    CHORD_TYPES,
    DOWNLOADS_DIR,
    FLATS,
    INDEX_FILE,
    INSTRUMENTS,
    LINES_PER_PAGE,
    MAX_FRET,
    NOTE_SEMI,
    SHARPS,
    SONGS_DATA,
    SONGS_DIR,
    STRING_OPEN,
    artist_sort_key,
    build_all_voicings_dbs,
    build_voicings_db,
    chord_positions_align,
    content_to_html,
    count_lines,
    decide_layout,
    extract_chord_names,
    extract_ug_data,
    fetch_page,
    generate_voicings,
    get_song_info,
    group_lines,
    is_chord_annotation_line,
    is_chord_only_line,
    is_tab_section,
    load_songs,
    make_chord_diagram_html,
    make_song_html,
    main,
    paginate_sections,
    parse_chord_name,
    parse_chord_positions,
    parse_sections,
    parse_transpose,
    process_file,
    processed_sources,
    rebuild_index,
    render_chord_lines,
    render_chord_lyric_line,
    render_section,
    save_songs,
    section_line_count,
    shift_note,
    slugify,
    split_mixed,
    transpose_chord,
    transpose_content,
    unwrap_view_source,
)

if __name__ == "__main__":
    main()
