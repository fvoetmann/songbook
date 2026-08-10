import pytest

from edit_song import ug_to_edit, edit_to_ug, split_inline_chords, merge_chord_line


@pytest.mark.parametrize("chord_line,lyric_line", [
    ("[ch]Am[/ch]", "Her er teksten"),
    ("[ch]Am[/ch]      [ch]G[/ch]", "Her er en laengere linje"),
    ("[ch]D/F#[/ch]", "Slash-akkord"),
])
def test_merge_and_split_inline_chords_are_inverse(chord_line, lyric_line):
    inline = merge_chord_line(chord_line, lyric_line)
    result = split_inline_chords(inline)
    assert len(result) == 2
    assert result[0] == chord_line
    assert result[1] == lyric_line


def test_merge_and_split_chord_only_line_with_no_lyric():
    # No lyric to anchor to: split_inline_chords recognizes this as an
    # already-aligned chord-only line and keeps it on a single line.
    inline = merge_chord_line("[ch]C[/ch]", "")
    assert split_inline_chords(inline) == ["[ch]C[/ch]"]


def test_split_inline_chords_leaves_plain_line_unchanged():
    assert split_inline_chords("bare tekst uden akkorder") == ["bare tekst uden akkorder"]


def test_split_inline_chords_ignores_non_chord_brackets():
    # "[Verse 1]"-style headers or arbitrary bracketed text must not be
    # mistaken for an inline chord marker.
    assert split_inline_chords("[Verse 1]") == ["[Verse 1]"]


def test_split_inline_chords_recognizes_shorthand_2_suffix():
    # Regression: "D2" (common shorthand for "Dsus2") wasn't in CHORD_TYPES,
    # so parse_chord_name("D2") returned None and split_inline_chords treated
    # "[D2]" as literal text instead of a chord marker — silently dropping
    # the chord's [ch] tag (and its diagram) on every edit_song.py save.
    inline = merge_chord_line("[ch]D[/ch] [ch]D2[/ch] [ch]Em[/ch]", "")
    result = split_inline_chords(inline)
    assert len(result) == 1
    assert "[ch]D2[/ch]" in result[0]


def test_ug_to_edit_and_back_preserves_chords():
    content = "[ch]Am[/ch]  [ch]G[/ch]\nHer er teksten"
    edit_format = ug_to_edit(content)
    back = edit_to_ug(edit_format)
    assert back == content


def test_ug_to_edit_merges_chord_and_lyric_line():
    content = "[ch]Am[/ch]\nHello world"
    edit_format = ug_to_edit(content)
    assert edit_format == "[Am]Hello world"
    back = edit_to_ug(edit_format)
    assert back == content


def test_edit_to_ug_strips_header_comment_lines():
    text = "# Titel: X\n# Artist: Y\n#\n[Am]Hej"
    assert edit_to_ug(text) == "[ch]Am[/ch]\nHej"


@pytest.mark.parametrize("content", [
    # Regression: chord-progression annotation lines with no real lyric to
    # pair against used to lose their [ch] tags entirely (or get scrambled)
    # after a save in edit_song.py, because split_inline_chords tried to
    # reposition/split them like a genuine "[Am]word" pairing.
    "[ch]Em[/ch]  [ch]Em[/ch](+F#) ",
    "[ch]Em[/ch]  [ch]E/D#[/ch]  [ch]C#m[/ch]  [ch]A[/ch]  [ch]D2[/ch]",
    "intro:  [ch]Amaj7[/ch]      [ch]B7[/ch]",
])
def test_ug_to_edit_uses_curly_braces_for_non_paired_lines(content):
    edit_format = ug_to_edit(content)
    assert "{" in edit_format and "[" not in edit_format
    assert edit_to_ug(edit_format) == content


def test_split_inline_chords_curly_braces_preserve_line_verbatim():
    # {chord} is never repositioned or split into a chord-line/lyric-line
    # pair, no matter how many chords or how little real text surrounds them.
    line = "{Em}  {Em}(+F#)  {C}  {D2} "
    result = split_inline_chords(line)
    assert result == ["[ch]Em[/ch]  [ch]Em[/ch](+F#)  [ch]C[/ch]  [ch]D2[/ch] "]


def test_split_inline_chords_curly_braces_accept_unparseable_names():
    # No validity check for {} — it's a "keep exactly as typed" escape
    # hatch, unlike [] which only recognizes real chord names.
    assert split_inline_chords("{not-a-chord}") == ["[ch]not-a-chord[/ch]"]


def test_full_edit_roundtrip_stable_across_repeated_saves():
    # Simulates opening and re-saving a song several times with no textual
    # changes — must reach a stable fixed point immediately, not drift.
    content = "[ch]Em[/ch]  [ch]Em[/ch](+F#)  [ch]C#m[/ch]\n[ch]D[/ch] [ch]D[/ch] [ch]D2[/ch] [ch]Em[/ch]"
    current = content
    for _ in range(3):
        current = edit_to_ug(ug_to_edit(current))
    assert current == content
