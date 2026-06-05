# Sangbog

Et Python-script der henter akkorder og tekst fra Ultimate Guitar og gemmer dem som print-venlige HTML-filer.

## Brug

```bash
python3 add_song.py                   # auto-scan downloads/ for nye sange
python3 add_song.py <gemt-ug-side.html>
```

Transponering: tilføj `_+N` eller `_-N` til filnavnet før `.html`:
```
fx: the-cure_boys-dont-cry_+3.html  → transponer op 3 halvtoner
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
- `index.html` — oversigtsside grupperet efter artist med søgefelt
- `downloads/` — gemte UG-sider (kilde-input)

## Instrumenter og akkorddiagrammer

Scriptet genererer akkordgreb for fire instrumenter, som brugeren kan skifte mellem i sang-visningen:

| Instrument | Stemning | Strenge |
|---|---|---|
| Guitar | EADGBe | 6 strenge, MIDI 40-64 |
| Ukulele | gCEA (re-entrant) | 4 strenge |
| Mandolin | GDAE | 4 strenge |
| Banjo | 5-strenget open G (DGBD+g) | 5 strenge, re-entrant |

Akkordgreb beregnes automatisk ud fra akkordnavnet (rod + type). Hover over en akkord i browseren viser et SVG-diagram. Instrument-baren nederst til højre skifter mellem instrumenter.

## Layout-logik

Scriptet analyserer indholdet og vælger automatisk layout:

| Situation | Layout |
|---|---|
| ≤ 65 ikke-blanke linjer | 1 kolonne |
| ≤ 120 linjer, akkordlinjer ≤ 65 tegn | 2 kolonner |
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
- Skriftstørrelse kan skiftes (normal/lille) via knap i instrument-baren

## Datakilde

UG gemmer sangdata som JSON i `<div class="js-store" data-content="...">`.
Strukturen er: `store → page → data → tab_view → wiki_tab → content`

Indholdet bruger UG-markup:
- `[ch]Am[/ch]` — akkord
- `[tab]...[/tab]` — blok (fjernes, indhold bevares)
- `[Verse 1]` — sektionsheader (stort begyndelsesbogstav)
