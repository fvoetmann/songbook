# Sangbog

En Python-baseret sangbog der henter akkorder og tekst fra Ultimate Guitar og gemmer dem som interaktive, print-venlige HTML-filer med akkorddiagrammer, automatisk scroll og PDF-eksport.

## Brug

```bash
python3 songbook.py                   # interaktiv menu: åbn/tilføj/rediger sange, generér PDF
```

Eller direkte:

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

## Redigering af sange

```bash
python3 edit_song.py <søgeord>    # rediger eksisterende sang (søg på titel, artist eller filnavn)
python3 edit_song.py --new        # opret ny sang fra bunden
```

Åbner sangen i `$EDITOR` (standard: nano) med et tekstformat:
- Header-linjer starter med `#` (Titel, Artist, Toneart, Capo, Transponer) — kan redigeres
- Akkorder skrives inline i teksten: `[Am]Her er teksten` → splittes automatisk til akkordlinje + tekstlinje
- `{Am}` (krøllede parenteser) markerer en akkord der IKKE er bundet til et bestemt ord — bruges
  automatisk til akkord-oversigter/-progressioner uden sangtekst under (fx `{Em}  {Em}(+F#)`).
  Sådanne akkorder gemmes altid præcis som de står, uden at blive flyttet eller splittet op —
  lad dem stå uændret medmindre du bevidst vil ændre selve akkorden
- Chord-only linjer (allerede justerede) genkendes og konverteres korrekt
- `Transponer: +N` eller `-N` i headeren transponerer alle akkorder (og Toneart) N halvtoner ved gem; `0` (standard) gør intet
- Tom fil ved gem annullerer ændringerne
- Ændres titel eller artist, omdøbes HTML-filen og indekset opdateres

## PDF-generering

```bash
python3 make_pdf.py
```

