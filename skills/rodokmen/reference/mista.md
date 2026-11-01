# Místa a domy – stránky obcí na webu

Každé místo z `data/mista.json`, kde žil aspoň jeden předek, má na webu stránku `/misto/<slug>/` a je v přehledu `/mista/`.
Stránka se z velké části **poskládá sama** z dat, která už máš:
- **Kdo tu žil** – osoby, v jejichž faktech (`f` v `osoby.py`) je výraz `re` místa; rok = první letopočet ve faktu.
- **Domy** – číslo popisné za názvem obce ve faktu: „Komín č. 17“, „Holice čp. 112“, „v Holicích čp. 112“, „N° 17“.
  U každého domu časová osa: kdo, kdy a co (narození, sňatek, úmrtí, „čtvrtník v Komíně č. 17“).
- Na stránce osoby řádek „Žil: Žabovřesky → Komín (č. 17)“ s odkazy; na mapě vede název obce v bublině na stránku místa.

Ruční doplňky (vše volitelné) dělají ze stránky to, co rodinu baví číst:

## 1. Popis, fotka a domy – `data/mista.json`
```json
"Komín": {"re": "Komín", "lat": 49.2329, "lon": 16.5503,
  "popis": "Vinařská obec nad Svratkou, od 1919 součást Brna. Vaškové tu hospodařili na statku č. 17 od roku 1772.",
  "foto": "komin_pohlednice_1910", "foto_popis": "Komín na pohlednici kolem 1910",
  "domy": {"17": {"popis": "Čtvrtlánický statek; od 1772 Vaškové, předtím Pařízkové.", "dnes": "Kristenova 19/6 (?)"},
           "19": "Dům Vavřince Vaška st."}}
```
- `popis` – 1–2 věty do přehledu míst a pod nadpis. `foto` – klíč obrázku ve `vyrezy/` (ulož přes `vyrez.py`).
- `domy` – klíč = číslo popisné jako text; hodnota text, nebo `{"popis", "dnes"}` (dnešní adresa, jen když je ověřená,
  jinak s „(?)“). Dům bez popisu se ukáže i tak, když je ve faktech osob.
- Upravuj nástrojem pro úpravu souborů (ne přepisem celého souboru); `mista.py` další pole zachová.

**Fakta pište tak, aby z nich šel vyčíst dům a rok**: „čtvrtník v Komíně č. 17“, „1826 držitel domu Komín č. 17 (indikační skica)“.
Pobyt, který z matrik neplyne (stěhování, služba), přidej jako fakt s rokem a obcí: „1936 rolník v Komíně č. 19“.

## 2. Text místa – `data/mista/<slug>.md`
Slug = název obce bez diakritiky, malými písmeny, mezery jako `-` (Dolní Roveň → `dolni-roven.md`); `kontrola.py` hlásí
soubory, které k žádnému místu nepatří. První řádek `# Název` se na web nedává. Poznámky pro Clauda `<!-- … -->`.
Doporučené oddíly (jen ty, ke kterým máš co napsat):
- `## Z historie obce` – 1–4 odstavce pro rodinu: první zmínka, panství/vrchnost, čím se lidé živili, požáry, války,
  epidemie, kdy obec přišla o samostatnost. **Hlavně to, co se dotklo předků** („v roce 1855, kdy zemřel Josef na choleru…“).
- `## Z kroniky` – doslovné úryvky v `> citaci`, pod nimi kronika, rok a strana / odkaz.
- `## Domy a ulice` – jak se změnila čísla domů, co stojí na místě statku dnes.
- Na konci `Zdroje:` – odkud text je. **Nic nedomýšlej**: z hlavy jen obecně známé věci, jinak ze zdroje, který jsi četl.
Odkazy na osoby `[Jan Vašek](/osoba/<slug>/)`, na jiná místa `[Žabovřesky](/misto/zabovresky/)` – nefunkční hlásí `npm run data`.
Koncept textu ukaž uživateli v chatu dřív, než ho zapíšeš (jako u příběhu rodu).

## 3. Mapy a staré obrázky – `data/dokumenty.json`
```json
{"img": "komin_indikacni_skica_1826_c17", "popis": "Indikační skica stabilního katastru: „Waschek Mathias N° 17“",
 "misto": "Komín", "dum": "17", "rok": 1826, "zdroj": "MZA Brno, indikační skici, Komein 1826", "osoby": [32]}
```
- `misto` = název přesně jako v `mista.json`; `dum` = číslo popisné (obrázek se ukáže u domu, jinak v galerii místa);
  `rok` řadí galerii; `zdroj` se vypisuje pod obrázkem (u map a cizích fotek ho vždy uveď); `osoby` volitelně (ukáže se i u osoby).
- Obrázek ulož přes `python3 -I tools/vyrez.py dokumenty/<soubor> <klíč> [x0,y0,x1,y1]` – u velké mapy vyřízni jen ves
  nebo dům (jinak je na webu nečitelný); celou mapu dej zvlášť jako druhý obrázek.

## Kde brát podklady
| co | kde | poznámka |
|---|---|---|
| **indikační skici stabilního katastru** (1824–1843: čísla domů červeně, jména držitelů polí) | Morava: MZA `mza.cz/indikacniskici`; Čechy: Archiv ČÚZK `ags.cuzk.gov.cz/archiv` | nejcennější pro domy; německý název obce |
| císařské otisky, katastrální mapy, 2.–3. vojenské mapování | Archiv ČÚZK; `oldmaps.geolab.cz` | volně použitelné s uvedením zdroje |
| dnešní adresy a čísla popisná | RÚIAN (`vdp.cuzk.cz`, nahlížení do KN) | čísla domů byla v 19./20. stol. často přečíslována – ověř na dvou mapách |
| historie obce | web obce, Wikipedie (jen jako vodítko), monografie obce (knihovny, digilib), Historický lexikon obcí | cituj |
| kroniky obcí a škol | digitalizované kroniky SOkA: portály archivů (ebadatelna.soapraha.cz, Porta fontium, ARON, MZA/SOkA), `kramerius` | kroniky začínají většinou 1923 (zákon o pamětních knihách), školní dřív |
| staré pohlednice a fotky | rodina!, Kramerius (pohlednice), `fotohistorie.cz`, muzea, Europeana | uveď zdroj; u cizích fotek autorská práva – web je soukromý, ale i tak zdroj |
| noviny (požáry, povodně) | `reference/portaly.md` → Noviny | |

Postup, který se osvědčil: (1) projdi fakta – kde se opakuje stejné číslo domu přes generace, to je „rodový dům“;
(2) najdi indikační skicu a v ní dům a jméno držitele (doloží předka i bez matriky – zapiš do faktů a deníku);
(3) porovnej s dnešní mapou (RÚIAN) – přečíslování; (4) teprve pak historie a kronika. Hledání zapisuj do deníku.

## Soukromí
Dnešní adresa rodového domu, kde žijí příbuzní nebo cizí lidé, je citlivější než mapa z roku 1826 – před zveřejněním
se uživatele zeptej, jestli ji na webu chce (`dnes` může zůstat prázdné).
