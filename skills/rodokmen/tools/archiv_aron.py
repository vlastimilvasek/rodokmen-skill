#!/usr/bin/env python3
"""Místní archiv snímků z ARONu (SOA Zámrsk) – celé knihy v plném rozlišení, aby se nemusely listovat znovu.

ARON dává ke každému snímku původní JPEG v plném rozlišení jedním požadavkem
(`/api/aron/referencedfiles/<id>`, id = soubor typu PUBLISHED v popisu svazku, ~2–5 MB, ~2 s) – žádné dlaždice.
Ukládá se do stejné struktury jako archiv MZA (`archiv_snimku.py`), takže nad oběma funguje `index_knih.py`:

  archiv/aron/<kniha>/0001.jpg      originál (kniha = prvních 8 znaků apu, stejný klíč jako v data/svazky.json)
  archiv/aron/<kniha>/0001_m.jpg    náhled 1600 px na listování
  archiv/aron/fronta.json           které knihy stáhnout (pořadí)
  archiv/aron/index.json            co je hotové

Použití:
  archiv_aron.py najdi "<obec>[,…]" [--pridat]   knihy obce na ARONu se snímky (řk. i evang.); --pridat = do fronty
  archiv_aron.py pridej <apu> [<apu> …]          přidá knihy do fronty (apu celé nebo 8 znaků, je-li v svazky.json)
  archiv_aron.py plan                            do fronty všechny knihy ARON z data/svazky.json (nejpoužívanější napřed)
  archiv_aron.py stahni [--fronty 2] [--do 7]    stáhne frontu (na noc; skončí v --do hodin, navazuje, ověřuje velikost)
  archiv_aron.py prevzit <kniha> <složka>        převezme dříve stažené snímky (s<n>.jpg / <n>.jpg) – pevným odkazem,
                                                 bez kopírování a bez mazání (soubor pak leží v obou složkách)
  archiv_aron.py stav                            přehled
  archiv_aron.py kde <kniha> <snímek>            cesta k uloženému snímku (nebo nic) – před stahováním z portálu

Archiv je pracovní pomůcka: archiv/ nejde do gitu ani na web. Výřez pro web se dělá ze snímku jako vždy (vyrez.py).
"""
import datetime, json, os, re, shutil, subprocess, sys, threading, time
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import aron_img  # noqa: E402

ARCH = os.path.join(ROOT, "archiv", "aron")
FRONTA = os.path.join(ARCH, "fronta.json")
INDEX = os.path.join(ARCH, "index.json")
LOG = os.path.join(ARCH, "stahovani.log")
lock = threading.Lock()


