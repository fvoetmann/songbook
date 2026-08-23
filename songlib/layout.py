"""Layout-beslutning og paginering af sangindhold."""

import re


def parse_sections(content: str) -> list:
    """Split content into [(header, body)] pairs with blank lines removed."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"\[/?tab\]", "", content)
    parts = re.split(r"(\[[A-Z][^\]]*\])", content)
    sections = []
    current_header = ""
    for part in parts:
        if re.match(r"^\[[A-Z][^\]]*\]$", part):
            current_header = part
        else:
            body = part.strip("\n")
            if body.strip():
                sections.append((current_header, body))
            current_header = ""
    return sections


TAB_STRING_LINE = re.compile(r"^[eEaAdDgGbB]\|", re.MULTILINE)


def is_tab_section(body: str) -> bool:
    """True if body contains guitar string notation (e|, B|, etc.). Matches
    string letters case-insensitively since sources vary (e.g. "EADGBe" vs
    all-lowercase "eadgbe")."""
    return bool(TAB_STRING_LINE.search(body))


def split_mixed(header: str, body: str) -> list:
    """Split a section that mixes chord+lyric and guitar tab into alternating
    parts. A section can contain more than one tab run (e.g. an intro riff
    followed by ordinary verse lines that just happen to share the section
    with it), so this walks the whole body rather than assuming the tab
    block is a single run at the end."""
    lines = body.split("\n")
    segments = []  # [(is_tab, [line, ...]), ...]
    for line in lines:
        is_tab_line = bool(TAB_STRING_LINE.match(line))
        if segments and segments[-1][0] == is_tab_line:
            segments[-1][1].append(line)
        else:
            segments.append([is_tab_line, [line]])

    # Pull a trailing caption line from a chord segment into the tab segment
    # that immediately follows it, but never cross a blank line: a caption
    # sits directly above its tab with no gap, while unrelated lyric content
    # earlier in the section is separated by one (this matters most after a
    # round-trip through edit_song.py's html_to_content, which can otherwise
    # glue a relocated tab block onto a much earlier section's trailing
    # lyric line).
    for i in range(len(segments) - 1):
        is_tab, seg_lines = segments[i]
        next_is_tab, next_lines = segments[i + 1]
        if is_tab or not next_is_tab:
            continue
        while (
            seg_lines
            and seg_lines[-1].strip()
            and not re.search(r"\[ch\]", seg_lines[-1])
        ):
            next_lines.insert(0, seg_lines.pop())

    result = []
    current_header = header
    for _, seg_lines in segments:
        # Drop leading/trailing blank lines, but never strip() the joined
        # text: a chord line's leading spaces position its first chord and
        # must survive when that line opens the segment (e.g. a passing
        # chord placed mid-lyric rather than under the first word).
        lines = list(seg_lines)
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        text = "\n".join(lines)
        if not text:
            continue
        result.append((current_header, text))
        current_header = ""
    return result


def count_lines(sections: list) -> tuple:
    """Return (total_non_blank_lines, max_chord_width, max_text_width) ignoring tab sections."""
    total, max_chord_width, max_text_width = 0, 0, 0
    for header, body in sections:
        if is_tab_section(body):
            continue
        if header:
            total += 1
        for line in body.split("\n"):
            if line.strip():
                total += 1
                clean = re.sub(r"\[ch\](.*?)\[/ch\]", r"\1", line)
                max_text_width = max(max_text_width, len(clean))
                if "[ch]" in line:
                    max_chord_width = max(max_chord_width, len(clean))
    return total, max_chord_width, max_text_width


LINES_PER_PAGE = 54


def decide_layout(total_lines: int, max_width: int) -> str:
    if total_lines <= LINES_PER_PAGE:
        return "single"
    elif total_lines <= 130 and max_width <= 65:
        return "double"
    else:
        return "multi"


def section_line_count(header: str, body: str) -> int:
    """Non-blank line count for one section, matching count_lines()'s per-section logic."""
    total = 1 if header else 0
    for line in body.split("\n"):
        if line.strip():
            total += 1
    return total


def paginate_sections(sections: list, lines_per_page: int = LINES_PER_PAGE) -> list:
    """Greedily pack whole sections into page buckets of ~lines_per_page lines each.
    A single section longer than the budget gets its own (overflowing) page rather
    than being split mid-section."""
    pages, current, current_lines = [], [], 0
    for h, b in sections:
        n = section_line_count(h, b)
        if current and current_lines + n > lines_per_page:
            pages.append(current)
            current, current_lines = [], 0
        current.append((h, b))
        current_lines += n
    if current:
        pages.append(current)
    return pages or [[]]