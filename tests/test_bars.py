from pathlib import Path

from songlib import (
    extract_chord_sequence,
    find_label_for_header,
    generate_default_bars,
    is_bars_section,
    make_song_html,
    match_section,
    parse_bars_meta,
    validate_bars,
)
from songlib.bars import Bar

from edit_song import edit_to_ug, html_to_content, ug_to_edit


# ── Grammatik ────────────────────────────────────────────────────────────

def test_is_bars_section():
    assert is_bars_section("[Bars]")
    assert is_bars_section("[bars]")
    assert not is_bars_section("[Verse 1]")


def test_parse_single_chord_bars():
    bars = parse_bars_meta("Intro: |D|A|G|")["Intro"]
    assert bars == [Bar(chords=["D"]), Bar(chords=["A"]), Bar(chords=["G"])]


def test_parse_shared_bar():
    bars = parse_bars_meta("Intro: |D A|G|")["Intro"]
    assert bars[0] == Bar(chords=["D", "A"])
    assert bars[1] == Bar(chords=["G"])


def test_parse_repeat_and_rest():
    bars = parse_bars_meta("Vers: |Em|%|.|")["Vers"]
    assert bars[0] == Bar(chords=["Em"])
    assert bars[1] == Bar(is_repeat=True)
    assert bars[2] == Bar(is_rest=True)


def test_parse_optional_edge_pipes():
    # Leading/trailing "|" are cosmetic and optional.
    assert parse_bars_meta("Vers: D|A")["Vers"] == [Bar(chords=["D"]), Bar(chords=["A"])]
    assert parse_bars_meta("Vers: |D|A|")["Vers"] == [Bar(chords=["D"]), Bar(chords=["A"])]


def test_parse_multiple_labels():
    body = "Intro: |D|A|\nVers: |Em|Am|"
    parsed = parse_bars_meta(body)
    assert set(parsed.keys()) == {"Intro", "Vers"}


def test_parse_ignores_blank_lines():
    assert parse_bars_meta("Intro: |D|\n\nVers: |Em|") == {
        "Intro": [Bar(chords=["D"])],
        "Vers": [Bar(chords=["Em"])],
    }


# ── Matchning ────────────────────────────────────────────────────────────

def test_extract_chord_sequence_preserves_order_and_duplicates():
    body = "[ch]Em[/ch]\ntext\n[ch]Am[/ch]\ntext\n[ch]Em[/ch]"
    assert extract_chord_sequence(body) == ["Em", "Am", "Em"]


def test_find_label_exact_match_preferred_over_prefix():
    labels = ["Vers", "Vers 2"]
    assert find_label_for_header("[Vers 2]", labels) == "Vers 2"


def test_find_label_prefix_match():
    assert find_label_for_header("[Vers 1]", ["Vers"]) == "Vers"
    assert find_label_for_header("[Chorus]", ["Vers"]) is None


def test_match_section_success_marks_bar_starts():
    bars = parse_bars_meta("Vers: |D A|G|")["Vers"]
    result = match_section(bars, ["D", "A", "G"])
    assert result is not None
    assert result.bar_starts == {0, 2}  # D starts bar 1, A is mid-bar, G starts bar 2


def test_match_section_mismatch_returns_none():
    bars = parse_bars_meta("Vers: |D|A|")["Vers"]
    assert match_section(bars, ["D", "G"]) is None
    assert match_section(bars, ["D"]) is None
    assert match_section(bars, ["D", "A", "G"]) is None


def test_match_section_repeat_and_rest_do_not_require_a_body_occurrence():
    bars = parse_bars_meta("Vers: |C|%|.|")["Vers"]
    result = match_section(bars, ["C"])
    assert result is not None
    assert result.bar_starts == {0}
    assert len(result.extra_after[0]) == 2


# ── Default-generering ───────────────────────────────────────────────────

def test_generate_default_bars_one_chord_per_bar():
    content = (
        "[Intro]\n[ch]D[/ch]  [ch]A[/ch]\n\n"
        "[Verse 1]\n[ch]Em[/ch]\nwords\n[ch]Am[/ch]\nmore words\n"
    )
    generated = generate_default_bars(content)
    assert generated == "[Bars]\nIntro: |D|A|\nVerse 1: |Em|Am|\n"


def test_generate_default_bars_skips_sections_without_chords():
    content = "[Intro]\nno chords here at all\n"
    assert generate_default_bars(content) == ""


def test_generate_default_bars_skips_tab_sections():
    content = "[Intro]\ne|--0--|\nB|--1--|\n"
    assert generate_default_bars(content) == ""


