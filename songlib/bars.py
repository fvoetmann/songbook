"""Takt-notation: [Bars]-sektionen, matchning mod eksisterende akkorder,
og default-takt-generering.

Se CLAUDE.md for grammatikken. Dette modul er bevidst holdt isoleret fra
akkord-parsing/round-trip-koden i chords.py/render.py/edit_song.py: det
kender kun til rå "[ch]navn[/ch]"-strenge og rører aldrig selve
akkordnavnene eller den skrøbelige inline-chord-splitning.
"""

import re
from dataclasses import dataclass, field

BARS_HEADER = "[Bars]"
BARS_DRAFT_HEADER = "[Bars draft]"


def is_bars_section(header: str) -> bool:
    return header.strip().lower() == BARS_HEADER.lower()


def is_bars_draft_section(header: str) -> bool:
    """[Bars draft] holder samme indhold/format som [Bars], men er bevidst
    inaktiv: skjult fra sang-visningen og ikke en del af takstreg-matchning,
    indtil sektionen omdøbes til [Bars] (fx via edit_song.py). Bruges af
    add_draft_bars.py til at foreslå takter for hele biblioteket uden at
    påvirke visningen af nogen sang før den enkelte sang er gennemgået."""
    return header.strip().lower() == BARS_DRAFT_HEADER.lower()


@dataclass
class Bar:
    chords: list = field(default_factory=list)  # tom for pause-/gentagelsestakter
    is_repeat: bool = False
    is_rest: bool = False


@dataclass
class MatchResult:
    header: str
    bars: list  # list[Bar] – den fulde, flade takt-sekvens
    # occurrence-indeks (i sektionens [ch]-rækkefølge) der skal have en taktstreg foran sig
    bar_starts: set
    # occurrence-indeks -> liste af Bar (pause/gentagelse) der indsættes lige efter
    extra_after: dict


_LABEL_LINE = re.compile(r"^\s*([^:\n]+):\s*(.+?)\s*$")


def _parse_bar_sequence(seq: str) -> list:
    seq = seq.strip()
    if seq.startswith("|"):
        seq = seq[1:]
    if seq.endswith("|"):
        seq = seq[:-1]
    bars = []
    for token in seq.split("|"):
        token = token.strip()
        if not token:
            continue
        if token == "%":
            bars.append(Bar(is_repeat=True))
        elif token == ".":
            bars.append(Bar(is_rest=True))
        else:
            bars.append(Bar(chords=token.split()))
    return bars


def parse_bars_meta(body: str) -> dict:
    """Parse en [Bars]-sektions krop til {label: [Bar, ...]}."""
    result = {}
    for line in body.splitlines():
        if not line.strip():
            continue
        m = _LABEL_LINE.match(line)
        if not m:
            continue
        label, seq = m.group(1).strip(), m.group(2).strip()
        result[label] = _parse_bar_sequence(seq)
    return result


def extract_chord_sequence(body: str) -> list:
    """Alle [ch]...[/ch]-akkordnavne i body, i dokumentrækkefølge (inkl. gentagne navne)."""
    return [m.group(1) for m in re.finditer(r"\[ch\](.*?)\[/ch\]", body)]


def find_label_for_header(header: str, labels) -> str:
    """Find den [Bars]-label der hører til en rigtig sektions-header. Eksakt
    match (case-insensitive) foretrækkes; ellers prefix-match (label er et
    prefix af header-teksten, fx 'Vers' matcher '[Vers 1]')."""
    clean_header = header.strip("[]").strip().lower()
    labels = list(labels)
    for label in labels:
        if label.strip().lower() == clean_header:
            return label
    for label in labels:
        low = label.strip().lower()
        if low and clean_header.startswith(low):
            return label
    return None


def _flatten_real_chords(bars: list) -> list:
    """De 'rigtige' akkorder i en takt-sekvens (uden %/.) i rækkefølge – én
    forekomst pr. akkord i en delt takt (fx 'D A' -> ['D', 'A'])."""
    out = []
    for bar in bars:
        if bar.is_repeat or bar.is_rest:
            continue
        out.extend(bar.chords)
    return out


