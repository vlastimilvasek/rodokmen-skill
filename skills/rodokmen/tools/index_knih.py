#!/usr/bin/env python3
"""Index knih z místního archivu snímků (archiv/) – rychlé hledání bez listování.

Index je jen VODÍTKO, kam se podívat: údaj v rodokmenu je „doloženo“ až po přečtení zápisu přímo na snímku.

Zdroj pravdy: data/index_knih/<klic>.json (text, ne obrázky – může být v gitu, na web nejde).
Z nich se staví archiv/index.sqlite (FTS5, normalizovaný pravopis příjmení).

Použití:
  index_knih.py nahled <kniha> <od> <do> [--cast x0,y0,x1,y1] [--sloupce N] [--sirka PX] [--krok N]
        náhledový arch: zvolená část snímků od–do vedle sebe s čísly snímků → pracovni/idx/… (pro čtení mapy knihy)
  index_knih.py nacti                     postaví archiv/index.sqlite ze všech data/index_knih/*.json
  index_knih.py hledej <příjmení> [jméno] [--obec X] [--od R] [--do R] [--druh N|O|Z]
        rejstříky a zápisy; pravopis se sjednocuje (Vašek = Waschek = Wašek, Kachlík = Kachlikowa…)
  index_knih.py kde <obec> <druh> <rok>[-<měsíc>]   které snímky pokrývají daný rok (z mapy knihy)
  index_knih.py stav                      co je v indexu

Formát data/index_knih/mza_<kniha>.json:
  {"kniha": "5915", "svazek": "mza_5915",
   "mapa": [ {"od": 2, "do": 37, "druh": "Z", "obec": "Komín", "rok_od": 1784, "rok_do": 1830, "pozn": "…"} ],
   "snimky": {"12": {"rok": "1786", "mesice": "I–IV", "folio": "10–11", "obec": "Komín", "druh": "Z"}},
   "rejstrik": [ {"sn": 458, "prijmeni": "Bílek", "jmeno": "Jan", "folio": "466", "rok": 1814, "cil": 230, "obec": "…"} ],
   "zapisy": [ {"sn": 29, "druh": "Z", "datum": "1821-08-10", "dum": "9", "obec": "Komín",
                "osoby": [{"role": "zemřelý", "jmeno": "Bernard", "prijmeni": "Kachlík", "vek": "66"}], "jistota": "dobrá"} ],
   "cetl": "Claude 2026-11-07", "pozn": "…"}
  „jistota“: "nejistá" u nejistého čtení. „cil“ = snímek, na kterém zápis z rejstříku leží (folio → snímek podle mapy; když nejde určit, chybí).
"""
import glob, json, os, re, sqlite3, subprocess, sys, unicodedata
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(ROOT, "data", "index_knih")
DB = os.path.join(ROOT, "archiv", "index.sqlite")
MZA = os.path.join(ROOT, "archiv", "mza")


def magick():
    import shutil
    m = shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
    if not m:
        sys.exit("Chybí ImageMagick (magick).")
    return m