Genererer `songbook.pdf` med alle sange sorteret alfabetisk efter artist/titel:
- Kræver `weasyprint` (CLI) og Python-pakken `pypdf`
- To-pas indholdsfortegnelse med korrekte sidenumre
- Sidenumre i bunden af hver side
- Outputfil: `songbook.pdf` i projektmappen

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Dækker akkordteori (`parse_chord_name`, `generate_voicings`), transponering, layout/pagineringsgrænser,
UG-parsing af rigtige gemte sider fra `downloads/`, round-trip mellem renderet HTML og UG-format
(`edit_song.py`'s reverse-parsing — den mest skrøbelige kontrakt i projektet), samt en golden-file-test
for `make_song_html`'s HTML/CSS/JS-skabelon. Ændres skabelonen bevidst, regenerér golden-filen med:

```bash
UPDATE_GOLDEN=1 .venv/bin/pytest tests/test_render_golden.py
```

## GitHub Pages / mobil

Sangbogen kan hostes som en statisk hjemmeside via GitHub Pages:

1. Gå til repo-indstillinger → Pages → Source: `main` branch, root
2. Siden er tilgængelig på `https://fvoetmann.github.io/songbook/`

Alle sider er mobilvenlige:
- Responsivt layout: A4-siden flyder ud til fuld bredde på skærme ≤ 640px
- 2-kolonne layout deaktiveres automatisk på mobilskærme, også i landskabstilstand (bredde- og højde-baseret media query)
- Akkorddiagrammer vises ved tryk (tap) på akkorder; skjules ved tryk et andet sted eller ved scroll
- Instrument-baren kan ombryde på smalle skærme

Efter ændringer i CSS/JS-template, kør for at opdatere alle eksisterende sange:
```bash
python3 rebuild_songs.py
```

## Filer

- `songbook.py` — interaktiv menu der samler add_song/edit_song/make_pdf og åbning af sangbogen
- `add_song.py` — hovedscript (tilføj sang fra UG)
- `edit_song.py` — rediger eller opret sang manuelt
- `make_pdf.py` — generer samlet PDF med indholdsfortegnelse
- `rebuild_songs.py` — regenerer alle sang-HTML-filer med aktuelt template
- `.nojekyll` — forhindrer GitHub Pages i at køre Jekyll
- `songs/` — genererede HTML-sange
- `songs.json` — intern liste over sange (title, artist, file, source, hash)
- `index.html` — oversigtsside grupperet efter artist med live-søgefelt (filtrerer på titel og artist); sortering ignorerer et indledende "The " (fx "The Beatles" sorteres under B), men viser navnet uændret
- `downloads/` — gemte UG-sider (kilde-input)

`songs.json`-felter:
- `title`, `artist`, `file` — metadata og filnavn
- `source` — kildefilnavn fra `downloads/` (eller `"manuel"` for manuelt oprettede)
- `hash` — SHA-256 af kildefilens indhold; bruges til at springe uændrede filer over ved genscanning

## Browser-funktioner (sang-visning)

Hver sang-HTML har en fast bar nederst til højre med følgende kontroller:

**Instrument-skift:** Guitar · Ukulele · Mandolin · Banjo
- Skifter akkorddiagrammer øjeblikkeligt; hover over en akkord viser SVG-diagram for det valgte instrument

**Skriftstørrelse:** A (normal) · a (lille)
- Skifter tekststørrelse i akkord/tekst-blokke (9pt / 8pt)

**Automatisk scroll:** ▶/⏸ + − [hastighed 1–9] +
- Starter/stopper automatisk nedadgående scroll
- Hastighed 1–9, justerbar med −/+ knapper; stopper automatisk når bunden er nået
- Standard hastighed: 5

**Akkorddiagrammer:**
- Greb vælges automatisk ud fra mindste fingerafstand til foregående akkord i samme blok (voice leading)
- Slash-akkorder (fx `D/F#`) slår op på rodakkorden
- Diagrammet vises som SVG i en tooltip over akkorden

**Instrumenter og stemninger:**

| Instrument | Stemning | Strenge |
|---|---|---|
| Guitar | EADGBe | 6 strenge |
| Ukulele | gCEA (re-entrant) | 4 strenge |
| Mandolin | GDAE | 4 strenge |
| Banjo | 5-strenget open G (DGBD+g) | 5 strenge, re-entrant |

Akkordgrebene er indlejret som en JSON-database direkte i HTML-filen (ingen ekstern afhængighed).

## Layout-logik

Scriptet analyserer indholdet og vælger automatisk layout:

| Situation | Layout |
|---|---|
| ≤ 54 ikke-blanke linjer | 1 kolonne |
| ≤ 130 linjer, akkordlinjer ≤ 65 tegn | 2 kolonner |
| Ellers | Flere sider |

Guitar tab-notation (linjer med `e|`, `B|` osv.) behandles separat:
- Akkord+tekst-sektioner vises i hoved-layoutet (evt. 2 kolonner)
- Tab-sektioner placeres altid til sidst, på ny side ved print, i enkeltkolonne

Ved "Flere sider" splittes indholdet i separate `.page`-ark (hele sektioner pakkes
sammen, op til ~54 linjer pr. ark; en enkelt sektion splittes aldrig midt over).
På almindelige skærme stables arkene som i dag; på brede/zoomede-ud skærme
(≥ 460mm effektiv bredde) vises de i stedet side om side i et grid, hver med
skygge, som et opslag. Print/PDF følger de samme arkgrænser (`break-before: page`
mellem hvert `.page`).

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

## Kendte forbedringspunkter

Fra en kodevurdering 2026-08-10 (`code-assessment.md`), efter at tests og en række konkrete
bugfixes allerede er lavet. Prioriteret rækkefølge for næste skridt:

1. **Én kilde til akkordteori (Python → JS)** — `CHORD_TYPES`/`INSTRUMENTS`/`NOTE_SEMI`/`ACCIDENTAL`/
   `SHARPS`/`FLATS` er duplikeret i Python og i den indlejrede JS og holdes manuelt i sync (senest ved
   tilføjelse af "2"-akkordtypen). Injicér i stedet som JSON ved generation — samme mønster som
   `__DBS_JSON__` allerede bruger til akkordgreb.
2. **`requirements.txt` mangler `pypdf`** — `make_pdf.py` kræver den, men `pip install -r requirements.txt`
   giver den ikke, så PDF-generering fejler efter en frisk installation.
3. **`rebuild_songs.py` skriver alle sang-filer hver gang**, også uændrede — ændrer mtime og udløser
   unødvendig GitHub Pages-republish. Skriv kun filen hvis den nye hash afviger fra den gamle.
4. **Dokumentér round-trip-kontrakten** (HTML ↔ UG-format, `edit_song.py`'s `html_to_content`/
   `ug_to_edit`/`edit_to_ug`) — det er den mest skrøbelige del af kodebasen, og værd at skrive ned nu.

Lavere prioritet, ingen konkret smerte observeret endnu (se `code-assessment.md` for detaljer):
modulopdeling af `add_song.py`, udflytning af HTML/CSS/JS-skabeloner til separate filer, caching af
`generate_voicings`, og øvrig oprydning (magic numbers, duplikeret `SHARPS`/`FLATS`/`layout_msg`,
`make_pdf.py`'s O(n²) `optimize_song_order`).
