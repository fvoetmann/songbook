"""Hentning og parsing af Ultimate Guitar-sider (gemte filer og URL'er)."""

import json
import re
import sys

import requests
from bs4 import BeautifulSoup


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(
            f"Kunne ikke hente siden ({e}).\n"
            "Ultimate Guitar blokerer ofte automatiske downloads. Gem siden manuelt:\n"
            "  1. Åbn sangen på ultimate-guitar.com\n"
            "  2. Tryk Ctrl+U (vis kildekode)\n"
            "  3. Tryk Ctrl+A → Ctrl+S og gem filen lokalt\n"
            "  4. Kør scriptet med den gemte fil"
        )
    return r.text


def unwrap_view_source(html_text: str) -> str:
    """Hvis filen er gemt fra browserens view-source visning, udpak den rå HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    cells = soup.find_all("td", class_="line-content")
    if not cells:
        return html_text
    return "\n".join(cell.get_text() for cell in cells)


def extract_ug_data(html_text: str) -> dict:
    html_text = unwrap_view_source(html_text)
    soup = BeautifulSoup(html_text, "html.parser")

    # Nuværende format: JSON i data-content på .js-store
    el = soup.find(class_="js-store")
    if el and el.get("data-content"):
        return json.loads(el["data-content"])

    # Ældre format: window.UGAPP_DATA i script-tag
    for script in soup.find_all("script"):
        text = script.string or ""
        if "window.UGAPP_DATA" in text:
            m = re.search(r"window\.UGAPP_DATA\s*=\s*(\{.+\})\s*;", text, re.DOTALL)
            if m:
                return json.loads(m.group(1))

    raise ValueError(
        "Kunne ikke finde sangdata. Er det en Ultimate Guitar akkord-side?"
    )


def get_song_info(data: dict) -> tuple:
    # Nuværende format: data -> store -> page -> data
    page_data = (
        data.get("store", {}).get("page", {}).get("data")
        or data.get("data")
        or {}
    )

    tab = page_data.get("tab", {})
    tab_view = page_data.get("tab_view", {})

    title = tab.get("song_name", "Ukendt sang")
    artist = tab.get("artist_name", "Ukendt artist")
    key = tab.get("tonality_name", "") or ""
    capo = str(tab.get("capo", "") or "")

    content = (
        (tab_view.get("wiki_tab") or {}).get("content")
        or tab.get("content")
        or ""
    )
    return title, artist, key, capo, content