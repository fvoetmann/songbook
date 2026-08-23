"""Akkordteori, voicings og transponering.

Indeholder INSTRUMENTS/NOTE_SEMI/ACCIDENTAL/CHORD_TYPES (holdt i sync med den
indlejrede JavaScript i templates.py) samt parse/generate/transponer-funktioner.
"""

import re

# ── Instrumentkonfigurationer ────────────────────────────────────────────────
# strings: MIDI-notenumre fra tykkeste til tyndeste streng
# Ukulele: re-entrant G (G4=67 er højere end C4=60)
# Mandolin: GDAE ligesom violin
# Banjo: 5. streng (sidste i listen) er en kort strengesnor der starter ved bånd 5 –
# kan i praksis kun spilles åben, aldrig gribes. Modelleres med 'fixed_open'.
STRING_OPEN = [40, 45, 50, 55, 59, 64]  # beholdes for bagudkompatibilitet
MAX_FRET = 9

INSTRUMENTS = {
    'guitar':   {'strings': [40, 45, 50, 55, 59, 64], 'max_fret': 9, 'min_play': 4, 'span': 2},
    'ukulele':  {'strings': [67, 60, 64, 69],          'max_fret': 7, 'min_play': 4, 'span': 3, 'reentrant': True},
    'mandolin': {'strings': [55, 62, 69, 76],          'max_fret': 7, 'min_play': 3, 'span': 3},
    'banjo':    {'strings': [50, 55, 59, 62, 67],      'max_fret': 7, 'min_play': 3, 'span': 3, 'reentrant': True, 'fixed_open': [4]},
}

NOTE_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
ACCIDENTAL = {'#': 1, 'b': -1}

# Akkordtype-suffixer → intervaller fra rod (sorteret på længde, længst først)
CHORD_TYPES = sorted([
    ('mmaj7',   [0, 3, 7, 11]),
    ('m(maj7)', [0, 3, 7, 11]),
    ('maj7',    [0, 4, 7, 11]),
    ('maj9',    [0, 2, 4, 7, 11]),
    ('7sus4',   [0, 5, 7, 10]),
    ('dim7',    [0, 3, 6, 9]),
    ('sus2',    [0, 2, 7]),
    ('sus4',    [0, 5, 7]),
    ('add9',    [0, 2, 4, 7]),
    ('aug',     [0, 4, 8]),
    ('dim',     [0, 3, 6]),
    ('m7',      [0, 3, 7, 10]),
    ('m6',      [0, 3, 7, 9]),
    ('m9',      [0, 2, 3, 7, 10]),
    ('maj',     [0, 4, 7]),
    ('m',       [0, 3, 7]),
    ('7',       [0, 4, 7, 10]),
    ('6',       [0, 4, 7, 9]),
    ('9',       [0, 2, 4, 7, 10]),
    ('5',       [0, 7]),
    ('2',       [0, 2, 7]),
    ('',        [0, 4, 7]),
], key=lambda x: -len(x[0]))


def parse_chord_name(name: str):
    """Returnér (rod_semi, intervaller, bas_semi|None) eller None."""
    bass_semi = None
    slash = name.find('/')
    if slash > 0:
        b = name[slash + 1:]
        if b and b[0] in NOTE_SEMI:
            bass_semi = NOTE_SEMI[b[0]]
            if len(b) > 1 and b[1] in ACCIDENTAL:
                bass_semi = (bass_semi + ACCIDENTAL[b[1]]) % 12
        name = name[:slash]

    if not name or name[0] not in NOTE_SEMI:
        return None
    root = NOTE_SEMI[name[0]]
    i = 1
    if i < len(name) and name[i] in ACCIDENTAL:
        root = (root + ACCIDENTAL[name[i]]) % 12
        i += 1

    suffix = name[i:]
    for suf, ivs in CHORD_TYPES:
        if suffix == suf:
            return root, ivs, bass_semi
    return None


