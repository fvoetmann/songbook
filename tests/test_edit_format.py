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
