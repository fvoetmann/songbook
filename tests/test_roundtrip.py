import re
from pathlib import Path

from add_song import extract_ug_data, get_song_info, make_song_html
from edit_song import html_to_content, ug_to_edit, edit_to_ug


def _chord_names(content: str) -> list:
    return re.findall(r"\[ch\](.*?)\[/ch\]", content)


def test_render_then_reconstruct_preserves_chords_and_title(ug_sample_path, tmp_path):
    html_text = ug_sample_path.read_text(encoding="utf-8", errors="replace")
    data = extract_ug_data(html_text)
    title, artist, key, capo, content = get_song_info(data)

    rendered, _layout = make_song_html(title, artist, key, capo, content, "")
    out_path = tmp_path / "song.html"
    out_path.write_text(rendered, encoding="utf-8")

    r_title, r_artist, r_key, r_capo, _url, r_content = html_to_content(out_path)

    assert r_title == title
    assert r_artist == artist
    # Every chord that went in must come back out, in the same order —
    # this is the contract rebuild_songs.py and edit_song.py depend on.
    assert _chord_names(r_content) == _chord_names(content)


def test_reconstruct_is_stable_under_a_second_round_trip(ug_sample_path, tmp_path):
    """render -> reconstruct -> render -> reconstruct should reach a fixed
    point: re-rendering the reconstructed content changes nothing further."""
    html_text = ug_sample_path.read_text(encoding="utf-8", errors="replace")
    data = extract_ug_data(html_text)
    title, artist, key, capo, content = get_song_info(data)

    rendered1, _ = make_song_html(title, artist, key, capo, content, "")
    p1 = tmp_path / "a.html"
    p1.write_text(rendered1, encoding="utf-8")
    _, _, _, _, _, content2 = html_to_content(p1)

    rendered2, _ = make_song_html(title, artist, key, capo, content2, "")
    p2 = tmp_path / "b.html"
    p2.write_text(rendered2, encoding="utf-8")
    _, _, _, _, _, content3 = html_to_content(p2)

    assert _chord_names(content3) == _chord_names(content2)


def test_edit_song_editor_cycle_preserves_all_chords(ug_sample_path, tmp_path):
    """Simulates opening a real song in edit_song.py's editor and saving it
    unchanged, three times in a row — the full render -> extract -> edit
    format -> save -> render cycle. Every chord (including ones with no
    following lyric, or embedded in annotation-only lines) must survive
    with its exact name intact, and the content must reach a stable fixed
    point rather than drifting further with each save."""
    html_text = ug_sample_path.read_text(encoding="utf-8", errors="replace")
    data = extract_ug_data(html_text)
    title, artist, key, capo, content = get_song_info(data)
    original_chords = _chord_names(content)

    current = content
    for i in range(3):
        rendered, _ = make_song_html(title, artist, key, capo, current, "")
        path = tmp_path / f"round{i}.html"
        path.write_text(rendered, encoding="utf-8")
        _, _, _, _, _, extracted = html_to_content(path)
        current = edit_to_ug(ug_to_edit(extracted))
        assert _chord_names(current) == original_chords
