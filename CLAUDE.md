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
- Header-linjer starter med `#` (Titel, Artist, Toneart, Capo, Tempo, Transponer) — kan redigeres
- `Tempo` er BPM for metronomen i browseren (standard 120 hvis tomt/udeladt)
- Akkorder skrives inline i teksten: `[Am]Her er teksten` → splittes automatisk til akkordlinje + tekstlinje
- `{Am}` (krøllede parenteser) markerer en akkord der IKKE er bundet til et bestemt ord — bruges
  automatisk til akkord-oversigter/-progressioner uden sangtekst under (fx `{Em}  {Em}(+F#)`).
  Sådanne akkorder gemmes altid præcis som de står, uden at blive flyttet eller splittet op —
  lad dem stå uændret medmindre du bevidst vil ændre selve akkorden
- Chord-only linjer (allerede justerede) genkendes og konverteres korrekt
- `Transponer: +N` eller `-N` i headeren transponerer alle akkorder (og Toneart) N halvtoner ved gem; `0` (standard) gør intet
- Tom fil ved gem annullerer ændringerne
- Ændres titel eller artist, omdøbes HTML-filen og indekset opdateres

## Takt-notation (afspilning)

Sange kan gradvist gøres "spilbare" (forberedelse til en senere afspilningsmotor, fx en
basgang) ved at tilføje en `[Bars]`-sektion, der beskriver hvor mange takter hver akkord
holder. Det er et **valgfrit** tillæg — sange uden `[Bars]` er fuldstændig upåvirkede.

```
[Bars]
Intro: |D A|G|Em7|Am7|
Vers: |Em7|Am7 Fmaj7|
```

- Én linje pr. sektionstype: `Label: <taktsekvens>`. `Label` matcher en `[Sektion]`-header
  i sangen, case-insensitivt — først eksakt, ellers som prefix (`Vers` matcher `[Vers 1]`,
  `[Vers 2]`)
- `<taktsekvens>`: `|`-adskilte takter (kant-`|` er valgfri/kosmetisk). Hver takt er:
  - én eller flere mellemrums-adskilte akkorder, der deler takten ligeligt (`D A` = 2
    akkorder i én takt, fx 2 slag hver i 4/4)
  - `%` = gentag forrige takt (samme akkord(er), holder videre)
  - `.` = paustakt (ingen akkord)
- Fast 4/4 for alle takter (matcher metronomens antagelse om accent hvert 4. slag)
- **Matchning:** de "rigtige" akkorder i taktsekvensen (uden `%`/`.`) skal, i rækkefølge,
  svare 1:1 til `[ch]`-akkorderne der allerede står i den tilhørende sektion i sangteksten.
  Stemmer det, tegnes taktstreger ind i den eksisterende visning (også i PDF, da PDF'en
  genbruger samme HTML). Stemmer det ikke, springes visuel taktstregs-visning over for den
  sektion, og der printes en advarsel ved gem/tilføjelse — resten af sangen er upåvirket
- **Visning:** taktstregen holder sig på akkordlinjen (over sangteksten) og går ikke ned i
  selve teksten. En `%`/`.`-markør (gentagelse/pause) vises umiddelbart efter den akkord i
  sangteksten den hører til, på samme linje som akkorden — ikke efter hele tekstlinjen
- Man skal allerede have skrevet akkorderne et sted i sangen (`[Am]`/`{Am}`) — `[Bars]`
  tilføjer kun taktinddeling oven på eksisterende akkorder, den genererer ikke nye
- `songs.json`-feltet `bars: true` sættes automatisk når mindst én sektion matcher

Kom hurtigt i gang med et udgangspunkt ("1 akkord = 1 takt", ingen gentagelser/pauser):

```bash
python3 add_default_bars.py <søgeord>
```

Scriptet indsætter en foreslået `[Bars]`-sektion og åbner sangen i `$EDITOR`, så
gentagelser (`%`), pauser (`.`) og akkorder der holder i flere takter kan rettes manuelt
før gem.

### `[Bars draft]` — inaktivt forslag for hele biblioteket

```bash
python3 add_draft_bars.py
```

