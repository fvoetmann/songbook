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
    ("2", "Tilføj ny sang", add_song),
    ("3", "Rediger sang", edit_song),
    ("4", "Generér PDF-sangbog", generate_pdf),
    ("5", "Afslut", None),
]


def main():
    while True:
        print("\n=== Sangbog ===")
        for key, label, _ in MENU:
            print(f"  {key}. {label}")
        choice = input("Vælg: ").strip()

        if choice == "5" or choice.lower() in ("q", "afslut", "quit"):
            break

        match = next((m for m in MENU if m[0] == choice), None)
        if not match:
            print("Ugyldigt valg.")
            continue

        _, _, action = match
        try:
            action()
        except KeyboardInterrupt:
            print("\nAfbrudt.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFarvel.")
