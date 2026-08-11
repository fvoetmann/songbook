# Kodevurdering – Sangbog

Dato: 2026-08-10
Omfang: `add_song.py`, `edit_song.py`, `make_pdf.py`, `rebuild_songs.py`, `songbook.py`, `songs.json`, `requirements.txt`, `index.html` (genereret).

**Status (opdateret 2026-08-11):** ✅ = lavet, 🟡 = delvist lavet, ⬜ = ikke lavet.
Se også [Efterfølgende opdagede fejl](#efterfølgende-opdagede-fejl-ikke-i-oprindelig-vurdering) nederst —
arbejdet med punkt 1 og 5 afslørede yderligere reelle bugs der ikke stod i den oprindelige vurdering.

---

## Samlet vurdering

Projektet er en velfungerende, personlig pipeline: UG-side → internt akkord-format → interaktiv sang-HTML → samlet PDF + indeks. Koden er generelt læsbar, velnavngivet og med gode docstrings for det sværeste (akkordteori, voice leading, round-trip mellem rendered HTML og UG-format). De største svagheder er ikke funktionalitet, men **vedligehold**: en 1338-linjers monolit, dobbelt-kodificeret akkordlogik i Python *og* indlejret JavaScript, nul tests, og en række robusheds-/edge-case-huller.

---

## Styrker

- **Ren akkordteori.** `parse_chord_name` (add_song.py:72) og `generate_voicings` (add_song.py:99) er velafgrænsede, kommenterede og håndterer re-entrant stemninger + `fixed_open` (banjo) korrekt.
- **Gennemtænkt round-trip design.** `edit_song.py` rekonstruerer rå UG-tekst fra rendered HTML (`line_div_to_ug`, `block_to_ug`, `merge_chord_line`), og `split_inline_chords`/`merge_chord_line` er nøjagtigt reversible — vigtigt, da `rebuild_songs.py` er afhængig af dette.
- **Konsekvent HTML-escapes** af navne/tekst (`html.escape`) — god XSS-hygiejne i det mest kritiske sted.
- **Lille, fokuseret CLI-entry** (`songbook.py`) der samler værktøjerne.
- **Pragmatiske heuristikker** med klare kommentarer (layout-beslutning, page-packing, voice-leading scoring).

---

## Prioriterede forslag

### 1. Tilføj tests (højeste prioritet) — ✅ Lavet

Der er ingen test i projektet. Det er det mest risikable hul, fordi der er meget spekulativ logik, hvor en stille regres- sion er svært at få øje på:

- `pytest` med fixtures fra de allerede gemte filer i `downloads/`:
  - ✅ `extract_ug_data` + `get_song_info` på 2–3 repræsentative gemte sider (credit: filerne findes allerede i repoet). — `tests/test_ug_parsing.py`
  - ✅ Round-trip: `render → html_to_content → render` giver samme akkorder og omtrent samme indhold for `edit_song.py`. — `tests/test_roundtrip.py`
  - ✅ `transpose_chord` / `transpose_content` for `+N`, `-N`, slash-akkorder (`D/F#`), b-noder (`Bb`). — `tests/test_transpose.py`
  - ✅ `parse_chord_name` over hele `CHORD_TYPES`. — `tests/test_chords.py`
  - ✅ `generate_voicings` sanity: root- og terts-tone til stede, span/mux-filtre overholdt, banjo 5. streng altid åben. — `tests/test_chords.py`
  - ✅ `decide_layout` og `paginate_sections` grænseværdier (54/130/65). — `tests/test_layout.py`
- ✅ Golden-file test for `make_song_html`: hvis template ændres utilsigtet, fejler testen i stedet for at alle 152 sange bliver gen-genereret uovervåget af `rebuild_songs.py`. — `tests/test_render_golden.py`

267 tests i alt (`pytest.ini`, `requirements-dev.txt`, kørsel dokumenteret i CLAUDE.md). Bonus ud over den oprindelige liste:
`tests/test_edit_format.py` (inline edit-format ↔ UG-format), `tests/test_tab_detection.py` (tab-genkendelse),
og en `tests/test_process_file_integration.py` mod monkeypatchede stier (rører aldrig det rigtige repo).

### 2. Bryd `add_song.py` op — ⬜ Ikke lavet

1338 linjer blander fem ansvarsområder:

| Linje-interval | Indhold |
|---|---|
| 27–218 | Akkordteori + voicing-generator |
| 220–683 | HTML/CSS/JS-skabeloner (store string-konstanter) |
| 687–723 | Transponering (Python) |
| 727–863 | UG-parsing, layout/pagination |
| 866–1149 | HTML-rendering af sange |
| 1152–1292 | songs.json, indeks, filbehandling |
| 1295–1338 | CLI `main()` |

Foreslået struktur (helst et almindeligt pakkemodul i stedet for `sys.path`-tricks):

```
songbook/
  core/
    chords.py          # NOTE_SEMI, CHORD_TYPES, parse, generate_voicings
    transpose.py       # shift_note, transpose_chord, transpose_content
    ugparse.py         # extract_ug_data, get_song_info, unwrap_view_source
    layout.py          # count_lines, decide_layout, paginate_sections
    render.py          # make_song_html (+ evt. skabelonfiler)
  app/
    store.py           # songs.json load/save, hashing
    index.py           # rebuild_index
    add_song_cli.py
    edit_song_cli.py
    make_pdf_cli.py
    rebuild_cli.py
```

De øvrige scripts bruger i dag `sys.path.insert(0, ...)` og importerer fra `add_song.py` (edit_song.py:23–28, make_pdf.py:14–15, rebuild_songs.py:15–17) — det skaber en skjult afhængighed, hvor f.eks. `make_pdf.py` trækker hele UG/requests-stakken ind bare for at få `artist_sort_key`.

### 3. Én kilde til sandheden for akkordteori (Python ↔ JavaScript) — ⬜ Ikke lavet

(Bemærk: da "2"-akkordsuffikset blev tilføjet under punkt 5-arbejdet, blev det manuelt holdt i sync begge
steder — hvilket er præcis den slags dobbelt-vedligehold denne opgave ville fjerne.)

Den samme teori er kodificeret **to steder**, og kommentaren siger det selv: *"Skal holdes i sync"* (add_song.py:258, 390).

- Python: `INSTRUMENTS`, `NOTE_SEMI`, `ACCIDENTAL`, `CHORD_TYPES`, `transpose_chord` (add_song.py:36–69, 688–709).
- JS: `INSTRUMENTS`, `NOTE_SEMI`, `ACCIDENTAL`, `CHORD_TYPES`, `parseChordName`, `generateVoicings`, `transposeChordName` (add_song.py:259–407).

Ved ændring af f.eks. en akkordtype eller en tuning kan browser-versionen og server-versionen drive fra hinanden uden nogen fejl opdages. Løsning: serialiser Python-datastrukturerne (INSTRUMENTS, CHORD_TYPES, SHARPS, FLATS) til JSON og injicér dem i JavaScript på generate-tidspunkt — præcis som `make_chord_diagram_html` allerede gør med `__DBS_JSON__` (add_song.py:683). Da skal kun Python-siden vedligeholdes.

### 4. Forskyd HTML/JS-skabelonerne ud af koden — ⬜ Ikke lavet

`CHORD_DIAGRAM_STYLE` + `CHORD_DIAGRAM_JS` er ~460 linjer string-konstanter indlejret i Python. `rebuild_songs.py` gør en runtime-re-generation mulig, så skabelonerne kan ligge som rigtige filer (`assets/chord-diagram.css`, `assets/chord-diagram.js`) og indlæses og injiceres ved generation. Det giver normal diffing, syntax-highlighting og linter-support, og korter Python-filen betydeligt. Den store `make_song_html`-f-string (add_song.py:1077–1149) kunne tilsvarende flyttes til en skabelonfil eller bygges stykkevist.

### 5. Ret konkrete fejl/edge-cases — ✅ Lavet (alle 6 punkter)

- ✅ **Forældreløs `_UGversion.html`** (add_song.py:1272–1280): når en manuelt redigeret sang detekteres, skrives den nye UG-version til filen, men `songs.json` og `index.html` opdateres **ikke** — den new fil er usynlig i indekset og kan ikke redigeres via `edit_song.py`. Enten tilføj et entry, eller tilføj en note/advarsel om hvordan man indarbejder den manuelt. — *Løst med tydelig advarsel + konkrete trin i konsol-outputtet.*
- ✅ **`href` uden attribute-escape** (add_song.py:1044): `f'<a href="{url}">'` — en URL (fx ved kald med direkte URL i `main()`, add_song.py:1318–1325) der indeholder `"` eller `<` bryder HTML / kan indsætte HTML. Brug `html.escape(url, quote=True)`. Bemærk: aldersteksten ellers er konsistent escaped. — *Løst, verificeret med XSS-forsøg.*
- ✅ **Intet exceptions-håndtering i auto-scan** (add_song.py:1306–1307): ét fejlbehæftet `downloads/`-fil kaster fuld traceback og afbryder hele batchen. Fange `ValueError`/`json.JSONDecodeError` per fil, log, og fortsæt. — *Løst.*
- ✅ **Uvalideret input i `find_song`** (edit_song.py:48): `int(input("Nummer: "))` kaster rå `ValueError` ved ikke-numerisk input, og et for stort tal giver `IndexError`. Fange og bede om nyt valg. — *Løst med retry-løkke.*
- ✅ **Tilfældig temp-fil i cwd** (add_song.py:1321): URL-hentning skriver `_tmp_ug.html` i projektmappen — kan kollidere med en rigtig fil i `downloads/`. Brug `tempfile.NamedTemporaryFile`. — *Løst.*
- ✅ **Inkonsistent encoding-behandling af `songs.json`**: `load_songs` læser uden `encoding=` (add_song.py:1168), mens `save_songs` skriver med utf-8; `make_pdf.py` læser med utf-8. På platforme med afvigende locale kan det give mismatch — angiv eksplicit i alle tre. — *Løst.*
- ✅ **`requests`-urbi** huntering: `fetch_page` har ingen fejlmeddelelse; en 403 (UG blokerer) viser bare timeout/HTTPError traceback. Fange og give den venlige besked som allerede står i CLAUDE.md (gem siden manuelt). — *Løst.*

### 6. Performance-sikring af voicings — ⬜ Ikke lavet

`generate_voicings` (add_song.py:99) laver `itertools.product` over alle fret-muligheder pr. streng (værste fald ~10^6 kombinationer for 6 strenge) og kaldes per akkord per instrument via `build_voicings_db` (add_song.py:202) — uden caching. For sange med mange akkorder og `rebuild_songs.py` over 152 sange akkumuleres det.

- Tilføj `functools.lru_cache` på `generate_voicings` (nøgle: root, tuple(ivs), bass, instrument) eller en eksplicit cache i `build_voicings_db`.
- Betragt prunings: kræv root i streng 1–2 tidligt, og drop `-1`-optioner aggressivt når `min_play` allerede er opfyldt.

### 7. Småting / ryd op — ⬜ Ikke lavet

- **Dubletter**: `SHARPS`/`FLATS` og `layout_msg`-ordbogen defineres flere steder (add_song.py:688–689 + JS; layout_msg i add_song.py:1267, edit_song.py:352, rebuild_songs.py:36). Saml i én konstant.
- **Magiske tal**: `LINES_PER_PAGE = 54`, `130`, `65`, `60` (add_song.py:854, 860, 1016). Flyt layout-tærsklerne til navngivne konstanter (eller i et config-modul) med kommentarer.
- **`requirements.txt` mangler nødvendige pakker**: `make_pdf.py` importerer `pypdf` (og kræver weasyprint), men requirements.txt har kun `requests` og `beautifulsoup4`. Tilføj i det mindste `pypdf`, og overvej versionspin.
- **`optimize_song_order` er O(n²)** (make_pdf.py:209–213): `song_pdfs[:song_pdfs.index(s)]` inde i et sum over listen giver kvadratisk adfærd, og `song_pdfs.index(s)` bruger liste-lighed — skrøbeligt over for dublet-entries. Beregn løbende sidetal i ét gennemløb i stedet.
- **`extract_first_style` (make_pdf.py:56)** antager at det *første* `<style>`-blok er sangens fælles CSS (diagram-CSS indsættes senere i `<head>` via `replace`). Det holder i dag, men er en skjult invariant — dokumentér eller gør det robust ved at markere skabelon-CSS med en kommentar/id.
- **`rebuild_songs.py` skriver alle sange hver gang** (rebuild_songs.py:32): selv identiske filer bliver genskrevet (ændrer mtime → trigger re-publish på GitHub Pages). Skriv kun, hvis den nye hash afviger fra den gamle.
- **Login-fri netadgang antaget**: `fetch_page` sender en static Chrome UA; UG blokerer med 403 — funktionen virker reelt sjældent og dokumenteres allerede som manuel download. Overvej at udfase `requests`-stien helt og kræve gemte filer.

### 8. Dokumentation — 🟡 Delvist lavet

- ⬜ CLAUDE.md og `songbook_overview.md` er solide. Tilføj evt. et afsnit om *hvordan* round-trip-formatet fungerer (HTML ↔ UG) og hvilke filer der må ændres af `rebuild_songs.py` — det er den skrøbeligste kontrakt i projektet. — *Ikke lavet endnu, men `{}`-konventionen (se nedenfor) er dokumenteret i CLAUDE.md's "Redigering af sange".*
- ✅ Når tests tilføjes, bør `pytest`-kørslen nævnes i CLAUDE.md samen med lint/typecheck. — *Tilføjet Tests-afsnit i CLAUDE.md.*

---

## Simpel prioritering

| # | Forslag | Indsats | Gevinst | Status |
|---|---|---|---|---|
| 1 | Tests (pytest med fixtures fra `downloads/`) | Medium | Kritisk — fanger regressions i round-trip, transponering og voicings | ✅ Lavet |
| 2 | Opdel `add_song.py` i moduler | Medium | Forudsætning for alt andet vedligehold | ⬜ Ikke lavet |
| 3 | Én kilde til akkordteori (Python ↔ JS) | Lille–medium | Fjerner den største driftrisiko | ⬜ Ikke lavet |
| 4 | Forskyd HTML/CSS/JS-skabeloner ud af koden | Lille | Bedre redigering og diffs | ⬜ Ikke lavet |
| 5 | Ret edge-case-fejl (liste ovenfor) | Lille | 3 reelle bugs rettet | ✅ Lavet |
| 6 | Cache voicings-generator | Lille | Hurtigere `rebuild_songs`/`add_song` | ⬜ Ikke lavet |
| 7 | Ryd op i duplikater, magic numbers, requirements | Lille | Lavere vedligehold | ⬜ Ikke lavet |
| 8 | `make_pdf.py`-optimering | Lille | Marginalt, kun ved mange sange | ⬜ Ikke lavet |

Samlet: solidt skrevet projekt med en god core-design, men det mangler det beskyttelsesnet (tests) og den struktur (modulopdeling + single source of truth) som de store round-trip- og duplikationsrisici ellers gør nødvendige. Af reelle fejl er den forældreløse `_UGversion.html` (add_song.py:1272–1280) og den uescapede `href` (add_song.py:1044) værd at rette først.

---

## Efterfølgende opdagede fejl (ikke i oprindelig vurdering)

Da testene i punkt 1 blev skrevet, og under undersøgelse af rapporterede visningsfejl, dukkede yderligere
reelle bugs op som ikke var identificeret i den oprindelige vurdering. Alle er rettet og testdækket:

- ✅ **Tabt akkord-markup ved round-trip** (`edit_song.py`, `line_div_to_ug`): en fysisk linje der blander
  akkorder med andet tekst på samme linje (fx `"[ch]A[/ch]  [ch]E[/ch]  x4"`, almindeligt ved
  intro/gentagelses-markeringer) mistede sine `[ch]`-tags når `html_to_content()` rekonstruerede UG-teksten.
  Ramte flere rigtige sange i biblioteket (bl.a. The Cure, Beatles). Rettet med en ny gren
  (`lyr_children_to_ug`) der genkender og rekonstruerer mønstret.
- ✅ **Manglende akkord-type "2"** (fx `D2`, forkortelse for sus2-typen): `parse_chord_name` genkendte ikke
  suffikset, så `edit_song.py`'s inline-redigering stille droppede sådanne akkorders farve/diagram ved gem.
  Tilføjet til `CHORD_TYPES` i både Python og indlejret JS.
- ✅ **Versalfølsom tab-genkendelse** (`is_tab_section`/`split_mixed`): krævede stort `EADGB` + lille `e`
  (standardnotation) for at genkende guitar-tab. Sange med alt-småt (`eadgbe`) eller bindestreg i stedet for
  `|` blev fejlagtigt vist som almindelig brødtekst i stedet for `<pre>`. Gjort versal-uafhængig.
- ✅ **`{Akkord}`-konvention indført** i `edit_song.py`'s redigeringsformat: akkorder der ikke er bundet til
  et bestemt ord (akkord-oversigter, `"Em Em(+F#)"`-stil progressionsnotation) blev tidligere fejlagtigt
  repositioneret eller mistede deres tag ved gentagne gem i editoren. Løses generelt (ikke kun per sang) ved
  at sådanne linjer nu automatisk vises med `{}` i stedet for `[]`, og gemmes altid præcis som de står.
  Verificeret stabil over 3 gem-cyklusser i test (`tests/test_edit_format.py`, `tests/test_roundtrip.py`).