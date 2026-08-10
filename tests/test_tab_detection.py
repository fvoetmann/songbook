import pytest

from add_song import is_tab_section, split_mixed


@pytest.mark.parametrize("body", [
    "e|--0--2--\nB|--1--3--\n",
    "E|--0--2--\ne|--1--3--\n",
    # All-lowercase string letters: some UG sources (and hand-typed tabs)
    # don't follow the "EADGBe" mixed-case convention.
    "e|--0--2--\nb|--1--3--\ng|--0--0--\nd|--2--2--\na|--2--2--\ne|--0--0--\n",
])
def test_is_tab_section_accepts_any_case(body):
    assert is_tab_section(body)


@pytest.mark.parametrize("body", [
    "just some lyrics\nwith a chord [ch]Am[/ch]\n",
    "e---0----5----0-------2---0---4-----2----\n",  # dashes, no pipe: not tab notation
])
def test_is_tab_section_rejects_non_tab_text(body):
    assert not is_tab_section(body)


def test_split_mixed_detects_lowercase_tab_lines():
    header = "[Intro]"
    body = "[ch]Am[/ch] some lyrics\ne|--0--2--\nb|--1--3--\n"
    result = split_mixed(header, body)
    assert len(result) == 2
    assert result[0] == (header, "[ch]Am[/ch] some lyrics")
    assert result[1][0] == ""
    assert "e|--0--2--" in result[1][1]
