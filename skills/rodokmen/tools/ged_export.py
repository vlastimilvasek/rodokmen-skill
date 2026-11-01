#!/usr/bin/env python3
"""Export rodokmenu (data/osoby.py + data/zaznamy.json + data/prepisy.json) do GEDCOM 5.5.1 (UTF-8).

Použití:  ged_export.py [vystup.ged]      (výchozí vystupy/rodokmen.ged)

Osoby podle Kekulého čísel, rodiny 2n × 2n+1 s dítětem n. Fakta „*“, „×“, „†“ jdou do BIRT/MARR/DEAT
(datum + místo), ostatní fakta, stav doložení a poznámka do NOTE. Zápisy z matrik jsou zdroje (SOUR)
s odkazem na snímek a českým překladem přepisu.
"""
import json, os, re, runpy, sys
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
STAV = {"doc": "doloženo matrikou", "prob": "pravděpodobné", "fam": "údaj od rodiny",
        "mh": "z cizího rodokmenu (neověřeno)", "unk": "neznámé"}
DATUM = re.compile(r"^(?:(asi|před|po)\s+)?(?:(\d{1,2})\.\s*(\d{1,2})\.\s*|(\d{1,2})/)?(\d{4})\s*(\(\?\))?\s*")


def ged_datum(text):
    """'3. 9. 1905 Komín č. 19' → ('3 SEP 1905', 'Komín č. 19')."""
    m = DATUM.match(text)
    if not m:
        return "", text.strip()
    pred, den, mes, mes2, rok, _ = m.groups()
    if den:
        d = f"{int(den)} {MES[int(mes) - 1]} {rok}"
    elif mes2:
        d = f"{MES[int(mes2) - 1]} {rok}"
    else:
        d = rok
    d = {"asi": "ABT ", "před": "BEF ", "po": "AFT "}.get(pred, "") + d
    return d, text[m.end():].strip()


def jmeno(n):
    n = n.strip()
    if n.startswith("(?)"):
        return "", n[3:].strip()
    casti = n.split()
    if len(casti) == 1:
        return casti[0], ""
    if casti[-1] == "(?)" and len(casti) >= 3:
        return " ".join(casti[:-2]), casti[-2] + " (?)"
    return " ".join(casti[:-1]), casti[-1]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "vystupy", "rodokmen.ged")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    d = runpy.run_path(os.path.join(ROOT, "data", "osoby.py"))
    P, SIDE = d["P"], d.get("SIDE", [])
    zaz = {z["klic"]: z for z in json.load(open(os.path.join(ROOT, "data", "zaznamy.json"), encoding="utf-8"))}
    pre = json.load(open(os.path.join(ROOT, "data", "prepisy.json"), encoding="utf-8"))
    web = json.load(open(os.path.join(ROOT, "data", "web.json"), encoding="utf-8"))

    L = ["0 HEAD", "1 SOUR RODOKMEN", "2 NAME " + (web.get("nazev") or "Rodokmen"), "1 GEDC", "2 VERS 5.5.1",
         "2 FORM LINEAGE-LINKED", "1 CHAR UTF-8", "1 LANG Czech"]

    def text(tag, s, lvl):
        """Dlouhý text rozdělený na CONC/CONT."""
        radky = str(s).split("\n")
        for i, r in enumerate(radky):
            kusy = [r[j:j + 200] for j in range(0, len(r), 200)] or [""]
            for k, kus in enumerate(kusy):
                if i == 0 and k == 0:
                    L.append(f"{lvl} {tag} {kus}".rstrip())
                elif k == 0:
                    L.append(f"{lvl + 1} CONT {kus}".rstrip())
                else:
                    L.append(f"{lvl + 1} CONC {kus}")

    def pohlavi(k, o):
        return o.get("sex") or ("M" if k % 2 == 0 else "F")

    # rodiny: klíč = číslo dítěte n, rodiče 2n a 2n+1
    rodiny = {}
    for k in sorted(P):
        if 2 * k in P or 2 * k + 1 in P:
            rodiny[k] = f"@F{k}@"

    for k in sorted(P):
        o = P[k]
        kr, pr = jmeno(o["n"])
        L += [f"0 @I{k}@ INDI", f"1 NAME {kr} /{pr}/".replace("  ", " ")]
        if kr:
            L.append(f"2 GIVN {kr}")
        if pr:
            L.append(f"2 SURN {pr}")
        L.append(f"1 SEX {pohlavi(k, o)}")
        poznamky = []
        for f in o.get("f", []):
            znak = f[:1]
            if znak in "*†" and f[1:2] == " ":
                dat, misto = ged_datum(f[2:])
                L.append("1 " + ("BIRT" if znak == "*" else "DEAT"))
                if dat:
                    L.append(f"2 DATE {dat}")
                if misto:
                    L.append(f"2 PLAC {misto}")
                if not dat and not misto:
                    poznamky.append(f)
            elif znak == "×":
                # sňatek s přímým předkem patří do rodiny; ostatní (druhé sňatky) jen do poznámky
                if k % 2 == 0 and k + 1 in P or k % 2 == 1 and k - 1 in P:
                    continue
                poznamky.append(f)
            else:
                poznamky.append(f)
        poznamky.append("Stav: " + STAV.get(o.get("st"), o.get("st", "")))
        if o.get("note"):
            poznamky.append(o["note"])
        text("NOTE", "\n".join(poznamky), 1)
        for r in o.get("r", []):
            if r in zaz:
                L.append(f"1 SOUR @S{list(zaz).index(r) + 1}@")
        if k in rodiny:
            L.append(f"1 FAMC {rodiny[k]}")
        if k >= 2:
            dite = k // 2
            L.append(f"1 FAMS {rodiny[dite]}")

    for dite, fid in rodiny.items():
        L.append(f"0 {fid} FAM")
        if 2 * dite in P:
            L.append(f"1 HUSB @I{2 * dite}@")
        if 2 * dite + 1 in P:
            L.append(f"1 WIFE @I{2 * dite + 1}@")
        L.append(f"1 CHIL @I{dite}@")
        # sňatek z fakt manžela (nebo manželky)
        for k in (2 * dite, 2 * dite + 1):
            o = P.get(k)
            if not o:
                continue
            fx = next((f for f in o.get("f", []) if f.startswith("× ")), None)
            if not fx:
                continue
            dat, zbytek = ged_datum(fx[2:])
            partner = P.get(k + 1 if k % 2 == 0 else k - 1)
            if partner and zbytek.endswith(partner["n"]):
                zbytek = zbytek[: -len(partner["n"])].strip()
            L.append("1 MARR")
            if dat:
                L.append(f"2 DATE {dat}")
            if zbytek:
                L.append(f"2 PLAC {zbytek}")
            break

    for i, (klic, z) in enumerate(zaz.items(), 1):
        L.append(f"0 @S{i}@ SOUR")
        L.append(f"1 TITL {z.get('nazev', klic)} ({z.get('datum', '')})")
        text("NOTE", (z.get("shrnuti", "") + "\n" + pre.get(klic, {}).get("cs", "")).strip(), 1)
        if z.get("odkaz"):
            L.append(f"1 WWW {z['odkaz']}")

    if SIDE:
        L.append("0 @N1@ NOTE Příbuzní mimo přímou linii:")
        for s in SIDE:
            L.append(f"1 CONT {s.get('n', '')}: {s.get('t', '')}"[:240])
    L.append("0 TRLR")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"uloženo: {out} ({len(P)} osob, {len(rodiny)} rodin, {len(zaz)} zdrojů)")


if __name__ == "__main__":
    main()
