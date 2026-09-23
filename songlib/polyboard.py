"""Eksport af [Bars]-takt-data til polyboard (live-coding-REPL med Tidal/Strudel-
lignende mini-notation).

Input er JSON-strukturen fra `#bar-data` i sang-HTML'en (se
`bars.build_bar_timeline_json`). Output er tekst der kan indsættes i polyboard:
`def`-linjer og en `d1 # note (...)/N`-linje hvor 1 cyklus = 1 takt.

Polyboards parser afviser `$liste`-opslag (`d3'$maj`) inde i andre `def`-kroppe,
så akkorder skrives som inline-lister: `d3'[0 4 7]`.
"""

import json
import re

from .chords import parse_chord_name

NOTE_NAMES = ["c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b"]
_MIN_SAVING = 6      # mindste token-besparelse for at udtrække et gentaget mønster
_MAX_PATTERN_LEN = 16  # længste mønster (i enheder) der søges efter
_DANISH = str.maketrans({"æ": "ae", "ø": "oe", "å": "aa"})


# ── Læsning fra sang-HTML ────────────────────────────────────────────────────

_BAR_DATA_RE = re.compile(r'<script[^>]*id="bar-data"[^>]*>(.*?)</script>', re.S)
_TEMPO_RE = re.compile(r'<meta name="tempo" content="([^"]*)"')


def bar_data_from_html(html_text: str):
    """Takt-data (dict) fra en sang-HTML, eller None hvis sangen ikke har aktiv [Bars]."""
    m = _BAR_DATA_RE.search(html_text)
    return json.loads(m.group(1)) if m else None


def tempo_from_html(html_text: str) -> str:
    """Sangens BPM som tekst (standard 120, som i browserens metronom)."""
    m = _TEMPO_RE.search(html_text)
    try:
        return str(float(m.group(1)) if "." in m.group(1) else int(m.group(1))) if m else "120"
    except ValueError:
        return "120"


# ── Akkord → toner ───────────────────────────────────────────────────────────

def _root_midi(semi: int) -> int:
    """Rod i området A2–G#3 (c4 = 60), så akkorderne ligger tæt på hinanden."""
    return 48 + semi if semi < 9 else 36 + semi


def _note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def chord_stack(name: str):
    """(laveste_midi, intervaller) for en akkord, eller None hvis ukendt.

    Slash-akkorder (D/F#) lægges som omvending med basnoden nederst:
    intervallerne regnes fra basnoden og indeholder altid 0."""
    parsed = parse_chord_name(name)
    if parsed is None:
        return None
    root, ivs, bass = parsed
    if bass is None or bass == root:
        return _root_midi(root), sorted(set(ivs))
    tones = {(root + iv - bass) % 12 for iv in ivs} | {0}
    return _root_midi(bass), sorted(tones)


# ── Takt-data → enheder ──────────────────────────────────────────────────────
# En enhed er (akkorder, antal_takter). Tom akkord-tuple = pause. `%` forlænger
# den forrige enhed, så "|Em7|%|%|%|" bliver én enhed (('Em7',), 4).

def bar_data_to_units(bar_data: dict) -> list:
    """[(label, [enhed, ...]), ...] i sangens rækkefølge; tomme sektioner udelades."""
    out = []
    for section in bar_data.get("sections", []):
        units = []
        for bar in section.get("bars", []):
            if bar.get("repeat"):
                if units:
                    chords, n = units[-1]
                    units[-1] = (chords, n + 1)
                else:
                    units.append(((), 1))  # ingen forrige takt at gentage
            elif bar.get("rest"):
                if units and units[-1][0] == ():
                    units[-1] = ((), units[-1][1] + 1)
                else:
                    units.append(((), 1))
            else:
                units.append((tuple(bar.get("chords", [])), 1))
        if units:
            out.append((section.get("section", ""), units))
    return out


