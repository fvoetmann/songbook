import json

import add_song


def test_process_file_end_to_end(tmp_path, monkeypatch, ug_sample_path):
    """Full pipeline (parse -> render -> write html -> update songs.json ->
    rebuild index) against a temp directory, so it never touches the real
    songs/, songs.json or index.html in the repo."""
    songs_dir = tmp_path / "songs"
    songs_data = tmp_path / "songs.json"
    index_file = tmp_path / "index.html"

    monkeypatch.setattr(add_song, "SONGS_DIR", songs_dir)
    monkeypatch.setattr(add_song, "SONGS_DATA", songs_data)
    monkeypatch.setattr(add_song, "INDEX_FILE", index_file)

    add_song.process_file(ug_sample_path)

    songs = json.loads(songs_data.read_text(encoding="utf-8"))
    assert len(songs) == 1
    entry = songs[0]
    assert (songs_dir / entry["file"]).exists()
    assert entry["source"] == ug_sample_path.name
    assert "hash" in entry

    assert index_file.exists()
    index_html = index_file.read_text(encoding="utf-8")
    assert entry["file"] in index_html


def test_process_file_is_idempotent_on_unchanged_output(tmp_path, monkeypatch, ug_sample_path):
    songs_dir = tmp_path / "songs"
    songs_data = tmp_path / "songs.json"
    index_file = tmp_path / "index.html"

    monkeypatch.setattr(add_song, "SONGS_DIR", songs_dir)
    monkeypatch.setattr(add_song, "SONGS_DATA", songs_data)
    monkeypatch.setattr(add_song, "INDEX_FILE", index_file)

    add_song.process_file(ug_sample_path)
    songs_first = json.loads(songs_data.read_text(encoding="utf-8"))

    # Re-processing the same untouched source must update in place, not
    # trip the "manuelt redigeret" conflict path or duplicate the entry.
    add_song.process_file(ug_sample_path)
    songs_second = json.loads(songs_data.read_text(encoding="utf-8"))

    assert len(songs_second) == 1
    assert songs_second == songs_first
    assert not list(songs_dir.glob("*_UGversion.html"))
