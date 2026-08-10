import pytest

from add_song import shift_note, transpose_chord, transpose_content, parse_transpose


@pytest.mark.parametrize("note,n,expected", [
    ("C", 1, "C#"),
    ("C", -1, "B"),
    ("B", 1, "C"),
    ("G", 12, "G"),      # full octave wraps back to itself
    ("G", -12, "G"),
    ("Bb", 1, "B"),
    ("Bb", -1, "A"),
])
def test_shift_note(note, n, expected):
    assert shift_note(note, n) == expected


def test_shift_note_unknown_returns_unchanged():
    assert shift_note("H", 3) == "H"


@pytest.mark.parametrize("chord,n,expected", [
    ("Am", 3, "Cm"),
    ("G", -1, "F#"),
    ("D/F#", 2, "E/G#"),
    ("Bb7", 2, "C7"),
    ("Cmaj7", 0, "Cmaj7"),
    ("C", 12, "C"),
    ("C", -12, "C"),
])
def test_transpose_chord(chord, n, expected):
    assert transpose_chord(chord, n) == expected


def test_transpose_chord_preserves_flat_spelling_scale():
    # Uses the flat scale when the input chord contains a flat.
    assert transpose_chord("Eb", 1) == "E"
    assert transpose_chord("Eb", -1) == "D"


def test_transpose_chord_unparseable_returns_unchanged():
    assert transpose_chord("N.C.", 3) == "N.C."


def test_transpose_content_zero_is_noop():
    content = "[ch]Am[/ch] text [ch]D/F#[/ch]"
    assert transpose_content(content, 0) == content


def test_transpose_content_shifts_all_chords():
    content = "[ch]Am[/ch] verse [ch]D/F#[/ch] more [ch]G7[/ch]"
    result = transpose_content(content, 2)
    assert result == "[ch]Bm[/ch] verse [ch]E/G#[/ch] more [ch]A7[/ch]"


@pytest.mark.parametrize("filename,expected", [
    ("song.html", 0),
    ("song_+3.html", 3),
    ("song_-2.html", -2),
    ("song_+11.html", 11),
    ("weird-name-without-suffix.html", 0),
])
def test_parse_transpose(filename, expected):
    assert parse_transpose(filename) == expected
