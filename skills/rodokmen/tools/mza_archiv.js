// Archiv snímků z MZA Acta Publica – ukládání ve stránce prohlížeče (Claude in Chrome).
// Jen „standardními prostředky prohlížeče“, jak dovoluje nápověda MZA: snímek, který prohlížeč
// OpenSeadragon na stránce sám načetl, se uloží jako obrázek s delší stranou nejvýš 2000 px.
// Žádné přímé dotazy na iipsrv, žádné obcházení ochrany. Pomalu (výchozí pauza 6 s mezi snímky).
//
// Použití (na stránce matrika/detail/<id>, po načtení):
//   1. vložit celý tento soubor přes javascript_tool
//   2. ARCH.start({svazek: 17547, od: 1, do: 111, pauza: 6})   // do = počet snímků, výchozí všechny
//   3. průběh: ARCH.stav   (hotovo / chyba / bezi, posledni, ulozeno)
//   4. zastavit: ARCH.stop()
// Soubory padají do složky Stažené soubory jako mza_<svazek>_<snimek4>.jpg;
// `python -I -X utf8 tools/archiv_snimku.py zarad` je přesune do archiv/mza/<svazek>/.
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const MAX = 2000;
  const A = window.ARCH = window.ARCH || {};
  A.stav = A.stav || { bezi: false };

  async function nacteno(timeoutMs) {
    let t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      if (document.hidden) { await skryto(); t0 = Date.now(); }
      const it = viewer.world.getItemAt(0);
      if (it && it.getFullyLoaded && it.getFullyLoaded()) return true;
      await sleep(300);
    }
    return false;
  }

  // Skrytá karta (jiná karta v okně, minimalizované/zakryté okno, zamčená obrazovka) nic nekreslí –
  // počkat, až bude zase vidět; nepočítat to jako chybu serveru.
  async function skryto() {
    if (!document.hidden) return;
    A.stav.zprava = 'karta MZA není vidět – čekám (okno nechat vpředu, nezamykat obrazovku)';
    A.stav.skryto = (A.stav.skryto || 0) + 1;
    while (document.hidden) await sleep(2000);
    A.stav.zprava = '';
    await sleep(1500);
  }

  function nastavVelikost() {
    const s = viewer.world.getItemAt(0).source, dpr = window.devicePixelRatio || 1;
    const k = MAX / Math.max(s.width, s.height);
    const w = Math.round(Math.min(s.width, s.width * k) / dpr), h = Math.round(Math.min(s.height, s.height * k) / dpr);
    // stránka MZA si výšku prohlížeče sama přenastavuje – proto pravidlo s !important (přebije inline styl)
    let st = document.getElementById('arch-styl');
    if (!st) { st = document.createElement('style'); st.id = 'arch-styl'; document.head.appendChild(st); }
    st.textContent = `#${viewer.element.id || 'openseadragon'}{position:fixed!important;left:0!important;top:0!important;width:${w}px!important;height:${h}px!important;max-height:none!important;z-index:99999!important;background:#fff!important}`;
    viewer.forceResize && viewer.forceResize();
    viewer.viewport.goHome(true);
  }

  function uloz(nazev, dataUrl) {
    const a = document.createElement('a');
    a.href = dataUrl; a.download = nazev;
    document.body.appendChild(a); a.click(); a.remove();
  }

  A.stop = () => { A.stav.bezi = false; A.stav.zprava = 'zastaveno uživatelem'; };

  A.start = async ({ svazek, od = 1, do: doS, pauza = 6 } = {}) => {
    if (A.stav.bezi) return 'už běží';
    if (!svazek) return 'chybí svazek (číslo knihy)';
    const n = viewer.tileSources.length;
    // přístup ke snímkům platí ~30 min od načtení stránky (čas v adrese dlaždic) – včas skončit, stránku obnovit a navázat
    const m = String(viewer.tileSources[0]).match(/fcgi\/(\d{10})\//);
    const platiDo = m ? +m[1] * 1000 - 300000 : Date.now() + 23 * 60000;   // stránka se sama obnoví ~2 min před vypršením – 5 min rezerva
    doS = Math.min(doS || n, n);
    let chyby = 0, selhaneDlazdice = 0; const velikosti = [];
    const h = () => { selhaneDlazdice++; };
    viewer.addHandler('tile-load-failed', h);
    Object.assign(A.stav, { skryto: 0, obnovit: false, bezi: true, svazek, od, do: doS, posledni: null, ulozeno: 0, chyba: null, zprava: '', start: new Date().toISOString() });
    try {
      for (let sn = od; sn <= doS && A.stav.bezi; sn++) {
        if (Date.now() > platiDo) { A.stav.zprava = 'vyprší platnost stránky – obnovit stránku a pokračovat od snímku ' + sn; A.stav.obnovit = true; break; }
        await skryto();
        selhaneDlazdice = 0;
        const otevreno = new Promise(r => viewer.addOnceHandler('open', r));
        viewer.goToPage(sn - 1);
        await Promise.race([otevreno, sleep(20000)]);
        await sleep(800);
        if (!viewer.world.getItemAt(0)) { chyby++; A.stav.zprava = `snímek ${sn}: neotevřel se`; if (chyby >= 2) { A.stav.chyba = 'snímek se neotevírá – KONEC'; break; } await sleep(60000); sn--; continue; }
        viewer.world.getItemAt(0).minPixelRatio = 0.3;   // nižší = ostřejší (výchozí 0.5 bere u 2000 px občas hrubší úroveň dlaždic)
        nastavVelikost();
        await sleep(1500);                       // po změně velikosti se teprve začnou nahrávat ostré dlaždice
        const ok = await nacteno(30000);
        if ((!ok || selhaneDlazdice > 3) && document.hidden) { sn--; continue; }   // skryla se během načítání – zkusit znovu
        if (!ok || selhaneDlazdice > 3) {
          chyby++;
          A.stav.zprava = `snímek ${sn}: nenačten (selhané dlaždice ${selhaneDlazdice})`;
          if (chyby >= 2) { A.stav.chyba = 'opakovaně se nenačítá – možná omezení serveru (429) nebo kontrola robota; KONEC'; break; }
          await sleep(60000); sn--; continue;   // jednou počkat minutu a zkusit znovu
        }
        chyby = 0;
        await sleep(1000);
        await nacteno(15000);
        const cv = viewer.drawer.canvas, s0 = viewer.world.getItemAt(0).source;
        if (Math.abs(cv.width / cv.height - s0.width / s0.height) > 0.03) { nastavVelikost(); await sleep(2500); await nacteno(15000); }
        let url = cv.toDataURL('image/jpeg', 0.88);
        // kontrola kvality: rozmazaný snímek má výrazně menší JPEG než předchozí – jednou počkat a zachytit znovu
        if (velikosti.length >= 3) {
          const med = [...velikosti].sort((a, b) => a - b)[velikosti.length >> 1];
          if (url.length < 0.55 * med) { await sleep(4000); await nacteno(15000); url = viewer.drawer.canvas.toDataURL('image/jpeg', 0.88); A.stav.zprava = `snímek ${sn}: zachycen znovu (kvalita)`; }
        }
        velikosti.push(url.length); if (velikosti.length > 15) velikosti.shift();
        uloz(`mza_${svazek}_${String(sn).padStart(4, '0')}.jpg`, url);
        A.stav.posledni = sn; A.stav.ulozeno++;
        await sleep(pauza * 1000);
      }
    } catch (e) {
      A.stav.chyba = String(e && e.message || e);
    } finally {
      viewer.removeHandler('tile-load-failed', h);
      A.stav.bezi = false; A.stav.konec = new Date().toISOString();
      A.stav.hotovo = A.stav.posledni === doS;
      A.stav.snimku = n;
      // souhrn pro archiv_snimku.py (počet snímků knihy, kam se došlo, případná chyba)
      uloz(`mza_${svazek}_souhrn.json`, 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify({ ...A.stav, detail: location.pathname })));
    }
    return A.stav;
  };
  return 'ARCH připraven';
})();