def expand_units(units: list, patterns: dict = None) -> list:
    """Fold enheder (og evt. mønster-referencer) ud til én akkord-tuple pr. takt.
    En forlænget enhed giver samme akkorder i alle sine takter. Bruges af tests
    til at sammenligne med de oprindelige takter."""
    patterns = patterns or {}
    out = []
    for sym in units:
        if isinstance(sym, str):
            out.extend(expand_units(patterns[sym], patterns))
        else:
            chords, n = sym
            out.extend([chords] * n)
    return out


# ── Gentagne mønstre ─────────────────────────────────────────────────────────

def _count_nonoverlapping(seqs: list, cand: tuple) -> int:
    n, L = 0, len(cand)
    for seq in seqs:
        i = 0
        while i + L <= len(seq):
            if tuple(seq[i:i + L]) == cand:
                n += 1
                i += L
            else:
                i += 1
    return n


def _replace(seq: list, cand: tuple, ref: str) -> list:
    out, i, L = [], 0, len(cand)
    while i < len(seq):
        if i + L <= len(seq) and tuple(seq[i:i + L]) == cand:
            out.append(ref)
            i += L
        else:
            out.append(seq[i])
            i += 1
    return out


def extract_patterns(seqs: list):
    """Udtræk gentagne, sammenhængende enhedssekvenser (inden for én sektion) som
    navngivne mønstre. Greedy: det mønster der sparer flest tokens tages først, og
    senere mønstre kan indeholde referencer til tidligere. Returnerer
    (nye_sekvenser, {'pat1': [symboler], ...}) – symboler er enheder eller
    referencer (strenge)."""
    seqs = [list(s) for s in seqs]
    patterns = {}
    while True:
        cands = set()
        for seq in seqs:
            for L in range(2, min(_MAX_PATTERN_LEN, len(seq)) + 1):
                for i in range(len(seq) - L + 1):
                    cands.add(tuple(seq[i:i + L]))
        whole = {tuple(seq) for seq in seqs}  # hele sektioner deles allerede via ens indhold
        best, best_key = None, None
        for cand in cands - whole:
            occ = _count_nonoverlapping(seqs, cand)
            if occ < 2:
                continue
            saving = occ * len(cand) - (len(cand) + occ)
            if saving < _MIN_SAVING:
                continue
            key = (saving, len(cand))
            if best_key is None or key > best_key:
                best, best_key = cand, key
        if best is None:
            return seqs, patterns
        ref = f"pat{len(patterns) + 1}"
        patterns[ref] = list(best)
        seqs = [_replace(s, best, ref) for s in seqs]


# ── Rendering ────────────────────────────────────────────────────────────────

def _def_name(label: str, used: set) -> str:
    """Sektions-label → gyldigt def-navn (kun bogstaver/cifre, starter med bogstav),
    unikt blandt `used` – også når basgangens `b`-præfiks lægges på."""
    base = re.sub(r"[^a-z0-9]", "", label.lower().translate(_DANISH)) or "section"
    if not base[0].isalpha():
        base = "s" + base
    name, k = base, 1
    while (name in used or "b" + name in used
           or (name.startswith("b") and name[1:] in used)):
        k += 1
        name = f"{base}{k}"
    used.add(name)
    return name


