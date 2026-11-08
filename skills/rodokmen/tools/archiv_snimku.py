#!/usr/bin/env python3
"""Místní archiv snímků matrik – aby se knihy nemusely na portálu listovat znovu kvůli jiné osobě.

Snímky z MZA (Acta Publica) ukládá v prohlížeči `tools/mza_archiv.js` (jen tím, co prohlížeč na stránce
sám zobrazil, delší strana max. 2000 px – tak to dovoluje nápověda MZA). Padají do složky Stažené soubory
jako mza_<kniha>_<snimek4>.jpg; tento nástroj je zařadí do archiv/mza/<kniha>/<snimek4>.jpg.

Použití:
  archiv_snimku.py plan [--farnosti N]   pořadí knih k uložení: farnosti s nejvíc osobami napřed → archiv/fronta.json
  archiv_snimku.py dalsi                 další nehotová kniha z fronty (pro noční běh: kniha, odkaz, od kterého snímku)
  archiv_snimku.py zarad [--zdroj DIR]   přesune stažené snímky a souhrny ze Stažených souborů do archiv/
  archiv_snimku.py stav                  přehled: kolik snímků které knihy je uloženo
  archiv_snimku.py kde <kniha> <snimek>  cesta k uloženému snímku (nebo nic) – před listováním na portálu

<kniha> = číslo knihy MZA (např. 17547) nebo klíč svazku (mza_17547).
Archiv je jen pracovní pomůcka: nejde na web ani do gitu (archiv/ je v .gitignore) a nesmí se nikde zveřejňovat
(podmínky MZA). Přesné čtení a výřez pro web se dál dělá ze zvětšení přímo na portálu.
"""
import glob, json, os, re, shutil, sys
from collections import Counter, defaultdict
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCH = os.path.join(ROOT, "archiv")
MZA = os.path.join(ARCH, "mza")
INDEX = os.path.join(ARCH, "index.json")
FRONTA = os.path.join(ARCH, "fronta.json")
STAZENE = os.path.join(os.path.expanduser("~"), "Downloads")


