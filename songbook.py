#!/usr/bin/env python3
"""Interaktiv menu til sangbogens redigeringsværktøjer.

Brug:
  python3 songbook.py
"""

import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
INDEX_FILE = ROOT / "index.html"
PDF_FILE = ROOT / "songbook.pdf"


def run_script(name: str, *args: str):
    subprocess.run([sys.executable, str(ROOT / name), *args], cwd=ROOT)


def open_songbook():
    webbrowser.open(f"file://{INDEX_FILE}")


def open_pdf_songbook():
    if not PDF_FILE.exists():
        print("songbook.pdf findes ikke endnu — generér den først.")
        return
    subprocess.run(["xdg-open", str(PDF_FILE)])


def add_song():
    print("Kør uden argument for at auto-scanne downloads/, eller angiv en fil/URL.")
    arg = input("Fil/URL (tom = auto-scan): ").strip()
    run_script("add_song.py", *([arg] if arg else []))


def edit_song():
    query = input("Søgeord (titel/artist/filnavn), eller 'ny' for at oprette en ny sang: ").strip()
    if not query:
        print("Intet søgeord angivet.")
        return
    if query.lower() in ("ny", "new"):
        run_script("edit_song.py", "--new")
    else:
        run_script("edit_song.py", query)


def generate_pdf():
    run_script("make_pdf.py")


MENU = [
    ("1", "Åbn sangbog", open_songbook),
    ("2", "Åbn PDF-sangbog", open_pdf_songbook),
    ("3", "Tilføj ny sang fra UG eller autoscan downloadede filer til sangbogen", add_song),
    ("4", "Rediger sang eller opret selv en ny sang", edit_song),
    ("5", "Generér PDF-sangbog", generate_pdf),
    ("6", "Afslut", None),
]


def main():
    while True:
        print("\n=== Sangbog ===")
        for key, label, _ in MENU:
            print(f"  {key}. {label}")
        choice = input("Vælg: ").strip()

        if choice.lower() in ("q", "afslut", "quit"):
            break

        match = next((m for m in MENU if m[0] == choice), None)
        if not match:
            print("Ugyldigt valg.")
            continue

        _, _, action = match
        if action is None:
            break

        try:
            action()
        except KeyboardInterrupt:
            print("\nAfbrudt.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFarvel.")