Går igennem alle sange der endnu ikke har en `[Bars]`- eller `[Bars draft]`-sektion og
indsætter samme naive "1 akkord = 1 takt"-gæt som `add_default_bars.py`, men under headeren
`[Bars draft]` i stedet for `[Bars]` — ikke-interaktivt, uden at åbne `$EDITOR`, for hele
biblioteket i én kørsel.

`[Bars draft]` opfører sig som en kommentar: sektionen gemmes i sang-HTML'en (skjult, ligesom
`[Bars]`), men er bevidst **inaktiv** — den indgår ikke i taktstregs-matchning, sætter ikke
`bars: true`, og ændrer intet ved sangens visning. For at aktivere en sangs forslag:

```bash
python3 edit_song.py <søgeord>
```

ret evt. takterne til (gentagelser, pauser, akkorder der deler en takt) og omdøb sektionens
header fra `[Bars draft]` til `[Bars]` — gem, og den almindelige matchning/visning tager over.

`[Bars]`-strukturen beregnes og gemmes som JSON (`<script id="bar-data">` i sang-HTML'en) og
bruges nu til en simpel basgang: når `[Bars]` er aktiveret for sangen, spiller metronomen (▶)
automatisk grundtonen af den aktive akkord på 1. slag af hver (del-)takt, i den rækkefølge
sektionerne optræder i sangen (loop'er når metronomen kører videre efter sidste takt). Som
standard kun grundtonen; knappen "Bas: grundtone" i metronom-gruppen skifter til "Bas: grund+kvint",
hvor kvinten (grundtone + 7 halvtoner) også spilles på akkordens 3. slag, hvis akkorden holder så
længe (fx en hel takt i 4/4). Valget gælder kun den aktuelle visning og gemmes ikke.

Samtidig fremhæves den aktuelt spillende akkord i sangteksten (gul baggrund), og en lille
"Takt N/M"-tæller ved siden af metronom-knappen viser hvor i sangen basgangen er, så man kan
følge med selv når den spillende akkord er scrollet uden for skærmen. Begge dele følger
metronomens ▶/⏸ og nulstilles til sangens begyndelse hver gang den startes.

## Eksport til polyboard

```bash
python3 export_polyboard.py <søgeord>                 # print polyboard-kode
python3 export_polyboard.py <søgeord> --out sang.txt  # gem i fil
python3 export_polyboard.py <søgeord> --bass          # tilføj basgang på slot d2
```

Oversætter en sangs aktive `[Bars]`-takter til kode til polyboard (en live-coding-REPL med
Tidal/Strudel-lignende mini-notation, fx `test.polyrythm.com`): `def`-linjer plus én
`d1 # note (…)/N`-linje hvor 1 cyklus = 1 takt. Indsæt det hele i polyboard og kør alle linjer
(Skift+Ctrl+Enter). Kræver `[Bars]` (ikke `[Bars draft]`); ukendte akkorder bliver til pause med advarsel.

- `--sound NAVN` sætter polyboard-lyden til akkorderne (standard `arpy`)
- `--restrike` genanslår forlængede (`%`) akkorder hver takt (`!N`) i stedet for ét langt anslag (`@N`)
- `--bass` tilføjer grundtone på 1. slag i hver takt (som MIDI-tal, så tallene ikke forveksles med slot-navnet `d2`)
- `--bass-sound NAVN` sætter basgangens lyd (standard `arpy`; `sine` blev afvist af polyboard)
- Gentagne fire-takters mønstre udtrækkes automatisk som `def pat1 = (…)`; identiske sektioner deler én `def`

Polyboards parser afviser akkordliste-opslag (`d3'$maj`) inde i `def`-kroppe (`UnknownName`), så akkorder
skrives som inline-lister (`d3'[0 4 7]`). Mønstret er låst til transportens absolutte cyklus: mute/unmute
globalt før start for at begynde ved takt 1. Logikken ligger i `songlib/polyboard.py`.

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
- `add_song.py` — hovedscript (tilføj sang fra UG); tynd wrapper om `songlib`-pakken
- `edit_song.py` — rediger eller opret sang manuelt
- `make_pdf.py` — generer samlet PDF med indholdsfortegnelse
- `rebuild_songs.py` — regenerer alle sang-HTML-filer med aktuelt template
- `add_default_bars.py` — foreslår en `[Bars]`-taktinddeling for en sang (se "Takt-notation" ovenfor)
- `add_draft_bars.py` — indsætter en inaktiv `[Bars draft]`-taktinddeling for alle sange i biblioteket der endnu ikke har en (se "Takt-notation" ovenfor)
- `export_polyboard.py` — oversætter en sangs `[Bars]`-takter til polyboard-kode (se "Eksport til polyboard" ovenfor)
- `songlib/` — logik-pakke bag scripts (akkordteori, templates, UG-parsing, layout, rendering, store, CLI, `bars.py` for takt-notation, `polyboard.py` for polyboard-eksport)
- `.nojekyll` — forhindrer GitHub Pages i at køre Jekyll
- `songs/` — genererede HTML-sange
- `songs.json` — intern liste over sange (title, artist, file, source, hash, evt. bars)
- `index.html` — oversigtsside grupperet efter artist med live-søgefelt (filtrerer på titel og artist); sortering ignorerer et indledende "The " (fx "The Beatles" sorteres under B), men viser navnet uændret
- `downloads/` — gemte UG-sider (kilde-input)

`songs.json`-felter:
- `title`, `artist`, `file` — metadata og filnavn
- `source` — kildefilnavn fra `downloads/` (eller `"manuel"` for manuelt oprettede)
- `hash` — SHA-256 af kildefilens indhold; bruges til at springe uændrede filer over ved genscanning
- `bars` — `true` hvis sangen har mindst én gyldigt matchet `[Bars]`-sektion; udeladt ellers

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

**Metronom:** ▶/⏸ + prik + − [tempo i BPM] +
- Starter/stopper et hørbart klik ved den valgte BPM (Web Audio API, ingen lydfil); accent hvert 4. slag
- Prikken blinker rødt i takt med klikket (visuel indikator, nyttig ved lav/slukket lyd)
- Startværdien læses fra sangens `<meta name="tempo">`-tag (standard 120); justering i browseren med −/+ er kun for den aktuelle visning og gemmes ikke
- Det gemte standard-tempo redigeres via `Tempo`-feltet i `edit_song.py` (se ovenfor)

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

Fra en kodevurdering 2026-08-10 (`code-assessment.md`), efter at tests, en række konkrete bugfixes,
modulopdelingen af `add_song.py` → `songlib/` og requirements-fix allerede er lavet. Prioriteret
rækkefølge for næste skridt:

1. **Én kilde til akkordteori (Python → JS)** — `CHORD_TYPES`/`INSTRUMENTS`/`NOTE_SEMI`/`ACCIDENTAL`/
   `SHARPS`/`FLATS` er duplikeret i `songlib/chords.py` og i den indlejrede JS
   (`songlib/templates.py`) og holdes manuelt i sync (senest ved tilføjelse af "2"-akkordtypen).
   Injicér i stedet som JSON ved generation — samme mønster som `__DBS_JSON__` allerede bruger til
   akkordgreb.
2. ~~**`requirements.txt` mangler `pypdf`**~~ — ✅ Lavet (pypdf tilføjet).
3. ~~**`rebuild_songs.py` skriver alle sang-filer hver gang**~~ — ✅ Lavet: filen skrives kun når
   den nye hash afviger fra den gamle, så mtime/Pages-republish undgås for uændrede sange.
4. **Dokumentér round-trip-kontrakten** (HTML ↔ UG-format, `edit_song.py`'s `html_to_content`/
   `ug_to_edit`/`edit_to_ug`) — det er den mest skrøbelige del af kodebasen, og værd at skrive ned nu.

Lavere prioritet, ingen konkret smerte observeret endnu (se `code-assessment.md` for detaljer):
udflytning af HTML/CSS/JS-skabeloner fra `songlib/templates.py` til separate filer, caching af
`generate_voicings`, og øvrig oprydning (magic numbers, duplikeret `SHARPS`/`FLATS`/`layout_msg`,
`make_pdf.py`'s O(n²) `optimize_song_order`).
