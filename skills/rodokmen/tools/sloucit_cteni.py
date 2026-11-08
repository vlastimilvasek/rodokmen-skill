# Sloučení dvou nezávislých čtení rejstříku do jednoho seznamu záznamů.
#   shoda příjmení (sjednocený klíč)  → 1 záznam, jistý, pokud aspoň jedno čtení je bez „?“
#   rozdíl příjmení                   → 2 záznamy (obě varianty, ať najde hledání kteroukoli), nejisté
#   jen v jednom čtení                → 1 záznam, nejistý
# Párování: (snímek, pag, jméno) → pak (snímek, pag ±1, příjmení) → pak (snímek, pag, podobné jméno).
import importlib.util, collections, difflib, os
_spec = importlib.util.spec_from_file_location("ik", os.path.join(os.path.dirname(__file__), "index_knih.py"))
ik = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ik)

KOMIN = ("sn", "q", "pis", "pr", "jm", "pag", "rok")      # sn|čtvrtina|písmeno|příjmení|jméno|pag|rok
VESELI = ("sn", "q", "pis", "rok", "pr", "jm", "pag")     # sn|čtvrtina|písmeno|rok|příjmení|jméno|folio


def nacti(soubory, poradi=KOMIN):
    out = []
    for f in soubory if isinstance(soubory, (list, tuple)) else [soubory]:
        if not os.path.exists(f): continue
        for r in open(f, encoding="utf-8"):
            p = r.rstrip("\n").split("|")
            if len(p) < 6 or not p[0].strip().isdigit(): continue
            p += [""] * (7 - len(p))
            z = {k: v.strip() for k, v in zip(poradi, p)}
            z["sn"] = int(z["sn"])
            out.append(z)
    return out


def _cislo(s):
    s = s.rstrip("?")
    return int(s) if s.isdigit() else None


def _kp(z): return ik.klic_prijmeni(z["pr"].replace("?", ""))
def _kj(z):
    import re as _re
    j = _re.sub(r"\(.*?\)", "", z["jm"].replace("?", "")).split()
    return ik.klic_jmena(j[0])[:4] if j else ""


def sloucit(A, B, opravy=None):
    """Vrátí (záznamy, statistika). Záznam: dict sn, q, pis, pr, jm, pag, rok, jistota, pozn."""
    opravy = opravy or {}
    for z in A + B:
        holy = z["pr"].rstrip("?")
        if holy in opravy: z["pr"] = opravy[holy]; z["opraveno"] = True
    zbyva_b = list(B)
    pary, jenA = [], list(A)
    def najdi(a, test):
        for b in zbyva_b:
            if b["sn"] == a["sn"] and test(a, b): return b
    for krok in (lambda a, b: a["pag"].rstrip("?") == b["pag"].rstrip("?") and _kj(a) == _kj(b),
                 lambda a, b: _kp(a) == _kp(b) and None not in (_cislo(a["pag"]), _cislo(b["pag"])) and abs(_cislo(a["pag"]) - _cislo(b["pag"])) <= 1
                              and difflib.SequenceMatcher(None, _kj(a), _kj(b)).ratio() > 0.6,
                 lambda a, b: a["pag"].rstrip("?") == b["pag"].rstrip("?") and (difflib.SequenceMatcher(None, _kj(a), _kj(b)).ratio() > 0.6
                              or difflib.SequenceMatcher(None, _kp(a), _kp(b)).ratio() > 0.6)):
        zbyva_a = []
        for a in jenA:
            b = najdi(a, krok)
            if b: zbyva_b.remove(b); pary.append((a, b))
            else: zbyva_a.append(a)
        jenA = zbyva_a
    out, st = [], collections.Counter()
    for a, b in pary:
        jisty_a, jisty_b = "?" not in a["pr"] + a["pag"], "?" not in b["pr"] + b["pag"]
        zaklad = a if jisty_a or not jisty_b else b
        if _kp(a) == _kp(b):
            st["shoda"] += 1
            pr = (a if "?" not in a["pr"] else b)["pr"]
            jist = None if ("?" not in a["pr"] or "?" not in b["pr"]) and (a.get("opraveno") or "?" not in pr) else "nejistá"
            out.append({**zaklad, "pr": pr.rstrip("?"), "jm": zaklad["jm"].rstrip("?"), "jistota": jist,
                        "pozn": None if a["pag"] == b["pag"] else "pag %s / %s" % (a["pag"], b["pag"])})
        else:
            st["rozdil"] += 1
            for z, j in ((a, b), (b, a)):
                out.append({**zaklad, "pr": z["pr"].rstrip("?"), "jm": zaklad["jm"].rstrip("?"), "jistota": "nejistá",
                            "pozn": "čtení se liší: %s / %s" % (a["pr"], b["pr"])})
    for z in jenA + zbyva_b:
        st["jen_jedno"] += 1
        out.append({**z, "pr": z["pr"].rstrip("?"), "jm": z["jm"].rstrip("?"), "jistota": "nejistá", "pozn": "jen v jednom čtení"})
    return out, st


if __name__ == "__main__":
    import sys
    A, B = nacti(sys.argv[1]), nacti(sys.argv[2])
    out, st = sloucit(A, B)
    print(len(A), len(B), dict(st))
    for z in out:
        if z["jistota"]: print(z["sn"], z["q"], z["pag"], z["pr"], z["jm"], "|", z["pozn"])


def nacti_veseli_stare(soubory):
    """Starší čtení Veselí (pracovni/idx/r5915/vystup_*.txt): „<sn>|<písmeno>|<rok>: Příjmení Jméno folio; …“."""
    import re, glob as _g
    out = []
    for f in sorted(_g.glob(soubory)):
        for radek in open(f, encoding="utf-8"):
            m = re.match(r"\s*(\d+)\|([^|]*)\|(\d{4})\s*:\s*(.*)", radek)
            if not m: continue
            for it in m[4].split(";"):
                it = it.strip().strip(".")
                mm = re.match(r"(.+?)\s+(\d{1,3}\??)\s*$", it)
                if not mm: continue
                nm = mm[1].replace("fol.", "").split()
                if not nm: continue
                out.append({"sn": int(m[1]), "q": "", "pis": m[2].strip(), "rok": m[3], "pr": nm[0], "jm": " ".join(nm[1:]), "pag": mm[2]})
    return out
