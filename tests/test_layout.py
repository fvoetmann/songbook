import pytest

from add_song import decide_layout, paginate_sections, LINES_PER_PAGE, section_line_count


@pytest.mark.parametrize("total_lines,max_width,expected", [
    (LINES_PER_PAGE, 10, "single"),
    (LINES_PER_PAGE + 1, 10, "double"),
    (130, 65, "double"),
    (130, 66, "multi"),
    (131, 65, "multi"),
    (1, 1, "single"),
])
def test_decide_layout_boundaries(total_lines, max_width, expected):
    assert decide_layout(total_lines, max_width) == expected


def _section(n_lines, header="[Verse]"):
    body = "\n".join(f"line{i}" for i in range(n_lines - (1 if header else 0)))
    return header, body


def test_section_line_count_includes_header():
    header, body = _section(5)
    assert section_line_count(header, body) == 5


def test_paginate_sections_packs_whole_sections_per_page():
    sections = [_section(20), _section(20), _section(20)]
    pages = paginate_sections(sections, lines_per_page=50)
    # First two sections (40 lines) fit on page 1; third pushes to page 2.
    assert len(pages) == 2
    assert len(pages[0]) == 2
    assert len(pages[1]) == 1


def test_paginate_sections_never_splits_a_single_section():
    oversized = _section(100)
    sections = [_section(10), oversized, _section(10)]
    pages = paginate_sections(sections, lines_per_page=50)
    # The oversized section gets its own overflowing page rather than being split.
    assert any(oversized in page for page in pages)
    for page in pages:
        assert sum(section_line_count(h, b) for h, b in page) <= 50 or len(page) == 1


def test_paginate_sections_empty_input_returns_one_empty_page():
    assert paginate_sections([]) == [[]]
