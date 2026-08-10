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
    rendered, layout = make_song_html(
        "Golden Testsang", "Golden Artist", "Am", "2", SAMPLE_CONTENT, "https://example.com/song"
    )
    golden_path = GOLDEN_DIR / "sample_song.html"

    import os
    if os.environ.get("UPDATE_GOLDEN"):
        golden_path.write_text(rendered, encoding="utf-8")

    expected = golden_path.read_text(encoding="utf-8")
    assert rendered == expected
    assert layout == "single"
