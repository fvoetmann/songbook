from add_song import extract_ug_data, get_song_info, unwrap_view_source


def test_extract_and_get_song_info_on_real_samples(ug_sample_path):
    html_text = ug_sample_path.read_text(encoding="utf-8", errors="replace")
    data = extract_ug_data(html_text)
    title, artist, key, capo, content = get_song_info(data)

    assert title and title != "Ukendt sang"
    assert artist and artist != "Ukendt artist"
    assert isinstance(key, str)
    assert isinstance(capo, str)
    assert content.strip()


def test_extract_ug_data_raises_on_unrelated_html():
    try:
        extract_ug_data("<html><body>Not a UG page</body></html>")
        assert False, "forventede ValueError"
    except ValueError:
        pass


def test_unwrap_view_source_passthrough_for_plain_html():
    plain = "<html><body><p>hej</p></body></html>"
    assert unwrap_view_source(plain) == plain
