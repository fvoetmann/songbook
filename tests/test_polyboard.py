import json
from pathlib import Path

import pytest

from songlib import render_polyboard
from songlib.polyboard import (
    bar_data_from_html,
    bar_data_to_units,
    chord_stack,
    expand_units,
    extract_patterns,
    tempo_from_html,
)

ROOT = Path(__file__).resolve().parent.parent


def bar(*chords, repeat=False, rest=False):
    return {"chords": list(chords), "repeat": repeat, "rest": rest}


def song(*sections):
    return {"beats_per_bar": 4, "sections": [{"section": n, "bars": b} for n, b in sections]}


# ── Akkord → toner ───────────────────────────────────────────────────────────

def test_chord_stack_root_position():
    assert chord_stack("D") == (50, [0, 4, 7])      # d3
    assert chord_stack("Dmaj7") == (50, [0, 4, 7, 11])
    assert chord_stack("Em7") == (52, [0, 3, 7, 10])
    assert chord_stack("A") == (45, [0, 4, 7])      # a2 – rødder ≥ A lægges en oktav ned
    assert chord_stack("Bb") == (46, [0, 4, 7])


def test_chord_stack_slash_is_inversion_over_bass():
    # D/F# = F# A D, regnet fra F# (54)
    assert chord_stack("D/F#") == (54, [0, 3, 8])


def test_chord_stack_unknown():
    assert chord_stack("Dmadd9") is None


# ── Takt-data → enheder ──────────────────────────────────────────────────────

def test_repeat_extends_previous_unit():
    units = bar_data_to_units(song(("Vers", [bar("Em"), bar(repeat=True), bar(repeat=True), bar("D")])))
    assert units == [("Vers", [(("Em",), 3), (("D",), 1)])]


def test_rests_merge_and_repeat_after_rest_stays_rest():
    units = bar_data_to_units(song(("A", [bar("D"), bar(rest=True), bar(rest=True), bar(repeat=True)])))
    assert units == [("A", [(("D",), 1), ((), 3)])]


def test_repeat_without_previous_bar_is_rest():
    units = bar_data_to_units(song(("A", [bar(repeat=True), bar("D")])))
    assert units == [("A", [((), 1), (("D",), 1)])]


def test_empty_sections_dropped():
    assert bar_data_to_units(song(("A", []), ("B", [bar("D")]))) == [("B", [(("D",), 1)])]


# ── Mønster-udtrækning ───────────────────────────────────────────────────────

FIG = [(("D", "D6"), 1), (("Dmaj7",), 1), (("D", "D6"), 1), (("Dmaj7",), 1)]


def test_extract_patterns_roundtrips():
    seqs = [FIG + FIG, [(("Em7",), 4)] + FIG + [(("Em7",), 4)] + FIG, [(("G6",), 4)] + FIG + [(("G6",), 4)] + FIG]
    new, patterns = extract_patterns(seqs)
    assert patterns, "det gentagne fire-takters mønster skal udtrækkes"
    for orig, rewritten in zip(seqs, new):
        assert expand_units(rewritten, patterns) == expand_units(orig)


def test_extract_patterns_ignores_small_or_single_use_repetition():
    seqs = [[(("D",), 1), (("A",), 1), (("D",), 1), (("A",), 1)]]
    new, patterns = extract_patterns(seqs)
    assert patterns == {} and new == seqs


def test_extract_patterns_never_extracts_a_whole_section():
    seqs = [FIG + FIG, FIG + FIG + [(("G",), 1)]]
    _, patterns = extract_patterns(seqs)
    assert all(len(body) != len(FIG + FIG) for body in patterns.values())


# ── Rendering ────────────────────────────────────────────────────────────────

SMALL = song(
    ("Intro", [bar("D", "A"), bar("G")]),
    ("Vers", [bar("Em"), bar(repeat=True)]),
)


def test_render_small_song_golden():
    text, warnings = render_polyboard(SMALL, "113", title="Song", artist="Artist")
    assert warnings == []
    assert text.splitlines()[0] == "-- Polyboard-eksport af Artist – Song (export_polyboard.py)"
    body = [l for l in text.splitlines() if l and not l.startswith("--")]
    assert body == [
        "setbpm 113",
        "def intro = ([d3'[0 4 7] a2'[0 4 7]] g3'[0 4 7])",
        "def vers = (e3'[0 3 7]@2)",
        "d1 # note ($intro@2 $vers@2)/4 # s arpy",
    ]


def test_render_restrike_uses_bang():
    text, _ = render_polyboard(SMALL, "113", restrike=True)
    assert "def vers = (e3'[0 3 7]!2)" in text


def test_render_multi_chord_bar_repeat_restrikes_even_without_flag():
    data = song(("A", [bar("D", "A"), bar(repeat=True)]))
    text, _ = render_polyboard(data)
    assert "def a = ([d3'[0 4 7] a2'[0 4 7]]!2)" in text