def match_section(bars: list, chord_sequence: list, header: str = ""):
    """Match en [Bars]-takt-sekvens mod en sektions faktiske [ch]-forekomster
    (i dokumentrækkefølge). Returnerer None ved uoverensstemmelse i antal
    eller navne – ingen visuel ændring foretages i så fald."""
    if _flatten_real_chords(bars) != chord_sequence:
        return None

    bar_starts = set()
    extra_after = {}
    occ_idx = -1
    for bar in bars:
        if bar.is_repeat or bar.is_rest:
            extra_after.setdefault(occ_idx, []).append(bar)
            continue
        for j in range(len(bar.chords)):
            occ_idx += 1
            if j == 0:
                bar_starts.add(occ_idx)
    return MatchResult(header=header, bars=bars, bar_starts=bar_starts, extra_after=extra_after)


def build_bar_timeline_json(matches) -> dict:
    """matches: iterable af MatchResult, i dokumentrækkefølge. Bygger
    JSON-payload til afspilning. Tager bevidst en liste/iterable (ikke et
    dict keyet på header-tekst) fordi samme sektions-label (fx "[Chorus]")
    kan optræde flere gange i en sang – et dict ville kollapse de gentagne
    forekomster til én og stille droppe resten af taktdataen."""
    sections = []
    for result in matches:
        bars_json = [
            {"chords": bar.chords, "repeat": bar.is_repeat, "rest": bar.is_rest}
            for bar in result.bars
        ]
        sections.append({"section": result.header.strip("[]").strip(), "bars": bars_json})
    return {"beats_per_bar": 4, "sections": sections}


def generate_default_bars(content: str, header: str = BARS_HEADER) -> str:
    """Byg en naiv [Bars]-krop ('1 akkord = 1 takt', ingen %/.) ud fra de
    akkorder der allerede står i sangens sektioner. Bruges af
    add_default_bars.py (og add_draft_bars.py, med header='[Bars draft]')
    til at give et udgangspunkt at rette i."""
    from .layout import is_tab_section, parse_sections

    lines = []
    seen_headers = set()
    for h, body in parse_sections(content):
        if not h or is_bars_section(h) or is_bars_draft_section(h) or h in seen_headers:
            continue
        if is_tab_section(body):
            continue
        chords = extract_chord_sequence(body)
        if not chords:
            continue
        seen_headers.add(h)
        label = h.strip("[]").strip()
        lines.append(f"{label}: |" + "|".join(chords) + "|")

    if not lines:
        return ""
    return f"{header}\n" + "\n".join(lines) + "\n"


def validate_bars(content: str) -> list:
    """Kør matchningen og returnér en liste af advarsler (som strenge) for
    [Bars]-labels der ikke fandt/matchede nogen sektion. Bruges af
    edit_song.py/store.py til at printe advarsler ved gem – rører ikke selve
    renderingen."""
    from .layout import is_tab_section, split_mixed, parse_sections

    sections = parse_sections(content)
    split = []
    for h, b in sections:
        split.extend(split_mixed(h, b))

    bars_bodies = [b for h, b in split if is_bars_section(h)]
    if not bars_bodies:
        return []

    bars_meta = {}
    for b in bars_bodies:
        bars_meta.update(parse_bars_meta(b))

    chord_sections = [
        (h, b) for h, b in split
        if not is_bars_section(h) and not is_bars_draft_section(h) and not is_tab_section(b)
    ]

    matched_labels = set()
    warnings = []
    for h, b in chord_sections:
        label = find_label_for_header(h, bars_meta.keys())
        if label is None:
            continue
        if match_section(bars_meta[label], extract_chord_sequence(b), h) is not None:
            matched_labels.add(label)
        else:
            warnings.append(
                f"[Bars] '{label}' matcher ikke akkorderne i {h} – "
                f"taktstreger vises ikke for denne sektion."
            )

    for label in bars_meta:
        if label not in matched_labels and not any(
            find_label_for_header(h, [label]) for h, _ in chord_sections
        ):
            warnings.append(f"[Bars] '{label}' matcher ingen sektion i sangen.")

    return warnings