def render_polyboard(bar_data: dict, tempo="120", *, title: str = "", artist: str = "",
                     sound: str = "arpy", bass: bool = False, bass_sound: str = "arpy",
                     restrike: bool = False):
    """Byg polyboard-tekst ud fra bar-data. Returnerer (tekst, advarsler).

    sound: polyboard-lyd til akkordlaget. bass: tilføj et grundtone-lag på slot d2
    (MIDI-tal, så tallene ikke forveksles med slot-navnet) med lyden bass_sound. restrike: genanslå
    forlængede akkorder hver takt (`!N`) i stedet for ét langt anslag (`@N`)."""
    warnings = []
    labelled = bar_data_to_units(bar_data)
    if not labelled:
        raise ValueError("Ingen takter at eksportere")
    labels = [label for label, _ in labelled]
    # Mønstre søges kun i unikt sektions-indhold: ens sektioner deler alligevel én def
    uniq = list(dict.fromkeys(tuple(units) for _, units in labelled))
    new_uniq, patterns = extract_patterns(uniq)
    rewritten = dict(zip(uniq, new_uniq))
    seqs = [rewritten[tuple(units)] for _, units in labelled]

    pattern_bars = {}
    for ref, body in patterns.items():
        pattern_bars[ref] = sum(pattern_bars[s] if isinstance(s, str) else s[1] for s in body)

    def bars_of(sym):
        return pattern_bars[sym] if isinstance(sym, str) else sym[1]

    # Identisk indhold deler én def (fx samme omkvæd tre gange)
    used = set(patterns)
    section_defs = {}   # indhold -> (navn, takter)
    order = []          # (navn, takter) i sangens rækkefølge
    for label, seq in zip(labels, seqs):
        key = tuple(seq)
        if key not in section_defs:
            section_defs[key] = (_def_name(label, used), sum(bars_of(s) for s in seq))
        order.append(section_defs[key])
    total = sum(n for _, n in order)

    unknown = set()

    def chord_token(unit):
        chords, n = unit
        if not chords:
            return "~" if n == 1 else f"~!{n}"
        toks = []
        for c in chords:
            if c is None:  # pause-slot der deler takten med en rigtig akkord (fx "...C")
                toks.append("~")
                continue
            st = chord_stack(c)
            if st is None:
                unknown.add(c)
                toks.append("~")
            else:
                low, ivs = st
                toks.append(f"{_note_name(low)}'[{' '.join(map(str, ivs))}]")
        tok = toks[0] if len(toks) == 1 else "[" + " ".join(toks) + "]"
        if n == 1:
            return tok
        if len(toks) == 1 and not restrike and tok != "~":
            return f"{tok}@{n}"
        return f"{tok}!{n}"

    def bass_token(unit):
        chords, n = unit
        if not chords:
            return "~" if n == 1 else f"~!{n}"
        toks = []
        for c in chords:
            if c is None:
                toks.append("~")
                continue
            st = chord_stack(c)
            toks.append("~" if st is None else str(st[0] - 12))
        tok = toks[0] if len(toks) == 1 else "[" + " ".join(toks) + "]"
        return tok if n == 1 else f"{tok}!{n}"

    def layer(prefix, slot, sound_name, token):
        def sym_str(sym):
            return f"${prefix}{sym}@{pattern_bars[sym]}" if isinstance(sym, str) else token(sym)
        lines = []
        for ref, body in patterns.items():
            lines.append(f"def {prefix}{ref} = ({' '.join(sym_str(s) for s in body)})")
        for key, (name, _) in section_defs.items():
            lines.append(f"def {prefix}{name} = ({' '.join(sym_str(s) for s in key)})")
        uses = " ".join(f"${prefix}{name}@{n}" for name, n in order)
        lines.append(f"{slot} # note ({uses})/{total} # s {sound_name}")
        return lines

    head = f"{artist} – {title}" if artist and title else (title or artist)
    lines = [f"-- Polyboard-eksport{' af ' + head if head else ''} (export_polyboard.py)",
             f"-- {total} takter i 4/4; 1 cyklus = 1 takt",
             "-- Kør alle linjer (Skift+Ctrl+Enter). Mønstret er låst til transportens cyklus:",
             "-- for at starte ved takt 1, så mute/unmute globalt før start (genstarter fra cyklus 0).",
             f"setbpm {tempo}", ""]
    lines += layer("", "d1", sound, chord_token)
    if bass:
        lines += ["", "-- Basgang: grundtone på 1. slag i hver takt (MIDI-tal)"]
        lines += layer("b", "d2", bass_sound, bass_token)

    for c in sorted(unknown):
        warnings.append(f"Ukendt akkord '{c}' – erstattet med pause")
    return "\n".join(lines) + "\n", warnings
