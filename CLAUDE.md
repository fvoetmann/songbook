# Sangbog

Et Python-script der henter akkorder og tekst fra Ultimate Guitar og gemmer dem som print-venlige HTML-filer.

## Brug

```bash
python3 add_song.py <gemt-ug-side.html>
```

Ultimate Guitar blokerer automatiske downloads med 403. Gem siden manuelt:
1. Åbn sangen på ultimate-guitar.com
2. Tryk Ctrl+U (vis kildekode)
3. Tryk Ctrl+A → Ctrl+S og gem filen lokalt
4. Kør scriptet med den gemte fil

## Filer

- `add_song.py` — hovedscript
- `songs/` — genererede HTML-sange
- `songs.json` — intern liste over sange
- `index.html` — oversigtsside med links til alle sange
- `add_song_backup.py` — backup af en stabil version

## Layout-logik

Scriptet analyserer indholdet og vælger automatisk layout:

| Situation | Layout |
|---|---|
| ≤ 58 ikke-blanke linjer | 1 kolonne |
| ≤ 115 linjer, akkordlinjer ≤ 52 tegn | 2 kolonner |
| Ellers | Flere sider |

Guitar tab-notation (linjer med `e|`, `B|` osv.) behandles separat:
- Akkord+tekst-sektioner vises i hoved-layoutet (evt. 2 kolonner)
- Tab-sektioner placeres altid til sidst, på ny side ved print, i enkeltkolonne

## Formatering

- Blanke linjer fjernes i akkord-sektioner
- Blanke linjer bevares i tab-sektioner (for læsbarhed)
- Sektioner (`[Verse 1]`, `[Chorus]` osv.) brydes aldrig midt over ved sideskift (`break-inside: avoid`)
- Akkorder vises med rødt (`#b00020`)
- Print: A4, 12mm top/bund, 14mm sider

## Datakilde

UG gemmer sangdata som JSON i `<div class="js-store" data-content="...">`.
Strukturen er: `store → page → data → tab_view → wiki_tab → content`

Indholdet bruger UG-markup:
- `[ch]Am[/ch]` — akkord
- `[tab]...[/tab]` — blok (fjernes, indhold bevares)
- `[Verse 1]` — sektionsheader (stort begyndelsesbogstav)
