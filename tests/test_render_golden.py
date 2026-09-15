from pathlib import Path

from add_song import make_song_html

GOLDEN_DIR = Path(__file__).parent / "golden"

SAMPLE_CONTENT = (
    "[Verse 1]\n"
    "[ch]Am[/ch]     [ch]G[/ch]\n"
    "Her er en linje  med tekst\n"
    "[ch]F[/ch]  [ch]C[/ch]\n"
    "Og en linje til\n"
    "\n"
    "[Chorus]\n"
    "[ch]D/F#[/ch]  x4\n"
)


def test_make_song_html_matches_golden_file():
    """Regression guard for the HTML/CSS/JS template: if this fails after an
    intentional template change, inspect the diff and, if it's the change
    you meant to make, regenerate with:
        UPDATE_GOLDEN=1 pytest tests/test_render_golden.py
    """
    rendered, layout, has_bars = make_song_html(
        "Golden Testsang", "Golden Artist", "Am", "2", SAMPLE_CONTENT, "https://example.com/song", "140"
    )
    golden_path = GOLDEN_DIR / "sample_song.html"

    import os
    if os.environ.get("UPDATE_GOLDEN"):
        golden_path.write_text(rendered, encoding="utf-8")

    expected = golden_path.read_text(encoding="utf-8")
    assert rendered == expected
    assert layout == "single"
    assert has_bars is False


BARS_CONTENT = (
    "[Intro]\n"
    "[ch]D[/ch]  [ch]A[/ch]  [ch]G[/ch]\n"
    "\n"
    "[Verse 1]\n"
    "[ch]Em7[/ch]\n"
    "If you smile at me\n"
    "\n"
    "[Bars]\n"
    "Intro: |D A|G|\n"
    "Verse: |Em7|\n"
)


def test_make_song_html_with_bars_matches_golden_file():
    """Regression guard for the [Bars]-rendering additions (barlines,
    hidden bars-source block, embedded bar-data JSON). Regenerate the same
    way as the sibling test above after an intentional template change:
        UPDATE_GOLDEN=1 pytest tests/test_render_golden.py
    """
    rendered, layout, has_bars = make_song_html(
        "Golden Bars Testsang", "Golden Artist", "D", "", BARS_CONTENT, "", "120"
    )
    golden_path = GOLDEN_DIR / "sample_song_bars.html"

    import os
    if os.environ.get("UPDATE_GOLDEN"):
        golden_path.write_text(rendered, encoding="utf-8")

    expected = golden_path.read_text(encoding="utf-8")
    assert rendered == expected
    assert layout == "single"
    assert has_bars is True
