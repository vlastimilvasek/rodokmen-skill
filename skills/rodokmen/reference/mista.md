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

## 4. Stará mapa přes dnešní – `data/stare_mapy.json` + `tools/georef.py`
Nejpůsobivější výstup: indikační skica (nebo katastrální mapa) průhledně přes dnešní mapu, s kroužky domů předků.
Na stránce obce se ukáže sekce „Překryv map“ místo horní fotky a malé mapy (posuvník průhlednosti, tlačítko ⛶ celé okno, podklad OpenStreetMap / letecký
snímek ČÚZK, a když je v kořeni projektu soubor `.mapy_api_klic`, i Mapy.com) a u domu odkaz „kde dům stál“.
```json
[{"id": "straznice_1827", "misto": "Strážnice", "nazev": "Indikační skica stabilního katastru", "rok": 1827,
  "obraz": "dokumenty/indikacni-skici/straznice_1827.jpg", "orez": [0, 1200, 5150, 4712],
  "skryt": [[0, 1200, 2580, 2640]], "zdroj": "MZA Brno, D9 Indikační skici, Strassnitz 1827 (MOR255818270)",
  "transformace": "podobnost",
  "body": [{"px": [3112, 2972], "gps": [48.900918, 17.313319], "popis": "kostel sv. Martina – křížení lodí"}],
  "domy": [{"px": [1703, 4052], "cislo": "161", "popis": "Jiří Lípa (1827)"}]}]
```
- `px` = pixel ve složeném obrázku `obraz`; `orez` = část, která jde na web; `skryt` = obdélníky, které na překryvu
  nemají být (seznamy majitelů, legendy, **vložené výřezy mimo skutečnou polohu** – např. zámek v rohu listu).
- `cislo` domu = číslo domu ve faktech osob (dům na stránce obce pak dostane GPS a odkaz „kde dům stál“).
- Kontrola: `python3 -I tools/georef.py` – odchylka každého bodu v metrech a GPS domů; `… georef.py <id> x,y` = GPS
  libovolného místa s odkazem na mapy.com. `npm run data` mapu narovná (sever nahoru, WebP s průhledným okolím).

**Postup (osvědčený):**
1. **Složit skicu** do jednoho obrázku. MZA `mza.cz/indikacniskici` (OpenSeadragon, objekt `dragon`):
   - *snímky obrazovky po přesných souřadnicích* – prohlížeč na celou obrazovku, `dragon.viewport.fitBounds(
     dragon.viewport.imageToViewportRectangle(x, y, w, w*výška/šířka))`, posouvat po celých šířkách a skládat v Pythonu
     (měřítko 0,5 stačí na město; jména u polí potřebují 1,0 = stovky snímků);
   - *dlaždice ve stránce* (rychlé, plné rozlišení) – **jen se souhlasem uživatele** (hromadné stahování z archivu):
     `src = dragon.world.getItemAt(0).source`, `src.getTileUrl(4, x, y)` (null = prázdná), dlaždice 217 × 174 px;
     složit na `<canvas>` po dílech ≤ 10 000 × 10 000 px a stáhnout (`canvas.toBlob` → odkaz `download`). Chrome napoprvé
     zablokuje „stahování více souborů“ – uživatel ho musí v adresním řádku povolit.
   - Listy jsou na MZA rozložené s mezerami (bílé čáry) – nevadí, je to jen pár metrů chyby.
