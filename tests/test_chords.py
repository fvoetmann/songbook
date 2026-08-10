import pytest

import add_song
from add_song import parse_chord_name, generate_voicings, CHORD_TYPES, INSTRUMENTS, NOTE_SEMI


@pytest.mark.parametrize("suffix,ivs", CHORD_TYPES)
@pytest.mark.parametrize("root_letter", list(NOTE_SEMI))
def test_parse_chord_name_roundtrips_over_all_types(root_letter, suffix, ivs):
    parsed = parse_chord_name(root_letter + suffix)
    assert parsed is not None
    root, parsed_ivs, bass = parsed
    assert root == NOTE_SEMI[root_letter]
    assert parsed_ivs == ivs
    assert bass is None


@pytest.mark.parametrize("name,expected_root,expected_bass", [
    ("D/F#", NOTE_SEMI["D"], (NOTE_SEMI["F"] + 1) % 12),
    ("C/E", NOTE_SEMI["C"], NOTE_SEMI["E"]),
    ("Am/G", NOTE_SEMI["A"], NOTE_SEMI["G"]),
])
def test_parse_chord_name_slash_bass(name, expected_root, expected_bass):
    parsed = parse_chord_name(name)
    assert parsed is not None
    root, ivs, bass = parsed
    assert root == expected_root
    assert bass == expected_bass


@pytest.mark.parametrize("name", ["", "H", "X7", "Am7b9"])
def test_parse_chord_name_rejects_unknown(name):
    assert parse_chord_name(name) is None


@pytest.mark.parametrize("instr_name,instr", INSTRUMENTS.items())
@pytest.mark.parametrize("chord_name", ["C", "Am", "G7", "D/F#", "Fmaj7"])
def test_generate_voicings_sanity(instr_name, instr, chord_name):
    parsed = parse_chord_name(chord_name)
    assert parsed is not None
    root, ivs, bass = parsed
    voicings = generate_voicings(root, ivs, bass, instr=instr)
    assert voicings, f"ingen greb fundet for {chord_name} på {instr_name}"

    string_open = instr["strings"]
    n_str = len(string_open)
    tones = {(root + iv) % 12 for iv in ivs}

    for frets in voicings:
        assert len(frets) == n_str
        played = {(string_open[s] + frets[s]) % 12 for s in range(n_str) if frets[s] >= 0}
        # Root must always sound.
        assert root % 12 in played
        # Third (or defining second interval) must always sound.
        if len(ivs) > 1:
            assert (root + ivs[1]) % 12 in played
        # Fret span among pressed (non-open, non-muted) strings stays playable.
        pressed = [f for f in frets if f > 0]
        if pressed:
            assert max(pressed) - min(pressed) <= instr["span"]
        if bass is not None:
            lo_abs = min(string_open[s] + frets[s] for s in range(n_str) if frets[s] >= 0)
            assert lo_abs % 12 == bass % 12


def test_generate_voicings_banjo_fifth_string_always_open():
    banjo = INSTRUMENTS["banjo"]
    root, ivs, bass = parse_chord_name("G")
    voicings = generate_voicings(root, ivs, bass, instr=banjo)
    assert voicings
    for frets in voicings:
        assert frets[4] == 0  # 5th (drone) string is fixed_open


def test_generate_voicings_unplayable_chord_returns_empty():
    # A chord requiring an interval far outside a very restrictive instrument
    # config should yield no voicings rather than raising.
    tiny = {"strings": [40, 45], "max_fret": 0, "min_play": 2, "span": 0}
    assert generate_voicings(0, [0, 4, 7], instr=tiny) == []


def test_build_voicings_db_skips_unparseable_names():
    db = add_song.build_voicings_db(["C", "???", "Am"])
    assert set(db) == {"C", "Am"}
