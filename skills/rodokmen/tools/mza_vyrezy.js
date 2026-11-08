// Přiblížené výřezy snímků z MZA (Claude in Chrome) – pro přesné čtení rejstříků a těžkých míst.
// Uloží to, co prohlížeč ukazuje při přiblížení (canvas, delší strana max. 2000 px), jako mza_<kniha>_<snímek4>_<štítek>.jpg
// do Stažených souborů. Pomalu (pauza mezi výřezy). Stránka platí ~28 min – dávky kratší.
// Použití: vložit, pak VYR.start({svazek: 5915, snimky: [456, 457], oblasti: VYR.ctvrtiny, pauza: 3})
//   oblast = [štítek, x, y, šířka, výška] jako zlomky snímku (0–1).
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const V = window.VYR = window.VYR || {};
  V.stav = V.stav || { bezi: false };
  // čtvrtiny s přesahem přes hřbet (levá strana do 0.55, pravá od 0.45)
  V.ctvrtiny = [["LH", 0, 0, 0.55, 0.52], ["LD", 0, 0.48, 0.55, 0.52], ["PH", 0.45, 0, 0.55, 0.52], ["PD", 0.45, 0.48, 0.55, 0.52]];
  async function nacteno(ms) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      if (document.hidden) { await sleep(2000); continue; }
      const it = viewer.world.getItemAt(0);
      if (it && it.getFullyLoaded()) return true;
      if (it && Date.now() - t0 > 20000 && it._tilesLoading <= 2) { V.stav.neuplne = (V.stav.neuplne || 0) + 1; return true; }   // visící dílek od serveru
      if ((Date.now() - t0) % 4000 < 300) { viewer.viewport.zoomBy(1.0005, null, true); viewer.forceRedraw(); }   // OSD po změně velikosti občas „usne“
      await sleep(300);
    }
    return false;
  }
  function velikost(w, h) {   // prohlížeč s poměrem stran oblasti, delší strana 2000 px
    const dpr = window.devicePixelRatio || 1, k = 2000 / Math.max(w, h);
    let st = document.getElementById('vyr-styl');
    if (!st) { st = document.createElement('style'); st.id = 'vyr-styl'; document.head.appendChild(st); }
    st.textContent = `#${viewer.element.id || 'openseadragon'}{position:fixed!important;left:0!important;top:0!important;width:${Math.round(w * k / dpr)}px!important;height:${Math.round(h * k / dpr)}px!important;max-height:none!important;z-index:99999!important;background:#fff!important}`;
  }
  function uloz(nazev, url) { const a = document.createElement('a'); a.href = url; a.download = nazev; document.body.appendChild(a); a.click(); a.remove(); }
  V.stop = () => { V.stav.bezi = false; };
  V.start = async ({ svazek, snimky, oblasti = V.ctvrtiny, pauza = 3 }) => {
    if (V.stav.bezi) return 'už běží';
    const m = String(viewer.tileSources[0]).match(/fcgi\/(\d{10})\//);
    const platiDo = m ? +m[1] * 1000 - 300000 : Date.now() + 23 * 60000;
    Object.assign(V.stav, { bezi: true, svazek, hotovo: [], chyba: null, obnovit: false, start: new Date().toISOString() });
    try {
      for (const sn of snimky) {
        if (!V.stav.bezi) break;
        if (Date.now() > platiDo) { V.stav.obnovit = true; break; }
        const otevreno = new Promise(r => viewer.addOnceHandler('open', r));
        viewer.goToPage(sn - 1);
        await Promise.race([otevreno, sleep(20000)]);
        await sleep(800);
        const it = viewer.world.getItemAt(0);
        if (!it) { V.stav.chyba = 'snímek ' + sn + ' se neotevřel'; break; }
        it.minPixelRatio = 0.3;
        const s = it.source, r = it.getBounds();
        for (const [tag, x, y, w, h] of oblasti) {
          velikost(w * s.width, h * s.height);
          await sleep(700);
          viewer.viewport.fitBounds(new OpenSeadragon.Rect(r.x + x * r.width, r.y + y * r.height, w * r.width, h * r.height), true);
          await sleep(1500);
          if (!await nacteno(60000)) { await sleep(20000); if (!await nacteno(60000)) { V.stav.chyba = 'snímek ' + sn + ' ' + tag + ' se nenačetl (možné omezení serveru)'; break; } }
          await sleep(800);
          uloz(`mza_${svazek}_${String(sn).padStart(4, '0')}_${tag}.jpg`, viewer.drawer.canvas.toDataURL('image/jpeg', 0.9));
          await sleep(pauza * 1000);
        }
        if (V.stav.chyba) break;
        V.stav.hotovo.push(sn);
      }
    } catch (e) { V.stav.chyba = String(e && e.message || e); }
    V.stav.bezi = false; V.stav.konec = new Date().toISOString();
    uloz(`mza_${svazek}_vyrezy_souhrn.json`, 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(V.stav)));
    return V.stav;
  };
  return 'VYR připraven';
})();
