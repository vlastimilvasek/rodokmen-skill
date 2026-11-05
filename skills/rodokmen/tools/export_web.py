#!/usr/bin/env python3
"""Export dat rodokmenu (data/*) do webu ve složce web/.

Čte data/osoby.py, data/zaznamy.json, data/svazky.json, data/prepisy.json, data/zvyrazneni.json,
data/mista.json (+ texty míst data/mista/<slug>.md), data/web.json, data/dokumenty.json a markdownové poznámky. Zapisuje
web/src/data/site.json, web/src/generated/*, web/public/{img,zdroje}, web/public/prihlaseni.html,
web/nginx.conf a web/netlify/edge-functions/brana.js.

Spouští se z web/ příkazem `npm run data` (nebo přímo `python3 -I tools/export_web.py`, na Windows `python -I -X utf8 …`).
"""
import hashlib, html, json, os, re, shutil, subprocess, sys, unicodedata
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
VYREZY = os.path.join(ROOT, "vyrezy")      # výřezy zápisů a dokumentů (asi 1800 px) – zobrazují se na webu
ZDROJE = os.path.join(ROOT, "zdroje")      # tytéž výřezy v plném rozlišení (proklik)

LINE_COLORS = {8: "#EFB45F", 9: "#F09A78", 10: "#E58AA6", 11: "#B99AE0",
               12: "#86B8E8", 13: "#6FCBB9", 14: "#9CD17A", 15: "#D3D46A"}
STATUS = {"doc": "doloženo matrikou", "prob": "pravděpodobné", "fam": "údaj od rodiny",
          "mh": "jen z cizího rodokmenu", "unk": "neznámé"}
KINDS = {"N": "křest / narození", "O": "sňatek", "Z": "úmrtí", "I": "rejstřík", "S": "sčítání lidu", "J": "jiný pramen"}