2. **Záchytné body** (4–8, rozprostřené po celé mapě, i na okrajích): kostely (křížení lodí), kaple, brány, nároží
   bloků, mosty, sloupy. Vyznač je očíslované na staré mapě (obrázek pro uživatele) a nech uživatele odečíst GPS na
   mapy.com (pravé tlačítko → souřadnice; stupně° minuty' → desetinné = st + min/60). Polohu známého objektu jde
   zjistit i geokódováním Mapy.com (`https://api.mapy.com/v1/geocode?query=…&apikey=…`; volej z Pythonu – Git Bash
   rozbíjí diakritiku v URL).
3. `transformace: "podobnost"` (posun, otočení, měřítko) pro jeden list / poctivě složenou skicu; `"afinni"` až při
   6+ bodech a zkreslení. **Střední chyba do ~15 m = výborné**; bod s odchylkou nad 30 m je špatně určený (jiný roh,
   přestavěný objekt) – oprav ho nebo dej `"vynechat": true`. Ověř ještě jedním bodem, který ve výpočtu není.

**Úskalí:**
- **Čísla domů nejsou záchytné body.** Domy se přečíslovávaly (Strážnice) a **město a předměstí měly samostatné
  číslování** (Veselí n. M.: č. 60 Předměstí ≠ dnešní Kožešnická 60, ta je bývalé č. 60 města). Dnešní adresa
  z RÚIAN se stejným číslem je jen hypotéza – ověř ji polohou na převedené mapě.
- Některé stavby se na skicu nekreslily (brány přes ulici, kříže) – bod pak urči podle okolních bloků.
- Klíč k Mapy.com patří do `.mapy_api_klic` (je v `.gitignore`), **nikdy do `data/`** a do zpráv ho neopisuj. Na
  zveřejněném webu je ale ve stránce vidět – upozorni uživatele (kredity jeho účtu; omez klíč na doménu, pokud to
  portál dovolí). Bez klíče web použije OpenStreetMap a ortofoto ČÚZK. Při podkladu Mapy.com musí být vidět logo
  a copyright Mapy.com (komponenta `OldMap.astro` to dělá).
- Hotové georeferencované listy stabilního katastru: NPÚ/ÚAZK `geoportal.npu.cz/arcgisr/rest/services/Polohopisy/StabKat/MapServer`
  (vrstva 5 = pokryté listy) – pokrytí je jen částečné, ověř dotazem na bod obce.

## Kde brát podklady
| co | kde | poznámka |
|---|---|---|
| **indikační skici stabilního katastru** (1824–1843: čísla domů červeně, jména držitelů polí) | Morava: MZA `mza.cz/indikacniskici`; Čechy: Archiv ČÚZK `ags.cuzk.gov.cz/archiv` | nejcennější pro domy; německý název obce |
| císařské otisky, katastrální mapy, 2.–3. vojenské mapování | Archiv ČÚZK; `oldmaps.geolab.cz` | volně použitelné s uvedením zdroje |
| dnešní adresy a čísla popisná | RÚIAN (`vdp.cuzk.cz`, nahlížení do KN; adresní místa i strojově: `ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/1/query`) | čísla domů byla v 19./20. stol. často přečíslována a předměstí měla vlastní číslování – ověř na převedené mapě (oddíl 4) |
| historie obce | web obce, Wikipedie (jen jako vodítko), monografie obce (knihovny, digilib), Historický lexikon obcí | cituj |
| kroniky obcí a škol | digitalizované kroniky SOkA: portály archivů (ebadatelna.soapraha.cz, Porta fontium, ARON, MZA/SOkA), `kramerius` | kroniky začínají většinou 1923 (zákon o pamětních knihách), školní dřív |
| staré pohlednice a fotky | rodina!, Kramerius (pohlednice), `fotohistorie.cz`, muzea, Europeana | uveď zdroj; u cizích fotek autorská práva – web je soukromý, ale i tak zdroj |
| noviny (požáry, povodně) | `reference/portaly.md` → Noviny | |

Postup, který se osvědčil: (1) projdi fakta – kde se opakuje stejné číslo domu přes generace, to je „rodový dům“;
(2) najdi indikační skicu a v ní dům a jméno držitele (doloží předka i bez matriky – zapiš do faktů a deníku);
(3) převeď skicu na dnešní mapu (oddíl 4) – kde dům stál dnes; čísla RÚIAN jen jako hypotéza (přečíslování,
samostatné číslování předměstí); (4) teprve pak historie a kronika. Hledání zapisuj do deníku.

## Soukromí
Dnešní adresa rodového domu, kde žijí příbuzní nebo cizí lidé, je citlivější než mapa z roku 1826 – před zveřejněním
se uživatele zeptej, jestli ji na webu chce (`dnes` může zůstat prázdné).