def generate_voicings(root: int, ivs: list, bass=None, n: int = 6, instr: dict = None) -> list:
    """Top-n spillbare greb som liste af frets (-1=muted, 0=åben, N=fret)."""
    from itertools import product as iproduct

    if instr is None:
        instr = INSTRUMENTS['guitar']
    string_open = instr['strings']
    n_str = len(string_open)
    max_fret = instr['max_fret']
    min_play = instr['min_play']
    max_span = instr['span']

    tones = {(root + i) % 12 for i in ivs}
    fixed_open = set(instr.get('fixed_open', []))

    opts = []
    for s in range(n_str):
        if s in fixed_open:
            opts.append([0])
            continue
        o = {-1}
        for t in tones:
            diff = (t - string_open[s]) % 12
            if diff <= max_fret:
                o.add(diff)
        opts.append(sorted(o))

    valid = []
    for combo in iproduct(*opts):
        fs = list(combo)
        playing = [f for f in fs if f >= 0]

        if len(playing) < min_play:
            continue

        pressed = [f for f in fs if f > 0]
        if pressed and max(pressed) - min(pressed) > max_span:
            continue

        played = {(string_open[s] + fs[s]) % 12 for s in range(n_str) if fs[s] >= 0}

        if root % 12 not in played:
            continue
        if len(ivs) > 1 and (root + ivs[1]) % 12 not in played:
            continue

        if bass is not None:
            # Laveste absolutte tonehøjde skal være basnoden (virker med re-entrant tuning)
            lo_abs = min(string_open[s] + fs[s] for s in range(n_str) if fs[s] >= 0)
            if lo_abs % 12 != bass % 12:
                continue

        valid.append(fs)

    if not valid:
        return []

    def score(fs):
        played = {(string_open[s] + fs[s]) % 12 for s in range(n_str) if fs[s] >= 0}
        pressed = [f for f in fs if f > 0]
        first = next((i for i in range(n_str) if fs[i] >= 0), n_str)
        last = next((i for i in range(n_str - 1, -1, -1) if fs[i] >= 0), -1)
        gaps = sum(1 for i in range(first, last + 1) if fs[i] == -1)
        if instr.get('reentrant') or bass is not None:
            inv = 0
        else:
            lo_abs = min(string_open[s] + fs[s] for s in range(n_str) if fs[s] >= 0)
            inv = 0 if lo_abs % 12 == root % 12 else 1
        n_play = sum(1 for f in fs if f >= 0)
        position = min(pressed) if pressed else 0
        return (
            -len(played & tones) / len(tones),
            gaps,
            inv,
            position,
            -n_play,
            sum(f for f in fs if f >= 0),
        )

    valid.sort(key=score)

    seen, result = set(), []
    for v in valid:
        k = tuple(v)
        if k not in seen:
            seen.add(k)
            result.append(v)
            if len(result) == n:
                break
    return result


def extract_chord_names(content: str) -> list:
    """Unikke akkordnavne i førstegangs-rækkefølge."""
    seen, result = set(), []
    for m in re.finditer(r'\[ch\](.*?)\[/ch\]', content):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def build_voicings_db(chord_names: list, instr: dict = None) -> dict:
    """{akkordnavn: [[frets], ...]} for alle akkorder i sangen."""
    db = {}
    for name in chord_names:
        parsed = parse_chord_name(name)
        if parsed is None:
            continue
        voicings = generate_voicings(*parsed, instr=instr)
        if voicings:
            db[name] = voicings
    return db


def build_all_voicings_dbs(chord_names: list) -> dict:
    """{instrument: {akkordnavn: [[frets], ...]}} for alle instrumenter."""
    return {name: build_voicings_db(chord_names, instr=cfg) for name, cfg in INSTRUMENTS.items()}


# Transponering
SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


def shift_note(note: str, semitones: int) -> str:
    scale = FLATS if 'b' in note else SHARPS
    try:
        idx = scale.index(note)
    except ValueError:
        return note
    return scale[(idx + semitones) % 12]


def transpose_chord(chord_str: str, semitones: int) -> str:
    m = re.match(r'^([A-G][#b]?)(.*?)(/([A-G][#b]?))?$', chord_str)
    if not m:
        return chord_str
    root, quality, bass = m.group(1), m.group(2), m.group(4)
    result = shift_note(root, semitones) + (quality or '')
    if bass:
        result += '/' + shift_note(bass, semitones)
    return result


def transpose_content(content: str, semitones: int) -> str:
    if semitones == 0:
        return content
    return re.sub(
        r'\[ch\](.*?)\[/ch\]',
        lambda m: f'[ch]{transpose_chord(m.group(1), semitones)}[/ch]',
        content,
    )


def parse_transpose(filename: str) -> int:
    m = re.search(r'_([+-]\d+)\.html$', filename)
    return int(m.group(1)) if m else 0