def jload(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError:
        return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(p + ".tmp", p)


def log(*a):
    line = datetime.datetime.now().strftime("%d.%m. %H:%M ") + " ".join(str(x) for x in a)
    with lock:
        print(line, flush=True)
        os.makedirs(ARCH, exist_ok=True)
        open(LOG, "a", encoding="utf-8", newline="\n").write(line + "\n")


def magick():
    m = shutil.which("magick")
    if not m and os.name == "nt":
        import glob
        m = next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
    return m or shutil.which("convert")


def plne_apu(k):
    """Celé apu z 36znakového id, odkazu nebo 8znakového klíče svazku (data/svazky.json, fronta)."""
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", k)
    if m:
        return m.group(0)
    for x in jload(FRONTA, []):
        if x["kniha"] == k[:8]:
            return x["apu"]
    sv = jload(os.path.join(ROOT, "data", "svazky.json"), {}).get(k[:8])
    if sv and "/apu/" in sv.get("url", ""):
        return sv["url"].rstrip("/").split("/")[-1]
    sys.exit("Neznám celé apu pro %s – zadej celé id (36 znaků)." % k)


def originaly(apu):
    """({pořadí: (id souboru, velikost)}, popis svazku)."""
    vol = aron_img.volume(apu)
    out = {}
    for dao in vol.get("digitalObjects", []) or []:
        for f in dao.get("files", []):
            if f.get("type") == "PUBLISHED":
                out[f["order"]] = (f["id"], f.get("size"))
    return out, vol


def popis_svazku(vol):
    nazev = (vol.get("name") or "").split(": ", 1)[-1].replace("Sbírka matrik Východočeského kraje, ", "")
    return (nazev + " | " + (vol.get("description") or ""))[:240]


def cesta(kniha, sn, nahled=False):
    return os.path.join(ARCH, kniha, "%04d%s.jpg" % (sn, "_m" if nahled else ""))


def ulozene(kniha):
    d = os.path.join(ARCH, kniha)
    if not os.path.isdir(d):
        return set()
    return {int(f[:4]) for f in os.listdir(d) if re.match(r"\d{4}\.jpg$", f)}


def do_fronty(apu, popis=None, snimku=None):
    fr = jload(FRONTA, [])
    k = apu[:8]
    if any(x["kniha"] == k for x in fr):
        return False
    if popis is None or snimku is None:
        orig, vol = originaly(apu)
        popis, snimku = popis_svazku(vol), len(orig)
    fr.append({"kniha": k, "apu": apu, "popis": popis, "snimku": snimku})
    jsave(FRONTA, fr)
    return True


def cmd_najdi(args):
    import aron_search
    obce = args[0]
    pridat = "--pridat" in args
    items, cnt = aron_search.search(obce)
    print("nalezeno", cnt)
    for i in sorted(items, key=lambda i: (aron_search.place(i.get("description")), i["name"])):
        try:
            orig, vol = originaly(i["id"])
        except Exception as e:
            print("  ?   ", i["id"], type(e).__name__)
            continue
        n = len(orig)
        nazev = i["name"].split(": ", 1)[-1].replace("Sbírka matrik Východočeského kraje, ", "")
        znak = "v archivu" if len(ulozene(i["id"][:8])) >= n > 0 else ("" if n else "bez snímků")
        print("%5d  %s  %-45s %s  %s" % (n, i["id"][:8], nazev[:45], (i.get("description") or "")[:90], znak))
        if pridat and n and do_fronty(i["id"], popis_svazku(vol), n):
            print("       → přidáno do fronty")


def cmd_pridej(args):
    for a in args:
        apu = plne_apu(a)
        print(apu[:8], "přidáno" if do_fronty(apu) else "už ve frontě")


def cmd_plan(args):
    sv = jload(os.path.join(ROOT, "data", "svazky.json"), {})
    zaz = jload(os.path.join(ROOT, "data", "zaznamy.json"), [])
    zaz = zaz.values() if isinstance(zaz, dict) else zaz
    pouziti = {}
    for z in zaz:
        pouziti[z.get("svazek")] = pouziti.get(z.get("svazek"), 0) + 1
    knihy = [(k, v) for k, v in sv.items() if "/apu/" in v.get("url", "") and "vychodoceskearchivy" in v.get("url", "")]
    knihy.sort(key=lambda kv: -pouziti.get(kv[0], 0))
    n = 0
    for k, v in knihy:
        apu = v["url"].rstrip("/").split("/")[-1]
        if do_fronty(apu, (v.get("svazek", "") + " | " + v.get("popis", ""))[:240], v.get("snimku")):
            n += 1
    print("Přidáno %d knih, ve frontě %d." % (n, len(jload(FRONTA, []))))


def stahni_knihu(x, konec, m):
    k, apu = x["kniha"], x["apu"]
    orig, vol = originaly(apu)
    n = len(orig)
    chybi = [i for i in sorted(orig) if i not in ulozene(k)]
    log("START", k, x.get("popis", "")[:60], "– %d sn., chybí %d" % (n, len(chybi)))
    chyby = 0
    for i in chybi:
        if time.time() > konec:
            log("KONEC ČASU", k, "(zbývá od sn. %d)" % i)
            return False
        fid, vel = orig[i]
        out = cesta(k, i)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        for pokus in range(4):
            try:
                data = aron_img.get("%s/referencedfiles/%s" % (aron_img.API, fid), binary=True, tries=2)
                if vel and len(data) != vel:
                    raise OSError("neúplný soubor %d/%d" % (len(data), vel))
                open(out + ".tmp", "wb").write(data)
                os.replace(out + ".tmp", out)
                if m:
                    subprocess.run([m, out, "-resize", "1600x", cesta(k, i, True)], capture_output=True)
                break
            except Exception:
                time.sleep(30 * (pokus + 1))
        else:
            chyby += 1
            log("CHYBA", k, "sn. %d" % i)
    with lock:
        idx = jload(INDEX, {})
        hot = len(ulozene(k))
        idx[k] = {"apu": apu, "popis": x.get("popis") or popis_svazku(vol), "snimku": n, "ulozeno": hot, "hotovo": hot >= n}
        jsave(INDEX, idx)
    log("HOTOVO" if not chyby else "HOTOVO s chybami (%d) – spusť znovu" % chyby, k)
    return True


def cmd_stahni(args):
    k = int(args[args.index("--fronty") + 1]) if "--fronty" in args else 2
    do = int(args[args.index("--do") + 1]) if "--do" in args else 7
    t = datetime.datetime.now().replace(hour=do, minute=0, second=0, microsecond=0)
    if t <= datetime.datetime.now():
        t += datetime.timedelta(days=1)
    konec = t.timestamp()
    m = magick()
    idx = jload(INDEX, {})
    fr = [x for x in jload(FRONTA, []) if not idx.get(x["kniha"], {}).get("hotovo")]
    log("=== stahování: %d knih, %d fronty, do %s ===" % (len(fr), k, t.strftime("%d.%m. %H:%M")))

    def fronta():
        while time.time() < konec:
            with lock:
                if not fr:
                    return
                x = fr.pop(0)
            try:
                stahni_knihu(x, konec, m)
            except Exception as e:
                log("CHYBA", x["kniha"], type(e).__name__, e)

    th = [threading.Thread(target=fronta) for _ in range(k)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    log("=== konec ===")


def cmd_prevzit(args):
    k, sl = args[0][:8], args[1]
    if not os.path.isdir(sl):
        sl = os.path.join(ROOT, sl)
    os.makedirs(os.path.join(ARCH, k), exist_ok=True)
    n = 0
    for f in os.listdir(sl):
        mm = re.match(r"s?(\d+)(_m)?\.jpg$", f)
        if not mm:
            continue
        cil = cesta(k, int(mm.group(1)), bool(mm.group(2)))
        if os.path.exists(cil):
            continue
        src = os.path.join(sl, f)
        try:
            os.link(src, cil)       # pevný odkaz: žádné místo navíc, původní soubor zůstává
        except OSError:
            shutil.copy2(src, cil)  # jiný disk / souborový systém bez odkazů
        n += 1
    print("Převzato %d souborů z %s do %s" % (n, os.path.relpath(sl, ROOT), os.path.relpath(os.path.join(ARCH, k), ROOT)))


def cmd_stav(args):
    idx = jload(INDEX, {})
    celkem = hot = 0
    for x in jload(FRONTA, []):
        k = x["kniha"]
        n = x.get("snimku") or idx.get(k, {}).get("snimku") or 0
        h = len(ulozene(k))
        celkem += n
        hot += min(h, n) if n else h
        print("%s %5d / %-5s %s" % (k, h, n or "?", x.get("popis", "")[:90]))
    print("CELKEM %d / %d snímků" % (hot, celkem))


def cmd_kde(args):
    p = cesta(args[0][:8], int(args[1]))
    if os.path.exists(p):
        print(p)
    else:
        sys.exit(1)


def main():
    cmds = ("najdi", "pridej", "plan", "stahni", "prevzit", "stav", "kde")
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    globals()["cmd_" + sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