def jload(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError:
        return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def cislo(k):
    return str(k).replace("mza_", "")


def farnost(sv):
    """'Brno-Komín, sv. Vavřinec, N 1784–1841, …' → 'Brno-Komín'; 'Valtice, N 1864–1893 Hlohovec, …' → 'Valtice'."""
    return sv.get("svazek", "").split(",")[0].strip() or "?"


def osoby_zaznamy():
    """Pro každou osobu (předci P + příbuzní SIDE) seznam klíčů jejích zápisů."""
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import osoby  # noqa
    out = []
    for num, o in getattr(osoby, "P", {}).items():
        out.append(("P%s" % num, o.get("r", [])))
    for i, o in enumerate(getattr(osoby, "SIDE", [])):
        out.append(("S%d" % i, o.get("r", [])))
    return out


def ulozene(c):
    return sorted(int(os.path.basename(f)[:4]) for f in glob.glob(os.path.join(MZA, c, "[0-9][0-9][0-9][0-9].jpg")))


def cmd_plan(args):
    nfar = int(args[args.index("--farnosti") + 1]) if "--farnosti" in args else 0
    svazky = jload(os.path.join(ROOT, "data", "svazky.json"), {})
    zaz = {z["klic"]: z for z in jload(os.path.join(ROOT, "data", "zaznamy.json"), [])}
    pouziti = Counter(z.get("svazek") for z in zaz.values())
    osoby_far = defaultdict(set)
    for oid, rr in osoby_zaznamy():
        for r in rr:
            sv = svazky.get(zaz.get(r, {}).get("svazek"))
            if sv:
                osoby_far[farnost(sv)].add(oid)
    far = sorted(osoby_far, key=lambda f: -len(osoby_far[f]))
    if nfar:
        far = far[:nfar]
    index = jload(INDEX, {})
    fronta = []
    for f in far:
        knihy = [(k, v) for k, v in svazky.items() if k.startswith("mza_") and farnost(v) == f and "/detail/" in v.get("url", "")]
        knihy.sort(key=lambda kv: -pouziti[kv[0]])
        for k, v in knihy:
            c = cislo(k)
            fronta.append({"kniha": c, "farnost": f, "osob_ve_farnosti": len(osoby_far[f]), "zapisu": pouziti[k],
                           "url": v["url"].split("?")[0], "svazek": v.get("svazek", ""),
                           "snimku": index.get(c, {}).get("snimku")})
    jsave(FRONTA, fronta)
    print("Farnosti podle počtu osob:")
    for f in far:
        n = sum(1 for x in fronta if x["farnost"] == f)
        print("  %3d osob  %-28s %d knih" % (len(osoby_far[f]), f, n))
    print("Fronta: %d knih → %s" % (len(fronta), os.path.relpath(FRONTA, ROOT)))


def cmd_dalsi(args):
    index = jload(INDEX, {})
    farnost = args[args.index("--farnost") + 1].lower() if "--farnost" in args else None   # např. --farnost komín
    for x in jload(FRONTA, []):
        i = index.get(x["kniha"], {})
        if farnost and farnost not in x.get("farnost", "").lower():
            continue
        if i.get("hotovo"):
            continue
        uz = ulozene(x["kniha"])
        od = 1
        while od in uz:   # navázat za souvislou řadou uložených snímků
            od += 1
        print(json.dumps({"kniha": x["kniha"], "url": x["url"], "od": od, "svazek": x["svazek"], "snimku": i.get("snimku")}, ensure_ascii=False))
        return
    print("HOTOVO – ve frontě nic nezbývá")


def cmd_zarad(args):
    zdroj = args[args.index("--zdroj") + 1] if "--zdroj" in args else STAZENE
    index = jload(INDEX, {})
    n = 0
    for f in sorted(glob.glob(os.path.join(zdroj, "mza_*_*.jpg"))):
        m = re.match(r"mza_(\d+)_(\d{4})(?: \(\d+\))?\.jpg$", os.path.basename(f))
        if not m:
            continue
        c, sn = m.groups()
        cil = os.path.join(MZA, c, sn + ".jpg")
        os.makedirs(os.path.dirname(cil), exist_ok=True)
        shutil.move(f, cil)   # novější kopie přepíše starší
        n += 1
    for f in sorted(glob.glob(os.path.join(zdroj, "mza_*_souhrn*.json"))):
        m = re.match(r"mza_(\d+)_souhrn", os.path.basename(f))
        if not m:
            continue
        c = m.group(1)
        s = jload(f, {})
        i = index.setdefault(c, {})
        i["snimku"] = s.get("snimku") or i.get("snimku")
        i["detail"] = s.get("detail") or i.get("detail")
        if s.get("chyba"):
            i["posledni_chyba"] = s["chyba"]
        os.remove(f)
    for c, i in index.items():
        uz = ulozene(c)
        i["ulozeno"] = len(uz)
        i["hotovo"] = bool(i.get("snimku")) and len(uz) >= i["snimku"]
    jsave(INDEX, index)
    print("Zařazeno %d snímků do %s" % (n, os.path.relpath(MZA, ROOT)))


def cmd_stav(args):
    index = jload(INDEX, {})
    fronta = {x["kniha"]: x for x in jload(FRONTA, [])}
    knihy = sorted(set(index) | set(fronta), key=lambda c: list(fronta).index(c) if c in fronta else 9999)
    celkem = 0
    for c in knihy:
        uz = len(ulozene(c))
        celkem += uz
        i, x = index.get(c, {}), fronta.get(c, {})
        print("%-6s %4d/%-4s %s %s" % (c, uz, i.get("snimku") or "?", "✔" if i.get("hotovo") else " ", x.get("svazek", "")[:80]))
    mb = sum(os.path.getsize(f) for f in glob.glob(os.path.join(MZA, "*", "*.jpg"))) / 1e6
    print("Celkem %d snímků, %.0f MB" % (celkem, mb))


def cmd_kde(args):
    c, sn = cislo(args[0]), int(args[1])
    p = os.path.join(MZA, c, "%04d.jpg" % sn)
    if os.path.exists(p):
        print(p)
    else:
        sys.exit(1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("plan", "dalsi", "zarad", "stav", "kde"):
        print(__doc__)
        sys.exit(2)
    globals()["cmd_" + sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