def test_render_rests_and_slash_and_sound():
    data = song(("A", [bar("D/F#"), bar(rest=True), bar(rest=True)]))
    text, _ = render_polyboard(data, sound="superpiano")
    assert "def a = (fs3'[0 3 8] ~!2)" in text
    assert text.rstrip().endswith("d1 # note ($a@3)/3 # s superpiano")


def test_render_bass_layer_uses_midi_numbers():
    text, _ = render_polyboard(SMALL, "113", bass=True)
    body = [l for l in text.splitlines() if l and not l.startswith("--")]
    assert "def bintro = ([38 33] 43)" in body        # D=38, A=33, G=43 (en oktav under akkorden)
    assert "def bvers = (40!2)" in body               # Em7 holdt 2 takter: grundtonen hver takt
    assert body[-1] == "d2 # note ($bintro@2 $bvers@2)/4 # s arpy"


def test_render_shares_def_for_identical_sections_and_dedupes_names():
    data = song(
        ("Chorus", [bar("D"), bar("A")]),
        ("Verse", [bar("G")]),
        ("Chorus", [bar("D"), bar("A")]),
        ("Verse", [bar("C")]),
    )
    text, _ = render_polyboard(data)
    assert text.count("def chorus =") == 1
    assert "def verse =" in text and "def verse2 =" in text
    assert "d1 # note ($chorus@2 $verse@1 $chorus@2 $verse2@1)/6 # s arpy" in text


def test_render_def_names_are_valid():
    data = song(("1. vers", [bar("D")]), ("Omkvæd!", [bar("A")]))
    text, _ = render_polyboard(data)
    assert "def s1vers = " in text
    assert "def omkvaed = " in text


def test_render_unknown_chord_becomes_rest_with_warning():
    data = song(("A", [bar("Dmadd9"), bar("D")]))
    text, warnings = render_polyboard(data)
    assert "def a = (~ d3'[0 4 7])" in text
    assert warnings == ["Ukendt akkord 'Dmadd9' – erstattet med pause"]


def test_render_empty_raises():
    with pytest.raises(ValueError):
        render_polyboard(song(("A", [])))


def test_render_pattern_used_in_song():
    data = song(
        ("Intro", [bar("D", "D6"), bar("Dmaj7"), bar("D", "D6"), bar("Dmaj7")] * 2),
        ("Vers", [bar("Em7"), bar(repeat=True), bar(repeat=True), bar(repeat=True)]
         + [bar("D", "D6"), bar("Dmaj7"), bar("D", "D6"), bar("Dmaj7")] * 3),
    )
    text, _ = render_polyboard(data)
    assert "def pat1 = (" in text
    assert "$pat1@4" in text


# ── Læsning fra HTML ─────────────────────────────────────────────────────────

def test_bar_data_and_tempo_from_html():
    payload = song(("A", [bar("D")]))
    html = (f'<meta name="tempo" content="113">\n'
            f'<script type="application/json" id="bar-data">{json.dumps(payload)}</script>')
    assert bar_data_from_html(html) == payload
    assert tempo_from_html(html) == "113"


def test_html_without_bars_or_tempo():
    assert bar_data_from_html("<html></html>") is None
    assert tempo_from_html("<html></html>") == "120"
    assert tempo_from_html('<meta name="tempo" content="">') == "120"


# ── Rigtig sang ──────────────────────────────────────────────────────────────

def test_harvest_moon_roundtrip_and_render():
    path = ROOT / "songs" / "neil-young-harvest-moon.html"
    if not path.exists():
        pytest.skip(f"fixture-fil mangler: {path}")
    bar_data = bar_data_from_html(path.read_text(encoding="utf-8"))
    labelled = bar_data_to_units(bar_data)

    # Original takt-for-takt akkordliste (en '%'-takt har samme akkorder som forrige)
    original = []
    for section in bar_data["sections"]:
        cur = ()
        for b in section["bars"]:
            if b["rest"]:
                cur = ()
            elif not b["repeat"]:
                cur = tuple(b["chords"])
            original.append(cur)
    assert sum(len(expand_units(units)) for _, units in labelled) == len(original) == 145

    uniq = list(dict.fromkeys(tuple(u) for _, u in labelled))
    new, patterns = extract_patterns(uniq)
    rebuilt = []
    lookup = dict(zip(uniq, new))
    for _, units in labelled:
        rebuilt.extend(expand_units(lookup[tuple(units)], patterns))
    assert rebuilt == original

    text, warnings = render_polyboard(bar_data, tempo_from_html(path.read_text(encoding="utf-8")), bass=True)
    assert warnings == []
    assert "setbpm 113" in text
    assert "/145 # s arpy" in text and "/145 # s superpiano" in render_polyboard(
        bar_data, "113", bass=True, bass_sound="superpiano")[0]