def jload(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_people():
    ns = {}
    exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    for name, default in (("P", {}), ("SIDE", []), ("LINES", {}), ("ISSUES", []), ("HYPOTEZY", []), ("SAME", {})):
        ns.setdefault(name, default)
    return ns


def record_rows():
    svazky = jload("svazky.json", {})
    rows = []
    for z in jload("zaznamy.json", []):
        sv = svazky.get(z.get("svazek", ""), {})
        key = z["klic"]
        rows.append(dict(
            key=key, kind=z.get("druh", "J"), date=z.get("datum", ""), title=z.get("nazev", key),
            summary=z.get("shrnuti", ""), scan=z.get("snimek", ""),
            archive=sv.get("archiv", ""), volume=sv.get("svazek", ""), vdesc=sv.get("popis", ""),
            portal=sv.get("portal", "archivu"), url=z.get("odkaz") or sv.get("url", ""),
            img=os.path.exists(os.path.join(VYREZY, key + ".jpg")),
            full=os.path.exists(os.path.join(ZDROJE, key + ".jpg")),
        ))
    return rows


def strip_comments(md):
    """Poznámky <!-- … --> v markdownu jsou pro Clauda, ne pro web."""
    return re.sub(r"<!--.*?-->\n?", "", md, flags=re.S)


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


DATE_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(1[4-9]\d\d)")


def birth_key(texts, rec_keys, recs, fallback=""):
    """Řadicí klíč narození (rrrrmmdd): křestní zápis → datum za */~/narozen v textu → první rok."""
    for r in rec_keys:
        if r in recs and recs[r]["kind"] == "N":
            m = DATE_RE.search(recs[r]["date"])
            if m:
                return int(m[3]) * 10000 + int(m[2]) * 100 + int(m[1])
    for t in texts:
        for m in DATE_RE.finditer(t):
            if re.search(r"(\*|~|[Nn]arozen|[Pp]okřtěn)[^.;]{0,25}$", t[max(0, m.start() - 30):m.start()]):
                return int(m[3]) * 10000 + int(m[2]) * 100 + int(m[1])
    for t in [texts[0], fallback]:   # jen rok – ze jména (texts[0]) nebo pole „y“; text se nepoužije (roky sňatků, úmrtí dětí…)
        m = re.search(r"(\*|×|†)?\s*\b(1[4-9]\d\d)\b", t or "")
        if m and m[1] != "†":   # u sňatku odhad narození o 25 let dřív, samotné úmrtí neřadí
            return (int(m[2]) - (25 if m[1] == "×" else 0)) * 10000
    for t in texts[1:]:
        m = re.search(r"\*\s*(1[4-9]\d\d)\b", t)
        if m:
            return int(m[1]) * 10000
    return 99999999


def norm_answer(text):
    """Stejná normalizace jako v prihlaseni.html: bez diakritiky, malá písmena, jen a-z0-9."""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", t)


def years(y):
    y = (y or "").strip()
    ys = re.findall(r"\d{4}", y)
    if not ys:
        return ""
    approx = "≈" if re.match(r"^(asi|≈)", y) else ""
    head, dash, tail = y.partition("–")
    if y.startswith(("?", "†")) or (dash and not re.search(r"\d", head)) or re.match(r"po\b", y):
        # neznámé narození: ukázat jen úmrtí („? – před 1743“ → „† před 1743“, „– po 1921“ → „žil 1921“)
        if re.search(r"\bpo\b", tail or y):
            return "žil " + ys[-1]
        return "† " + ("před " if "před" in y else "") + ys[-1]
    if y.startswith("*"):
        return "* " + ys[0]
    if len(ys) == 1:
        return approx + ys[0]
    second = "?" if "před" in tail else ("po " if re.search(r"\bpo\b", tail) else "") + \
        ("≈" if re.search(r"(asi|≈)", tail) else "") + ys[-1]
    return f"{approx}{ys[0]}–{second}"


def gen(k):
    return k.bit_length() - 1


def relation(k):
    g, male = gen(k), (k % 2 == 0)
    if g == 0:
        return "výchozí osoba rodokmenu"
    if g == 1:
        return "otec" if male else "matka"
    base = "dědeček" if male else "babička"
    if g <= 5:
        return "pra" * (g - 2) + base
    return f"{'předek' if male else 'předkyně'} v {g}. generaci ({'pra' * (g - 2)}{base})"


def placeholder(p):
    return p["n"].startswith(("otec neuveden", "matka neuvedena")) or p["n"] in ("", "?")


def magick_bin():   # ImageMagick 7 (magick), jinak 6 (convert) – ten ale ne na Windows, tam je convert.exe jiný program
    return shutil.which("magick") or (os.name != "nt" and shutil.which("convert")) or None


def size(path):
    w, h = subprocess.run([magick_bin(), path + "[0]", "-format", "%w %h", "info:"],
                          capture_output=True, text=True, check=True).stdout.split()
    return int(w), int(h)


def draw_boxes(src, dst, boxes, small):
    """Kopie výřezu v plném rozlišení s nakreslenými rámečky (pokud má stejný poměr stran jako webový výřez,
    na kterém se rámečky měřily). Vrací False, pak se kopíruje bez rámečků."""
    if not os.path.exists(small) or not magick_bin():
        return False
    (W, H), (w, h) = size(src), size(small)
    if abs(W / H - w / h) > 0.015 * (w / h):
        return False
    sw = max(4, round(W / 450))
    cmd = [magick_bin(), src, "-fill", "none", "-stroke", "#d7302a", "-strokewidth", str(sw)]
    for x0, y0, x1, y1 in boxes:
        cmd += ["-draw", f"rectangle {x0 * W:.0f},{y0 * H:.0f},{x1 * W:.0f},{y1 * H:.0f}"]
    subprocess.run(cmd + ["-quality", "90", dst], check=True)
    return True


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def login_files(cfg):
    """Přihlašovací brána: otázka na webu, na serveru (nginx i Netlify) jen otisk odpovědi (SHA-256).
    Stejný otisk spočítá přihlašovací stránka a uloží ho do cookie – samotná odpověď se nikam neukládá."""
    login = cfg.get("prihlaseni") or {}
    answer = norm_answer(login.get("odpoved", ""))
    tpl = open(os.path.join(WEB, "prihlaseni.sablona.html"), encoding="utf-8").read()
    if "rodokmen:" not in tpl:   # stará šablona (do 0.4.0) ukládá do cookie odpověď – s novou bránou by se nikdo nepřihlásil
        sys.exit("CHYBA: web/ má starou šablonu přihlášení. Aktualizujte projekt: python3 -I <skill>/tools/novy_projekt.py <složka projektu>")
    contact = cfg.get("kontakt") or {}
    hint = ""
    if contact.get("email"):
        hint = (f'Neznáte odpověď? Napište {html.escape(contact.get("jmeno", ""))} na '
                f'<a href="mailto:{html.escape(contact["email"])}">{html.escape(contact["email"])}</a>.')
    page = (tpl.replace("{{NAZEV}}", html.escape(cfg.get("nazev", "Rodokmen")))
               .replace("{{UVOD}}", html.escape(login.get("uvod", "Tenhle web je jen pro rodinu a příbuzné.")))
               .replace("{{OTAZKA}}", html.escape(login.get("otazka", "Odpověď na rodinnou otázku")))
               .replace("{{NAPOVEDA}}", hint))
    write(os.path.join(WEB, "public", "prihlaseni.html"), page)

    edge = os.path.join(WEB, "netlify", "edge-functions", "brana.js")
    if answer:
        digest = hashlib.sha256(("rodokmen:" + answer).encode()).hexdigest()
        nginx_map = f'  "{digest}" 1;'
        write(edge, open(os.path.join(WEB, "netlify", "brana.sablona.js"), encoding="utf-8").read().replace("{{HASH}}", digest))
    else:   # bez přihlášení – web je otevřený
        nginx_map = "  default 1;"
        if os.path.exists(edge):
            os.remove(edge)
    nginx = open(os.path.join(WEB, "nginx.sablona.conf"), encoding="utf-8").read().replace("{{ODPOVED}}", nginx_map)
    write(os.path.join(WEB, "nginx.conf"), nginx)
    return bool(answer)


HOUSE = re.compile(r"(?:\bč\.\s*p\.|\bčp\.|\bč\.|N°|\bNo\.)\s*(\d+)")
EVENT = {"*": "narození", "~": "křest", "×": "sňatek", "†": "úmrtí"}
MISTA_MD = os.path.join(DATA, "mista")     # data/mista/<slug>.md – historie obce, úryvky z kronik (volitelné)


def fact_year(text):
    m = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", text)
    return int(m.group(1)) if m else None


def build_places(people, docs_cfg):
    """Místa z data/mista.json: kdo tam žil (podle faktů osob), domy (čísla popisná ve faktech) a obrázky.

    Fakt patří k místu, když v něm je výraz `re` místa; číslo domu se bere za názvem obce („Komín č. 17“, „čp. 112“).
    Rok je první letopočet ve faktu; fakt bez roku se ukáže bez data (řadí se podle let života osoby).
    """
    places = []
    for name, e in jload("mista.json", {}).items():
        if "lat" not in e:
            continue
        rx = re.compile(e.get("re") or re.escape(name))
        slug = slugify(name)
        residents, houses = [], {}
        for p in sorted(people.values(), key=lambda p: p["k"]):
            facts = []
            for f in p["facts"]:
                m = rx.search(f)
                if not m:
                    continue
                h = HOUSE.search(f, m.end()) or None
                ev = re.match(r"^(?:\d\.\s*)?([*~×†])", f)
                facts.append(dict(text=f, year=fact_year(f), house=h.group(1) if h else None,
                                  kind=EVENT.get(ev.group(1), "") if ev else ""))
            if not facts:
                continue
            yrs = [x["year"] for x in facts if x["year"]]
            life = [int(y) for y in re.findall(r"\b(?:1[4-9]\d\d|20\d\d)\b", p["y"] or "")]
            hs = list(dict.fromkeys(x["house"] for x in facts if x["house"]))
            residents.append(dict(slug=p["slug"], line=p["line"] or 0, facts=facts, houses=hs,
                                  span=[min(yrs), max(yrs)] if yrs else None,
                                  sort=min(yrs) if yrs else (life[0] if life else 9999)))
            for x in facts:
                if x["house"]:
                    houses.setdefault(x["house"], []).append(dict(slug=p["slug"], year=x["year"], text=x["text"], kind=x["kind"],
                                                                  sort=x["year"] or (min(yrs) if yrs else life[0] if life else 9999)))
        residents.sort(key=lambda r: (r["sort"], people[r["slug"]]["k"]))
        byline = {}
        for r in residents:
            byline.setdefault(r["line"], []).append(r["slug"])
        if e.get("hypoteza"):
            byline = {e.get("rod", 0): []}
        if not byline:
            continue
        yrs = [int(y) for r in residents for y in re.findall(r"\b1[4-9]\d\d\b", people[r["slug"]]["y"] or "")]
        desc_h = e.get("domy") or {}
        for num in desc_h:
            houses.setdefault(str(num), [])
        house_list = []
        for num in sorted(houses, key=lambda n: int(n) if n.isdigit() else 10 ** 6):
            d = desc_h.get(num) or {}
            d = {"popis": d} if isinstance(d, str) else d
            ev = sorted(houses[num], key=lambda x: (x["sort"], people[x["slug"]]["k"]))
            house_list.append(dict(num=num, desc=d.get("popis", ""), today=d.get("dnes", ""), events=ev,
                                   docs=[x["img"] for x in docs_cfg if x.get("misto") == name and str(x.get("dum", "")) == num]))
        for r in residents:
            people[r["slug"]].setdefault("places", []).append(dict(slug=slug, name=name, houses=r["houses"], sort=r["sort"]))
        md = os.path.join(MISTA_MD, slug + ".md")
        places.append(dict(name=name, slug=slug, lat=e["lat"], lon=e["lon"], lines=[dict(k=k, people=v) for k, v in sorted(byline.items())],
                           years=[min(yrs), max(yrs)] if yrs else None, hypothesis=bool(e.get("hypoteza")),
                           desc=e.get("popis", ""), photo=e.get("foto", ""), photoCaption=e.get("foto_popis", ""),
                           residents=residents, houses=house_list, hasText=os.path.exists(md),
                           docs=[x["img"] for x in docs_cfg if x.get("misto") == name]))
    for p in people.values():
        p["places"] = sorted(p.get("places", []), key=lambda x: x["sort"])
    return places


def build_old_maps(places):
    """Staré mapy z data/stare_mapy.json (tools/georef.py): narovná je na dnešní souřadnice (web/public/img/stare-mapy/<id>.webp)
    a spočítá GPS domů. Domy se připojí k domům místa (pl.houses[].gps), aby šly ukázat na mapě."""
    sys.path.insert(0, TOOLS)
    import georef
    by_name = {pl["name"]: pl for pl in places}
    out = []
    for m in georef.nacti():
        try:
            pr = georef.Prevod(m)
        except ValueError as e:
            print("VAROVÁNÍ – stará mapa:", e)
            continue
        if pr.chyba > georef.VAROVANI_M:
            print(f"VAROVÁNÍ – stará mapa {m['id']}: střední chyba {pr.chyba:.0f} m, zkontrolujte záchytné body (python tools/georef.py)")
        bounds = georef.narovnat(m, pr, os.path.join(WEB, "public", "img", "stare-mapy", m["id"] + ".webp"))
        pl = by_name.get(m.get("misto"))
        houses = []
        for h in m.get("domy", []):
            lat, lon = pr.gps(*h["px"])
            houses.append(dict(num=str(h.get("cislo", "")), label=h.get("popis", ""), lat=round(lat, 6), lon=round(lon, 6)))
            if pl:
                for ph in pl["houses"]:
                    if ph["num"] == str(h.get("cislo", "")):
                        ph.setdefault("gps", [round(lat, 6), round(lon, 6)])
        out.append(dict(id=m["id"], place=pl["slug"] if pl else None, title=m.get("nazev", ""), year=m.get("rok"),
                        source=m.get("zdroj", ""), img=f"/img/stare-mapy/{m['id']}.webp", bounds=bounds,
                        error=round(pr.chyba), points=len(pr.odchylky), houses=houses,
                        anchors=[dict(label=b.get("popis", ""), lat=b["gps"][0], lon=b["gps"][1])
                                 for b in m.get("body", []) if b.get("gps") and not b.get("vynechat")]))
    return out


def main():
    ns = load_people()
    P, LINES, SIDE, ISSUES = ns["P"], ns["LINES"], ns["SIDE"], ns["ISSUES"]
    if 1 not in P:
        sys.exit("V data/osoby.py chybí výchozí osoba (číslo 1).")
    SAME = ns["SAME"]                       # alias Kekulé → kanonické Kekulé (předek v rodokmenu vícekrát)
    cfg = jload("web.json", {})
    login = cfg.get("prihlaseni") or {}
    if "--nasazeni" in sys.argv and not norm_answer(login.get("odpoved", "")) and not login.get("otevreny"):
        sys.exit("CHYBA: v data/web.json není odpověď na přihlašovací otázku – web by byl otevřený komukoli.\n"
                 "Nastavte prihlaseni.odpoved, nebo (jen když to opravdu chcete) prihlaseni.otevreny: true.")
    docs_cfg = jload("dokumenty.json", [])
    recs = {r["key"]: r for r in record_rows()}

    slugs, used = {}, set()
    for k in sorted(P):
        p = P[k]
        if placeholder(p) or k in SAME:
            continue
        yv = (p.get("y") or "").strip()
        ys = [] if yv.startswith(("?", "†")) else re.findall(r"\d{4}", yv)   # rok úmrtí do adresy nedávat
        s = slugify(p["n"] + (" " + ys[0] if ys else ""))
        if s in used or not s:
            s = f"{s}-{k}"
        used.add(s)
        slugs[k] = s
    for a, c in SAME.items():
        slugs[a] = slugs[c]
    aliases_of = {}
    for a, c in SAME.items():
        aliases_of.setdefault(c, []).append(a)

    def line_of(k):
        g = gen(k)
        return k >> (g - 3) if g >= 3 else None

    side_of, rel_used = {}, set()          # příbuzní mimo linii – každý má vlastní stránku /pribuzny/<slug>/
    for e in SIDE:
        base = slugify(re.sub(r"[–(),?„“]|provd\.", " ", e["n"])) or "pribuzny"
        rs = base if base not in rel_used else f"{base}-{len(rel_used)}"
        rel_used.add(rs)
        rr = [r for r in e.get("r", []) if r in recs]
        side_of[id(e)] = dict(slug=rs, name=e["n"], text=e["t"], records=rr, sib=e.get("sour", True),
                              of=slugs.get(e["k"]), sort=birth_key(["* " + e["nar"]], [], recs) if e.get("nar") else birth_key([e["n"], e["t"]], rr, recs))

    people = {}
    for k, p in sorted(P.items()):
        if k not in slugs or k in SAME:
            continue
        path, c = [], k
        while c >= 1:
            path.append(slugs.get(c))
            c //= 2
        people[slugs[k]] = dict(
            k=k, slug=slugs[k], name=p["n"], y=p.get("y", ""), years=years(p.get("y")), st=p.get("st", "unk"),
            status=STATUS.get(p.get("st"), ""), gen=gen(k), sex="M" if k == 1 and p.get("sex", "M") == "M" or k > 1 and k % 2 == 0 else "F",
            rel=relation(k), line=line_of(k), facts=p.get("f", []), note=p.get("note", ""), records=[r for r in p.get("r", []) if r in recs],
            father=slugs.get(2 * k), mother=slugs.get(2 * k + 1),
            fatherUnknown=(2 * k in P and placeholder(P[2 * k])), motherUnknown=(2 * k + 1 in P and placeholder(P[2 * k + 1])),
            child=slugs.get(k // 2) if k > 1 else None, spouse=slugs.get(k ^ 1) if k > 1 else None,
            family=None, ownFamily=None, path=path,
            side=[side_of[id(s)] for s in SIDE if s["k"] == k],
            docs=[dict(img=d["img"], caption=d["popis"], source=d.get("zdroj", "")) for d in docs_cfg if k in d.get("osoby", [])],
            children=[slugs[c] for c in [k // 2] + [a // 2 for a in aliases_of.get(k, [])] if k > 1 and c in slugs],
            also=[dict(k=a, rel=relation(a), line=line_of(a), child=slugs.get(a // 2)) for a in aliases_of.get(k, [])],
            sort=birth_key([p.get("y", "")] + [x for x in p.get("f", []) if x.lstrip().startswith(("*", "~"))], [], recs),   # jen vlastní údaje – v r jsou i křty dětí
        )
        if aliases_of.get(k):
            for a in aliases_of[k]:
                people[slugs[k]]["records"] = list(dict.fromkeys(people[slugs[k]]["records"] + [r for r in P[a].get("r", []) if r in recs]))
            people[slugs[k]]["facts"] = [f for f in people[slugs[k]]["facts"] if not f.startswith("TÁŽ OSOBA")]

    families = {}
    for k in sorted(P):
        f, m = 2 * k, 2 * k + 1
        if k not in slugs or k in SAME or (f not in slugs and m not in slugs):
            continue
        fs, ms = slugs.get(f), slugs.get(m)
        fid = "-a-".join(x for x in (fs, ms) if x) if fs and ms else (fs or ms) + "-rodina"
        surname = (P[m]["n"].split()[-1] if m in P else "").strip("()?")
        mfacts = [x for x in P.get(f, {}).get("f", []) + P.get(m, {}).get("f", []) if x.startswith("×")]
        marriage = [x for x in mfacts if surname and surname[:5] in x] or mfacts
        frec = P.get(f, {}).get("r", []) + P.get(m, {}).get("r", [])
        child_rec = [r for r in P[k].get("r", []) if r in recs and recs[r]["kind"] == "N"]
        rlist = [r for r in dict.fromkeys(frec) if r in recs and recs[r]["kind"] == "O"] + child_rec
        if fid in families:   # stejný pár potkán dvakrát (předek v rodokmenu vícekrát) – jedna rodina, víc dětí
            fam = families[fid]
            fam["children"].append(slugs[k])
            fam["records"] = list(dict.fromkeys(fam["records"] + rlist))
            fam["side"] += people[slugs[k]]["side"]
        else:
            families[fid] = dict(id=fid, father=fs, mother=ms, fatherUnknown=f in P and placeholder(P[f]),
                                 child=slugs[k], children=[slugs[k]], marriage=marriage, records=rlist,
                                 line=line_of(f) if f in P else line_of(m), gen=gen(f), side=list(people[slugs[k]]["side"]))
        people[slugs[k]]["family"] = fid
        for x in (fs, ms):
            if x:
                people[x]["ownFamily"] = fid

    refs = {}
    for s, p in people.items():
        for r in p["records"] + [r for e in p["side"] for r in e["records"]]:
            refs.setdefault(r, []).append(s)
    hl = jload("zvyrazneni.json", {})
    prep = jload("prepisy.json", {})
    records = []
    for key, r in recs.items():
        r = dict(r)
        r["boxes"] = hl.get(key, {}).get("boxes", [])
        tr = prep.get(key, {})
        r["orig"], r["cs"] = tr.get("orig", ""), tr.get("cs", "")
        r["kindName"] = KINDS.get(r["kind"], r["kind"])
        r["people"] = list(dict.fromkeys(refs.get(key, [])))
        records.append(r)

    lines = {}
    for k, (name, desc) in sorted(LINES.items()):
        if k not in LINE_COLORS:
            continue
        members = [(p["k"], p) for p in people.values() if p["line"] == k]
        members += [(a["k"], p) for p in people.values() for a in p["also"] if a["line"] == k]
        members.sort(key=lambda x: x[0])
        lines[slugify(name)] = dict(k=k, slug=slugify(name), name=name, desc=desc, color=LINE_COLORS[k],
                                    root=slugs.get(k), people=[p["slug"] for _, p in members],
                                    gens={p["slug"]: gen(kk) for kk, p in members})
    lines = {s: l for s, l in lines.items() if l["root"]}
    for p in people.values():
        p["lineSlug"] = next((l["slug"] for l in lines.values() if l["k"] == p["line"]), None)

    places = build_places(people, docs_cfg)
    old_maps = build_old_maps(places)

    known = [p for p in people.values() if p["k"] > 1]
    stats = dict(ancestors=len(known), documented=sum(p["st"] == "doc" for p in known), records=len(records),
                 generations=max(p["gen"] for p in people.values()) + 1)
    hypotheses = [dict(line=h.get("rod"), title=h.get("nadpis", "Hypotéza"), text=h.get("text", ""),
                       items=[dict(name=a, text=b) for a, b in h.get("polozky", [])],
                       records=[r for r in h.get("zaznamy", []) if r in recs]) for h in ns["HYPOTEZY"]]

    has_story = os.path.exists(os.path.join(DATA, "pribeh.md"))
    public_cfg = {k: v for k, v in cfg.items() if k != "prihlaseni"}
    public_cfg["maPribeh"] = has_story
    relatives = {}
    for e in side_of.values():
        if e["of"] in people:
            relatives[e["slug"]] = dict(e, family=people[e["of"]]["family"])
    key_file = os.path.join(ROOT, ".mapy_api_klic")   # klíč k Mapy.com (git ho ignoruje); bez něj jen OSM a ortofoto ČÚZK
    mapy_key = open(key_file, encoding="utf-8").read().strip() if os.path.exists(key_file) else ""
    site = dict(relatives=relatives, config=public_cfg, oldMaps=old_maps, mapyKey=mapy_key, places=places, root=slugs[1], aliases={a: slugs[a] for a in SAME}, people=people,
                families=families, records=records, lines=lines,
                issues=[dict(title=i, text="") if isinstance(i, str) else dict(title=i[0], text=i[1]) for i in ISSUES], stats=stats, hypotheses=hypotheses,
                docs=[dict(img=d["img"], caption=d["popis"], people=[slugs[k] for k in d.get("osoby", []) if k in slugs],
                           place=slugify(d["misto"]) if d.get("misto") else None, house=str(d.get("dum", "")) or None,
                           year=d.get("rok"), source=d.get("zdroj", ""))
                      for d in docs_cfg if os.path.exists(os.path.join(VYREZY, d["img"] + ".jpg"))])

    write(os.path.join(WEB, "src", "data", "site.json"), json.dumps(site, ensure_ascii=False, indent=1))
    gen_dir = os.path.join(WEB, "src", "generated")
    for src, dst in (("archivni_dotazy.md", "dotazy.md"), ("research_log.md", "denik.md"), ("zajimavosti.md", "zajimavosti.md")):
        path = os.path.join(DATA, src)
        text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        write(os.path.join(gen_dir, dst), strip_comments(re.sub(r"^# .*\n", "", text, count=1)))
    mista_dir = os.path.join(gen_dir, "mista")   # texty míst: celé znovu, ať nezůstanou smazané
    shutil.rmtree(mista_dir, ignore_errors=True)
    os.makedirs(mista_dir, exist_ok=True)
    for pl in places:
        if pl["hasText"]:
            text = open(os.path.join(MISTA_MD, pl["slug"] + ".md"), encoding="utf-8").read()
            write(os.path.join(mista_dir, pl["slug"] + ".md"), strip_comments(re.sub(r"^# .*\n", "", text, count=1)))
    story = os.path.join(DATA, "pribeh.md")
    write(os.path.join(gen_dir, "pribeh.md"), strip_comments(open(story, encoding="utf-8").read()) if has_story else "---\ntitle: Příběh\nlead: ''\n---\n")

    hrefs = os.path.join(gen_dir, "fan_hrefs.json")
    json.dump({k: f"/osoba/{s}/" for k, s in slugs.items()}, open(hrefs, "w", encoding="utf-8", newline="\n"))
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(TOOLS, "fan_chart.py"),
                    os.path.join(gen_dir, "fan.svg"), "--web", hrefs], check=True, capture_output=True)

    gated = login_files(cfg)

    copied = 0
    zv = os.path.join(DATA, "zvyrazneni.json")
    hl_mtime = os.path.getmtime(zv) if os.path.exists(zv) else 0
    for sub, src_dir in (("img", VYREZY), ("zdroje", ZDROJE)):
        dst_dir = os.path.join(WEB, "public", sub)
        os.makedirs(dst_dir, exist_ok=True)
        for key in list(recs) + [d["img"] for d in docs_cfg] + [pl["photo"] for pl in places if pl["photo"]] + \
                ([cfg["uvod"]["foto"]] if cfg.get("uvod", {}).get("foto") else []):
            src = os.path.join(src_dir, key + ".jpg")
            dst = os.path.join(dst_dir, key + ".jpg")
            if not os.path.exists(src):
                continue
            boxes = hl.get(key, {}).get("boxes", [])
            stale = not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst) \
                or (sub == "zdroje" and boxes and hl_mtime > os.path.getmtime(dst))
            if not stale:
                continue
            if sub == "zdroje" and boxes and draw_boxes(src, dst, boxes, os.path.join(VYREZY, key + ".jpg")):
                copied += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
    print(f"{len(people)} osob, {len(families)} rodin, {len(records)} zápisů, {len(lines)} rodů, {len(places)} míst; "
          f"zkopírováno {copied} obrázků; přihlášení {'zapnuté' if gated else 'VYPNUTÉ (web je otevřený)'}")

    # odkazy v textech, které nikam nevedou (adresa osoby se změní třeba doplněním roku narození: jan-novak → jan-novak-1798)
    targets = dict(osoba=people, zdroj=recs, rod=lines, rodina=families, misto={pl["slug"]: pl for pl in places})
    texts = {f: open(os.path.join(gen_dir, f), encoding="utf-8").read() for f in ("pribeh.md", "zajimavosti.md")}
    texts.update({f"mista/{pl['slug']}.md": open(os.path.join(mista_dir, pl["slug"] + ".md"), encoding="utf-8").read()
                  for pl in places if pl["hasText"]})
    texts["web.json"] = json.dumps(cfg, ensure_ascii=False)
    texts["osoby.py (hypotézy)"] = json.dumps(hypotheses, ensure_ascii=False)
    broken = [(f, m.group(0)) for f, t in texts.items()
              for m in re.finditer(r"/(osoba|zdroj|rod|rodina|misto)/([^/\s)\"'#?<>\]]+)", t) if m.group(2) not in targets[m.group(1)]]
    for f, link in dict.fromkeys(broken):
        print(f"POZOR: nefunkční odkaz {link}/ v {f} – oprav ho (adresy stránek jsou ve web/src/data/site.json)")


if __name__ == "__main__":
    main()
