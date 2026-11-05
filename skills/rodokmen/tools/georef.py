"""Georeferencování starých map: převod pixelů staré mapy (indikační skica, katastrální mapa…) na dnešní GPS.

Mapy a záchytné body jsou v data/stare_mapy.json (seznam), každá mapa:
  {"id": "straznice_1827", "misto": "Strážnice", "nazev": "Indikační skica stabilního katastru", "rok": 1827,
   "obraz": "dokumenty/indikacni-skici/straznice_1827.jpg", "orez": [x0, y0, x1, y1],   # část obrázku na web
   "skryt": [[x0, y0, x1, y1], …],         # obdélníky, které na překryvu nemají být (seznamy majitelů, vložené výřezy)
   "zacelit": [[x0, y0, x1, y1, dx, dy], …],  # obdélník (legenda, nápis) přemalovat okolním papírem z místa posunutého o dx, dy
   "zdroj": "MZA Brno, …", "transformace": "podobnost" | "afinni",
   "body": [{"px": [x, y], "gps": [lat, lon], "popis": "kostel sv. Martina – křížení lodí", "vynechat": false}],
   "domy": [{"px": [x, y], "cislo": "161", "popis": "Jiří Lípa (1827)"}]}
Záchytné body = místa, která se od doby mapy nezměnila (kostely, brány, nároží, mosty); GPS odečíst na mapy.com
(pravé tlačítko → souřadnice). Čísla domů jako body NEPOUŽÍVAT – domy se přečíslovávaly a města s předměstím
měla samostatné číslování.

Podobnostní transformace (posun, otočení, měřítko) stačí na jeden list nebo poctivě složenou mapu a potřebuje
aspoň 2 body (rozumně 4+); afinní (i zkosení) aspoň 3 (rozumně 6+). Odchylky bodů ukážou, jestli převod sedí:
do ~15 m je výborné (šířka domu), přes 30 m znamená špatně určený bod nebo nepřesně složenou mapu.

Použití:  python tools/georef.py                 – všechny mapy: odchylky bodů a GPS domů
          python tools/georef.py <id> x,y …      – GPS libovolných pixelů na mapě <id> (s odkazem na mapy.com)
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUBOR = os.path.join(ROOT, "data", "stare_mapy.json")
VAROVANI_M = 30


class Prevod:
    """Transformace pixel → (lat, lon) spočtená metodou nejmenších čtverců ze záchytných bodů."""

    def __init__(self, mapa):
        import numpy as np
        self.typ = mapa.get("transformace", "podobnost")
        pts = [b for b in mapa.get("body", []) if b.get("gps") and not b.get("vynechat")]
        need = 3 if self.typ == "afinni" else 2
        if len(pts) < need:
            raise ValueError(f"mapa {mapa.get('id')}: málo záchytných bodů ({len(pts)}, potřeba aspoň {need})")
        self.lat0 = sum(b["gps"][0] for b in pts) / len(pts)
        self.lon0 = sum(b["gps"][1] for b in pts) / len(pts)
        self.kx, self.ky = 111320 * math.cos(math.radians(self.lat0)), 110574
        P = np.array([b["px"] for b in pts], float)
        E = np.array([self._en(*b["gps"]) for b in pts], float)
        if self.typ == "afinni":
            self.M = np.linalg.lstsq(np.c_[P, np.ones(len(P))], E, rcond=None)[0]
        else:   # e = a x + b y + c, n = b x − a y + d (osa y obrázku míří dolů)
            A = np.zeros((2 * len(P), 4)); r = np.zeros(2 * len(P))
            for i, ((x, y), (e, n)) in enumerate(zip(P, E)):
                A[2 * i], r[2 * i] = [x, y, 1, 0], e
                A[2 * i + 1], r[2 * i + 1] = [-y, x, 0, 1], n
            self.p = np.linalg.lstsq(A, r, rcond=None)[0]
        self.odchylky = [(b.get("popis", ""), math.hypot(*(np.array(self.en(*b["px"])) - e))) for b, e in zip(pts, E)]
        self.chyba = math.sqrt(sum(d * d for _, d in self.odchylky) / len(self.odchylky))

    def _en(self, lat, lon):
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def en(self, x, y):
        if self.typ == "afinni":
            return tuple(float(v) for v in [x, y, 1.0] @ self.M)
        a, b, c, d = self.p
        return (a * x + b * y + c, b * x - a * y + d)

    def gps(self, x, y):
        e, n = self.en(x, y)
        return (self.lat0 + n / self.ky, self.lon0 + e / self.kx)

    def meritko(self):
        """Metrů na pixel a otočení (°, kladné = proti směru hodinových ručiček)."""
        if self.typ == "afinni":
            (a, b), (c, d) = self.M[0], self.M[1]
            return math.sqrt(abs(a * (-d) - b * (-c))), math.degrees(math.atan2(b, a))
        a, b = self.p[:2]
        return math.hypot(a, b), math.degrees(math.atan2(b, a))


def narovnat(mapa, prevod, cil, max_sirka=3000):
    """Uloží ořez staré mapy narovnaný na dnešní souřadnice (sever nahoru, osy v délce/šířce) jako WebP
    s průhledným okolím a vrátí jeho hranice [[lat_jih, lon_západ], [lat_sever, lon_východ]] pro Leaflet."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    x0, y0, x1, y1 = mapa.get("orez") or [0, 0, *Image.open(os.path.join(ROOT, mapa["obraz"])).size]
    rohy = [prevod.gps(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    s, n = min(r[0] for r in rohy), max(r[0] for r in rohy)
    w, e = min(r[1] for r in rohy), max(r[1] for r in rohy)
    if os.path.exists(cil) and os.path.getmtime(cil) > max(os.path.getmtime(SOUBOR), os.path.getmtime(os.path.join(ROOT, mapa["obraz"]))):
        return [[float(s), float(w)], [float(n), float(e)]]
    src = Image.open(os.path.join(ROOT, mapa["obraz"])).convert("RGBA")
    from PIL import ImageDraw
    for x0_, y0_, x1_, y1_, dx, dy in mapa.get("zacelit", []):   # nápis na prázdném papíře → zakrýt papírem z okolí
        patch = src.crop((x0_ + dx, y0_ + dy, x1_ + dx, y1_ + dy))
        from PIL import ImageFilter
        m = Image.new("L", patch.size, 0); f = 25
        ImageDraw.Draw(m).rectangle((f, f, patch.width - f, patch.height - f), fill=255)
        src.paste(patch, (x0_, y0_), m.filter(ImageFilter.GaussianBlur(f / 2)))
    for r in mapa.get("skryt", []):          # seznamy, legendy a výřezy mimo skutečnou polohu → průhledné
        ImageDraw.Draw(src).rectangle(r, fill=(0, 0, 0, 0))
    src = src.crop((x0, y0, x1, y1))
    W = min(max_sirka, src.width)
    H = round(W * ((n - s) * prevod.ky) / ((e - w) * prevod.kx))
    # inverzní zobrazení: pixel výstupu (u, v) → GPS → pixel zdroje; převod je lineární, stačí 3 body
    import numpy as np
    def zdroj(u, v):
        lat, lon = n - v / H * (n - s), w + u / W * (e - w)
        # řešení lineární soustavy pro pixel zdroje
        return inv(lat, lon)
    ref = [(0, 0), (1000, 0), (0, 1000)]
    G = np.array([[*prevod.gps(x, y), 1] for x, y in ref]); X = np.array(ref, float)
    T = np.linalg.solve(G, X)                       # [lat, lon, 1] → [x, y]
    def inv(lat, lon):
        return np.array([lat, lon, 1.0]) @ T
    o = zdroj(0, 0); dx = (zdroj(1, 0) - o); dy = (zdroj(0, 1) - o)
    koef = (dx[0], dy[0], o[0] - x0, dx[1], dy[1], o[1] - y0)
    out = src.transform((W, H), Image.AFFINE, koef, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    os.makedirs(os.path.dirname(cil), exist_ok=True)
    out.save(cil, "WEBP", quality=80, method=4)
    return [[float(s), float(w)], [float(n), float(e)]]


def nacti():
    return json.load(open(SOUBOR, encoding="utf-8")) if os.path.exists(SOUBOR) else []


def main():
    mapy = nacti()
    if not mapy:
        sys.exit("data/stare_mapy.json neexistuje nebo je prázdný.")
    args = sys.argv[1:]
    if args and not args[0][0].isdigit():
        mapy = [m for m in mapy if m["id"] == args[0]]
        args = args[1:]
        if not mapy:
            sys.exit("Taková mapa v data/stare_mapy.json není.")
    for m in mapy:
        pr = Prevod(m)
        mer, rot = pr.meritko()
        print(f"\n{m['id']} – {m.get('misto', '')}: {len(pr.odchylky)} bodů, {pr.typ}, {mer:.3f} m/px, otočení {rot:.1f}°, "
              f"střední chyba {pr.chyba:.1f} m")
        for popis, d in pr.odchylky:
            print(f"   {d:6.1f} m  {popis}{'   ← zkontrolovat' if d > VAROVANI_M else ''}")
        for h in m.get("domy", []):
            la, lo = pr.gps(*h["px"])
            print(f"   č. {h.get('cislo', ''):>5}  {la:.6f}, {lo:.6f}  {h.get('popis', '')}")
        for s in args:
            x, y = map(float, s.split(","))
            la, lo = pr.gps(x, y)
            print(f"   {s} → {la:.6f}, {lo:.6f}  https://mapy.com/cs/zakladni?x={lo:.6f}&y={la:.6f}&z=19")


if __name__ == "__main__":
    main()
