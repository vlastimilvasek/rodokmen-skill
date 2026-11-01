#!/usr/bin/env python3
"""Připraví hotový web pro vlastní server s Apache (Plesk) do složky nasazeni/ – samostatný git repozitář,
který se odesílá do soukromého repozitáře na GitHubu a odtud ho stahuje Plesk (rozšíření Git).

Použití (z kořene projektu, po `cd web && npm run data && npm run build`):
  nasadit_plesk.py            zkopíruje web/dist do nasazeni/, přidá .htaccess s přihlášením a uloží commit
  (odeslání: cd nasazeni && git push – jen se souhlasem uživatele)

Do nasazeni/ jde jen hotový web: žádná data projektu ani odpověď na přihlašovací otázku (jen její otisk SHA-256).
Přihlášení: přihlašovací stránka uloží otisk do cookie „rodokmen“, .htaccess pustí dál jen s ní.
V Plesku musí statické soubory obsluhovat Apache (vypnout „Obsluhovat statické soubory přímo nginxem“),
jinak nginx .htaccess obejde.
"""
import os, re, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "web", "dist")
CIL = os.path.join(ROOT, "nasazeni")

HTACCESS = """# Vyrábí tools/nasadit_plesk.py – ručně neupravovat.
# Lehké přihlášení: přihlašovací stránka uloží do cookie „rodokmen“ otisk (SHA-256) odpovědi na rodinnou otázku,
# tady se porovná. Samotná odpověď tu není.
Options -Indexes
DirectoryIndex index.html
ErrorDocument 401 /prihlaseni.html
ErrorDocument 404 /404.html

<IfModule mod_headers.c>
  Header always set X-Robots-Tag "noindex, nofollow"
  <Files "prihlaseni.html">
    Header always set Cache-Control "no-store"
  </Files>
</IfModule>

RewriteEngine On
# vždy přes https
RewriteCond %{HTTPS} !=on
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
# přihlašovací a chybová stránka jsou dostupné vždy
RewriteRule ^(prihlaseni|404)\\.html$ - [L]
# bez správné cookie → 401 (Apache zobrazí přihlašovací stránku)
RewriteCond %{HTTP_COOKIE} !(^|;\\s*)rodokmen={HASH}(;|$)
RewriteRule ^ - [R=401,L]

<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType image/jpeg "access plus 30 days"
  ExpiresByType image/png "access plus 30 days"
</IfModule>
"""


def main():
    nginx = os.path.join(ROOT, "web", "nginx.conf")
    if not os.path.exists(nginx) or not os.path.exists(os.path.join(DIST, "index.html")):
        sys.exit("Nejdřív: cd web && npm run data && npm run build (s nastavenou přihlašovací odpovědí).")
    m = re.search(r'"([0-9a-f]{64})"\s+1;', open(nginx, encoding="utf-8").read())
    if not m:
        sys.exit("V web/nginx.conf není otisk odpovědi – je ve web.json vyplněná přihlašovací odpověď?")
    os.makedirs(CIL, exist_ok=True)
    for n in os.listdir(CIL):                      # smazat starý obsah kromě .git
        if n == ".git":
            continue
        p = os.path.join(CIL, n)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    for n in os.listdir(DIST):
        s, d = os.path.join(DIST, n), os.path.join(CIL, n)
        shutil.copytree(s, d) if os.path.isdir(s) else shutil.copy2(s, d)
    with open(os.path.join(CIL, ".htaccess"), "w", encoding="utf-8", newline="\n") as f:
        f.write(HTACCESS.replace("{HASH}", m.group(1)))
    with open(os.path.join(CIL, ".gitattributes"), "w", encoding="utf-8", newline="\n") as f:
        f.write("* -text\n")                       # soubory beze změn konců řádků
    if not os.path.isdir(os.path.join(CIL, ".git")):
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=CIL, check=True)
    subprocess.run(["git", "add", "-A"], cwd=CIL, check=True)
    r = subprocess.run(["git", "commit", "-q", "-m", "Aktualizace webu"], cwd=CIL)
    print("připraveno v nasazeni/" + ("" if r.returncode == 0 else " (beze změn)"))
    print("odeslání na GitHub: cd nasazeni && git push")


if __name__ == "__main__":
    main()