# ── Rendering (make_song_html) ───────────────────────────────────────────

BARS_CONTENT = (
    "[Intro]\n"
    "[ch]D[/ch]  [ch]A[/ch]  [ch]G[/ch]\n\n"
    "[Verse 1]\n"
    "[ch]Em7[/ch]\n"
    "If you smile at me, I will understand\n"
    "[ch]Am7[/ch]\n"
    "Cause that is something everybody everywhere does\n\n"
    "[Bars]\n"
    "Intro: |D A|G|\n"
    "Verse: |Em7|Am7|\n"
)


def test_song_without_bars_section_has_bars_false():
    content = "[Verse 1]\n[ch]Am[/ch]\nHer er en linje\n"
    _html, _layout, has_bars = make_song_html("T", "A", "", "", content, "")
    assert has_bars is False
    assert "barline" not in _html
    # Den delte bas-JS refererer altid til '#bar-data' (som getElementById, der
    # blot returnerer null her) - kun det indlejrede <script id="bar-data">-tag
    # selv er betinget af has_bars.
    assert '<script type="application/json" id="bar-data">' not in _html


def test_song_with_matching_bars_section_renders_barlines():
    rendered, _layout, has_bars = make_song_html("Wooden Ships", "CSN", "D", "", BARS_CONTENT, "", "120")
    assert has_bars is True
    # D+A share the first bar (one barline before D, none before A); G starts its own bar.
    assert rendered.count('<span class="barline" data-derived="bars"></span>') == 4
    assert '<script type="application/json" id="bar-data">' in rendered
    assert 'class="block bars-source" hidden' in rendered


def test_song_with_mismatched_bars_section_renders_unchanged():
    content = (
        "[Verse 1]\n[ch]Am[/ch]\nHer er en linje\n\n"
        "[Bars]\nVers: |Am|G|\n"  # two bars, but body only has one chord
    )
    rendered, _layout, has_bars = make_song_html("T", "A", "", "", content, "")
    assert has_bars is False
    assert "barline" not in rendered


def test_validate_bars_warns_on_mismatch():
    content = "[Verse 1]\n[ch]Am[/ch]\nHer er en linje\n\n[Bars]\nVers: |Am|G|\n"
    warnings = validate_bars(content)
    assert len(warnings) == 1
    assert "Vers" in warnings[0]


def test_validate_bars_warns_on_unmatched_label():
    content = "[Verse 1]\n[ch]Am[/ch]\nHer er en linje\n\n[Bars]\nSolo: |Am|G|\n"
    warnings = validate_bars(content)
    assert len(warnings) == 1
    assert "Solo" in warnings[0]


def test_validate_bars_no_warnings_without_bars_section():
    assert validate_bars("[Verse 1]\n[ch]Am[/ch]\nHer er en linje\n") == []


def test_validate_bars_no_warnings_on_clean_match():
    assert validate_bars(BARS_CONTENT) == []


# ── Round-trip (edit_song.py) ────────────────────────────────────────────

def test_bars_section_round_trips_through_editor_cycle(tmp_path):
    """The [Bars] section (header + body) and the synthesized barline/
    rest/repeat markers must survive render -> extract -> edit format ->
    save, reaching a stable fixed point (mirrors test_roundtrip.py's
    edit_song.py editor-cycle test, extended with a [Bars] section)."""
    current = BARS_CONTENT
    for _ in range(3):
        rendered, _layout, _has_bars = make_song_html("Wooden Ships", "CSN", "D", "", current, "")
        path = tmp_path / "song.html"
        path.write_text(rendered, encoding="utf-8")
        _, _, _, _, _, _, extracted = html_to_content(path)
        current = edit_to_ug(ug_to_edit(extracted))

    assert "[Bars]" in current
    assert "Intro: |D A|G|" in current
    assert "Verse: |Em7|Am7|" in current
    # The synthesized barline/rest/repeat markers must never leak into content.
    assert "barline" not in current
    assert "barmark" not in current


def test_bars_with_repeat_and_rest_round_trips(tmp_path):
    content = "[Bridge]\n[ch]C[/ch]\nSome words here\n\n[Bars]\nBridge: |C|%|.|\n"
    rendered, _layout, has_bars = make_song_html("T", "A", "", "", content, "")
    assert has_bars is True
    path = tmp_path / "song.html"
    path.write_text(rendered, encoding="utf-8")
    _, _, _, _, _, _, extracted = html_to_content(path)
    assert extracted == content.strip()
