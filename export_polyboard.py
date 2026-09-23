#!/usr/bin/env python3
"""
Eksportér en sang med [Bars]-takter til polyboard (live-coding-REPL med
Tidal/Strudel-lignende mini-notation).

Brug:
  python3 export_polyboard.py <søgeord>                 # print til skærmen
  python3 export_polyboard.py <søgeord> --out sang.txt  # gem i fil
  python3 export_polyboard.py <søgeord> --bass          # tilføj basgang (slot d2)

Tilvalg:
  --sound NAVN   polyboard-lyd til akkorderne (standard: arpy)
  --bass-sound NAVN  lyd til basgangen med --bass (standard: arpy)
  --restrike     genanslå forlængede akkorder hver takt i stedet for ét langt anslag

Kræver at sangen har en aktiv [Bars]-sektion (se CLAUDE.md, "Takt-notation").
"""

import argparse
import sys

from songlib import SONGS_DIR, render_polyboard
from songlib.polyboard import bar_data_from_html, tempo_from_html

from edit_song import find_song


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="+", help="søgeord (titel, artist eller filnavn)")
    ap.add_argument("--out", help="gem outputtet i denne fil i stedet for at printe")
    ap.add_argument("--sound", default="arpy", help="polyboard-lyd til akkorderne (standard: arpy)")
    ap.add_argument("--bass", action="store_true", help="tilføj basgang (grundtone) på slot d2")
    ap.add_argument("--bass-sound", default="arpy", help="polyboard-lyd til basgangen (standard: arpy)")
    ap.add_argument("--restrike", action="store_true", help="genanslå forlængede akkorder hver takt")
    args = ap.parse_args()

    song, html_path = find_song(" ".join(args.query))
    if not html_path.exists():
        sys.exit(f"Filen findes ikke: {html_path}")

    html_text = html_path.read_text(encoding="utf-8")
    bar_data = bar_data_from_html(html_text)
    if not bar_data:
        sys.exit(
            f"'{song['artist']} – {song['title']}' har ingen aktiv [Bars]-sektion. "
            f"Tilføj takter med: python3 add_default_bars.py {' '.join(args.query)!r}"
        )

    text, warnings = render_polyboard(
        bar_data, tempo_from_html(html_text), title=song["title"], artist=song["artist"],
        sound=args.sound, bass=args.bass, bass_sound=args.bass_sound, restrike=args.restrike,
    )
    for w in warnings:
        print(f"ADVARSEL: {w}", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Gemt: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