def opt(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def klic_prijmeni(s):
    """Sjednocení pravopisu příjmení pro hledání: bez diakritiky, německé/latinské zápisy → české, bez ženských koncovek."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("sch", "s"), ("tsch", "c"), ("cz", "c"), ("tz", "c"), ("sz", "s"), ("ss", "s"), ("w", "v"),
                 ("th", "t"), ("ph", "f"), ("ck", "k"), ("qu", "kv"), ("y", "i"), ("j", "i"), ("x", "ks"), ("g", "h")):
        s = s.replace(a, b)
    for kon in ("ovna", "ova", "inna", "ina", "in", "a"):   # Kachlíková, Kachlikowa, Wotawin, Wotawa → kachlik / votav
        if len(s) > len(kon) + 3 and s.endswith(kon):
            s = s[: -len(kon)]
            break
    s = re.sub(r"(.)\1+", r"\1", s)   # zdvojená písmena
    return s


def klic_jmena(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z]", "", s)
    return {"joannes": "jan", "johann": "jan", "johannes": "jan", "ioannes": "jan", "joseph": "josef", "josephus": "josef",
            "wenzel": "vaclav", "wenceslaus": "vaclav", "mathias": "matej", "matthias": "matej", "georg": "jiri", "georgius": "jiri",
            "franz": "frantisek", "franciscus": "frantisek", "maria": "marie", "marianna": "marie", "anna": "anna",
            "catharina": "katerina", "katharina": "katerina", "theresia": "terezie", "thekla": "tekla", "thecla": "tekla",
            "bernardus": "bernard", "thomas": "tomas", "simon": "simon", "barbara": "barbora", "elisabetha": "alzbeta",
            "magdalena": "magdalena", "martinus": "martin", "andreas": "ondrej", "jacobus": "jakub", "jakob": "jakub",
            "paulus": "pavel", "paul": "pavel", "petrus": "petr", "peter": "petr", "laurentius": "vavrinec",
            "lorenz": "vavrinec", "antonius": "antonin", "anton": "antonin", "carolus": "karel", "karl": "karel"}.get(s, s)


def cmd_nahled(args):
    kniha, od, do = args[0].replace("mza_", ""), int(args[1]), int(args[2])
    cast = [float(x) for x in opt(args, "--cast", "0,0,1,0.35").split(",")]
    sloupce = int(opt(args, "--sloupce", "2"))
    sirka = int(opt(args, "--sirka", "900"))
    m = magick()
    out_dir = os.path.join(ROOT, "pracovni", "idx")
    os.makedirs(out_dir, exist_ok=True)
    dily = []
    krok = int(opt(args, "--krok", "1"))   # např. každý 10. snímek – u souvislých knih stačí na mapu let
    for sn in range(od, do + 1, krok):
        f = os.path.join(MZA, kniha, "%04d.jpg" % sn)
        if not os.path.exists(f):
            continue
        t = os.path.join(out_dir, "_t%04d.png" % sn)
        x0, y0, x1, y1 = cast
        crop = "%%[fx:w*%g]x%%[fx:h*%g]+%%[fx:w*%g]+%%[fx:h*%g]" % (x1 - x0, y1 - y0, x0, y0)   # zlomky 0–1 → pixely
        subprocess.run([m, f, "-crop", crop, "+repage", "-resize", "%dx" % sirka, "-gravity", "NorthWest", "-fill", "red", "-pointsize", "34",
                        "-undercolor", "white", "-annotate", "+6+4", "sn %d" % sn, t], check=True)
        dily.append(t)
    if not dily:
        sys.exit("Žádné snímky v archiv/mza/%s/ pro %d–%d" % (kniha, od, do))
    out = os.path.join(out_dir, "%s_%04d-%04d.jpg" % (kniha, od, do))
    subprocess.run([m, "montage", *dily, "-tile", "%dx" % sloupce, "-geometry", "+4+4", "-background", "#888", "-quality", "85", out], check=True)
    for t in dily:
        os.remove(t)
    print(out)


SCHEMA = """
CREATE TABLE kniha(kniha TEXT PRIMARY KEY, svazek TEXT, cetl TEXT, pozn TEXT);
CREATE TABLE mapa(kniha TEXT, od INT, do INT, druh TEXT, obec TEXT, rok_od INT, rok_do INT, pozn TEXT);
CREATE TABLE snimek(kniha TEXT, sn INT, rok TEXT, mesice TEXT, folio TEXT, obec TEXT, druh TEXT, pozn TEXT);
CREATE TABLE rejstrik(kniha TEXT, sn INT, prijmeni TEXT, jmeno TEXT, folio TEXT, rok INT, cil INT, obec TEXT, druh TEXT, kp TEXT, kj TEXT, jistota TEXT);
CREATE TABLE zapis(id INTEGER PRIMARY KEY, kniha TEXT, sn INT, druh TEXT, datum TEXT, dum TEXT, obec TEXT, jistota TEXT, pozn TEXT);
CREATE TABLE osoba(zapis INT, role TEXT, jmeno TEXT, prijmeni TEXT, vek TEXT, pozn TEXT, kp TEXT, kj TEXT);
CREATE INDEX ix_r ON rejstrik(kp); CREATE INDEX ix_o ON osoba(kp);
"""


def cmd_nacti(args):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    n = {"knih": 0, "rejstrik": 0, "zapisu": 0}
    for f in sorted(glob.glob(os.path.join(JSON_DIR, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        k = str(d["kniha"])
        db.execute("INSERT INTO kniha VALUES(?,?,?,?)", (k, d.get("svazek"), d.get("cetl"), d.get("pozn")))
        for m in d.get("mapa", []):
            db.execute("INSERT INTO mapa VALUES(?,?,?,?,?,?,?,?)", (k, m["od"], m["do"], m.get("druh"), m.get("obec"), m.get("rok_od"), m.get("rok_do"), m.get("pozn")))
        for sn, s in d.get("snimky", {}).items():
            db.execute("INSERT INTO snimek VALUES(?,?,?,?,?,?,?,?)", (k, int(sn), s.get("rok"), s.get("mesice"), s.get("folio"), s.get("obec"), s.get("druh"), s.get("pozn")))
        for r in d.get("rejstrik", []):
            db.execute("INSERT INTO rejstrik VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (k, r.get("sn"), r.get("prijmeni"), r.get("jmeno"), r.get("folio"), r.get("rok"), r.get("cil"),
                                                                             r.get("obec"), r.get("druh"), klic_prijmeni(r.get("prijmeni")), klic_jmena(r.get("jmeno")), r.get("jistota")))
            n["rejstrik"] += 1
        for z in d.get("zapisy", []):
            c = db.execute("INSERT INTO zapis(kniha,sn,druh,datum,dum,obec,jistota,pozn) VALUES(?,?,?,?,?,?,?,?)",
                           (k, z.get("sn"), z.get("druh"), z.get("datum"), z.get("dum"), z.get("obec"), z.get("jistota"), z.get("pozn")))
            for o in z.get("osoby", []):
                db.execute("INSERT INTO osoba VALUES(?,?,?,?,?,?,?,?)", (c.lastrowid, o.get("role"), o.get("jmeno"), o.get("prijmeni"), o.get("vek"), o.get("pozn"),
                                                                       klic_prijmeni(o.get("prijmeni")), klic_jmena(o.get("jmeno"))))
            n["zapisu"] += 1
        n["knih"] += 1
    db.commit()
    print("Index: %(knih)d knih, %(rejstrik)d řádků rejstříků, %(zapisu)d zápisů → archiv/index.sqlite" % n)


def pripoj():
    if not os.path.exists(DB):
        cmd_nacti([])
    return sqlite3.connect(DB)


def cmd_hledej(args):
    poz = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or not args[i - 1].startswith("--"))]
    kp = klic_prijmeni(poz[0])
    kj = klic_jmena(poz[1]) if len(poz) > 1 else None
    obec, od, do, druh = opt(args, "--obec"), opt(args, "--od"), opt(args, "--do"), opt(args, "--druh")
    db = pripoj()
    q = "SELECT r.kniha, r.sn, r.prijmeni, r.jmeno, r.folio, r.rok, r.cil, r.obec, r.druh, r.jistota FROM rejstrik r WHERE r.kp=?"
    p = [kp]
    if kj: q += " AND r.kj=?"; p.append(kj)
    if obec: q += " AND r.obec LIKE ?"; p.append("%" + obec + "%")
    if od: q += " AND r.rok>=?"; p.append(int(od))
    if do: q += " AND r.rok<=?"; p.append(int(do))
    if druh: q += " AND r.druh=?"; p.append(druh)
    rr = db.execute(q + " ORDER BY r.rok, r.kniha", p).fetchall()
    for k, sn, pr, j, fo, rok, cil, ob, dr, ji in rr:
        print("rejstřík  kniha %-6s %s %-4s %-14s %-12s pag. %-4s → snímek %-4s (rejstřík sn. %s) %s%s" % (k, dr or "", rok or "", pr, j or "", fo or "?", cil or "?", sn, ob or "", " [čtení nejisté]" if ji == "nejistá" else ""))
    q = ("SELECT z.kniha, z.sn, z.druh, z.datum, z.dum, z.obec, o.role, o.jmeno, o.prijmeni, o.vek, z.jistota FROM osoba o JOIN zapis z ON z.id=o.zapis WHERE o.kp=?")
    p = [kp]
    if kj: q += " AND o.kj=?"; p.append(kj)
    if obec: q += " AND z.obec LIKE ?"; p.append("%" + obec + "%")
    if od: q += " AND substr(z.datum,1,4)>=?"; p.append(od)
    if do: q += " AND substr(z.datum,1,4)<=?"; p.append(do)
    if druh: q += " AND z.druh=?"; p.append(druh)
    zz = db.execute(q + " ORDER BY z.datum", p).fetchall()
    for k, sn, dr, dat, dum, ob, role, j, pr, vek, ji in zz:
        print("zápis     kniha %-6s %s %-10s %-10s č. %-4s %-12s %-10s %s %s%s  → snímek %s" % (k, dr, dat or "", ob or "", dum or "", role or "", j or "", pr, ("(%s)" % vek) if vek else "", " [?]" if ji == "nejistá" else "", sn))
    if not rr and not zz:
        # přibližná shoda – rejstříky čtené z 2000 px mají v příjmeních chyby (Swatopek místo Swatosch …)
        import difflib
        kl = [r[0] for r in db.execute("SELECT DISTINCT kp FROM rejstrik UNION SELECT DISTINCT kp FROM osoba")]
        blizke = difflib.get_close_matches(kp, kl, n=6, cutoff=0.72)
        if blizke:
            print("Přesně nic; podobná příjmení v indexu (klíč „%s“):" % kp)
            for b2 in blizke:
                q2 = "SELECT DISTINCT prijmeni FROM rejstrik WHERE kp=?"
                tv = ", ".join(x[0] for x in db.execute(q2, (b2,)))
                print("   %-14s (%s) – `index_knih.py hledej %s`" % (b2, tv, tv.split(",")[0]))
        else:
            print("Nic (klíč „%s“). Index je jen pro zaindexované knihy – `index_knih.py stav`." % kp)


def cmd_kde(args):
    obec, druh, kdy = args[0], args[1].upper(), args[2]
    rok = int(kdy.split("-")[0])
    db = pripoj()
    mm = db.execute("SELECT kniha, od, do, rok_od, rok_do, obec, pozn FROM mapa WHERE druh=? AND obec LIKE ? AND rok_od<=? AND rok_do>=?",
                    (druh, "%" + obec + "%", rok, rok)).fetchall()
    if not mm:
        print("Nic v mapách knih.")
    for k, od, do, ro, rd, ob, pz in mm:
        ss = db.execute("SELECT sn, rok, mesice, folio FROM snimek WHERE kniha=? AND sn BETWEEN ? AND ? ORDER BY sn", (k, od, do)).fetchall()
        hit = [s for s in ss if s[1] and str(rok) in s[1]]
        print("kniha %s, %s %s %d–%d: snímky %d–%d%s" % (k, ob, druh, ro, rd, od, do, (" – " + pz) if pz else ""))
        if hit:
            print("   rok %d: snímky %s" % (rok, ", ".join("%d (%s%s)" % (s[0], s[2] or "", (", fol. " + s[3]) if s[3] else "") for s in hit)))
        elif ss:
            pred = [s for s in ss if s[1] and s[1][:4].isdigit() and int(s[1][:4]) <= rok]
            po = [s for s in ss if s[1] and s[1][:4].isdigit() and int(s[1][:4]) > rok]
            print("   mezi snímky %s a %s" % (pred[-1][0] if pred else od, po[0][0] if po else do))


def cmd_stav(args):
    for f in sorted(glob.glob(os.path.join(JSON_DIR, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        print("%-10s mapa %d oddílů, %d snímků s rokem, rejstřík %d řádků, zápisů %d  (%s)" % (
            d.get("svazek"), len(d.get("mapa", [])), len(d.get("snimky", {})), len(d.get("rejstrik", [])), len(d.get("zapisy", [])), d.get("cetl", "")))


def main():
    cmds = ("nahled", "nacti", "hledej", "kde", "stav")
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    globals()["cmd_" + sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
