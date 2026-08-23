"""CLI for add_song: auto-scan downloads/, behandl en fil eller hent en URL."""

import json
import sys
import tempfile
from pathlib import Path

from .store import DOWNLOADS_DIR, INDEX_FILE, process_file, processed_sources
from .ug import fetch_page


def main():
    DOWNLOADS_DIR.mkdir(exist_ok=True)

    if len(sys.argv) == 1:
        # Auto-scan downloads/ for nye filer
        done = processed_sources()
        new_files = [f for f in sorted(DOWNLOADS_DIR.glob("*.html")) if f.name not in done]
        if not new_files:
            print("Ingen nye sange i downloads/ — sangbogen er opdateret.")
            return
        print(f"Fandt {len(new_files)} ny(e) sang(e) i downloads/:")
        for f in new_files:
            print(f"\n→ {f.name}")
            try:
                process_file(f)
            except (ValueError, json.JSONDecodeError) as e:
                print(f"  FEJL: {e} — springer over.")
        print(f"\nIndeks opdateret: {INDEX_FILE}")

    elif len(sys.argv) == 2:
        arg = sys.argv[1]
        if Path(arg).exists():
            print(f"→ {arg}")
            process_file(Path(arg))
            print(f"Indeks opdateret: {INDEX_FILE}")
        else:
            url = arg
            print(f"Henter {url} ...")
            page_html = fetch_page(url)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as tmp_f:
                tmp_f.write(page_html)
                tmp = Path(tmp_f.name)
            try:
                process_file(tmp)
            finally:
                tmp.unlink()
            print(f"Indeks opdateret: {INDEX_FILE}")

    elif len(sys.argv) == 3:
        print(f"→ {sys.argv[1]}")
        process_file(Path(sys.argv[1]), url=sys.argv[2])
        print(f"Indeks opdateret: {INDEX_FILE}")

    else:
        print(__doc__)
        sys.exit(1)