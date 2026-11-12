// Data exported from the research repo by tools/export_web.py (re-run `npm run data` after changes).
import site from '../data/site.json';

export const { people, families, relatives = {}, lines, stats, issues, hypotheses, docs, config } = site;
/** Počet rodů slovem pro nadpisy („Osm rodů“). */
export const linesTitle = (n) => (['Žádný rod', 'Jeden rod', 'Dva rody', 'Tři rody', 'Čtyři rody', 'Pět rodů', 'Šest rodů', 'Sedm rodů', 'Osm rodů'][n] ?? `${n} rodů`);
export const root = people[site.root];
export const records = Object.fromEntries(site.records.map((r) => [r.key, r]));
export const recordList = site.records;
export const byK = Object.fromEntries([
  ...Object.values(people).map((p) => [p.k, p]),
  ...Object.entries(site.aliases ?? {}).map(([k, slug]) => [Number(k), people[slug]]),
]);
export const lineByK = Object.fromEntries(Object.values(lines).map((l) => [l.k, l]));
export const places = site.places ?? [];
export const oldMaps = site.oldMaps ?? [];
export const placeBySlug = Object.fromEntries(places.map((pl) => [pl.slug, pl]));
export const docByImg = Object.fromEntries((docs ?? []).map((d) => [d.img, d]));

export const href = {
  person: (slug) => `/osoba/${slug}/`,
  family: (id) => `/rodina/${id}/`,
  line: (slug) => `/rod/${slug}/`,
  record: (key) => `/zdroj/${key}/`,
  place: (slug) => `/misto/${slug}/`,
  relative: (slug) => `/pribuzny/${slug}/`,
  descent: (slug) => `/potomci/${slug}/`,
};

/** „Kateřina Tichá (* 1822)“ → jméno + roky zvlášť; u „* rok“ dáme přesnější datum narození z řadicího klíče. */
export function splitName(n, sort) {
  const m = n.match(/^(.*?)\s*\(([^()]*\d{4}[^()]*)\)\s*(\?)?$/);
  const name = m ? m[1] + (m[3] ? ' (?)' : '') : n;
  const info = m ? m[2] : '';
  const years = info && /[–-]/.test(info) ? info : birthLabel(sort) || info;
  return { name, years };
}

/** Krabička (jméno, roky, odkaz) pro příbuzného mimo linii. */
export const relBox = (r) => ({ ...splitName(r.name, r.sort), url: href.relative(r.slug), slug: r.slug, st: '', kind: 'relative' });
const personBox = (p) => ({ name: p.name, years: p.years || '', url: href.person(p.slug), slug: p.slug, st: p.st, k: p.k, kind: 'person' });

/** Odkaz z polí otec/matka/partner příbuzného (export: {kind: person|relative|text, slug, name}) → krabička. */
export function refBox(ref) {
  if (!ref) return null;
  if (ref.kind === 'person' && people[ref.slug]) return personBox(people[ref.slug]);
  if (ref.kind === 'relative' && relatives[ref.slug]) return relBox(relatives[ref.slug]);
  return { name: ref.name, years: '', url: null, st: '', kind: 'text' };
}

/** Rodiče příbuzného: výslovně zapsaní (otec/matka), jinak u sourozence rodiče předka. */
export function relativeParents(r) {
  if (r.father || r.mother) return [r.father ?? null, r.mother ?? null];
  if (r.sib && people[r.of]) {
    const a = people[r.of];
    return [a.father ? { kind: 'person', slug: a.father } : null, a.mother ? { kind: 'person', slug: a.mother } : null];
  }
  return [null, null];
}

/** Uzel rodokmenu (pro Pedigree/MobileTree): krabička + odkazy na rodiče; u předků podle Kekulého čísla. */
export function pedigreeNode(ref) {
  if (!ref) return null;
  if (ref.kind === 'person') {
    const p = people[ref.slug];
    if (!p) return null;
    const par = (kk) => (byK[kk] ? { kind: 'person', slug: byK[kk].slug } : null);
    return { box: personBox(p), kk: p.k, parents: [par(2 * p.k), par(2 * p.k + 1)] };
  }
  if (ref.kind === 'relative') {
    const r = relatives[ref.slug];
    return r ? { box: relBox(r), parents: relativeParents(r) } : null;
  }
  return { box: refBox(ref), parents: [null, null] };
}

/** Sloupce rodokmenu: [osoba], [rodiče], [prarodiče], … (null = neznámý). */
export function pedigreeCols(start, depth = 3) {
  const cols = [[pedigreeNode(start)]];
  for (let c = 0; c < depth; c++) cols.push(cols[c].flatMap((n) => (n ? n.parents.map(pedigreeNode) : [null, null])));
  return cols;
}

/** Potomci příbuzného mimo linii: jedna generace (partner + děti podle polí otec/matka ostatních příbuzných). */
export function relativeDescent(slug) {
  const r = relatives[slug];
  if (!r) return [];
  const kids = (r.children ?? []).map((s) => relatives[s]).filter(Boolean).map((c) => ({ ...relBox(c), anc: false, sort: c.sort }));
  if (!r.partner && !kids.length) return [];
  return [{ self: relBox(r), spouse: refBox(r.partner), spouseNote: r.partner ? '' : 'neznámý partner', kids, next: null }];
}

/**
 * Potomci (strom potomků) osoby: generace od osoby dolů po přímé linii až k výchozí osobě.
 * Každá generace = pár (osoba + partner) a jejich známé děti (dítě v linii + sourozenci ze SIDE),
 * chronologicky. Data obsahují jen přímou linii a sourozence, proto se rozvětvuje jen dítě v linii.
 *
 */
export function descent(slug, maxGen = Infinity) {
  const gens = [];
  const seen = new Set();
  let s = slug;
  while (s && people[s]?.ownFamily && families[people[s].ownFamily] && !seen.has(s) && gens.length < maxGen) {
    seen.add(s);
    const p = people[s];
    const f = families[p.ownFamily];
    const spouse = p.spouse ?? (p.sex === 'F' ? f.father : f.mother) ?? null;
    const spouseNote = spouse ? '' : p.sex === 'F' && f.fatherUnknown ? 'otec neuveden' : 'neznámý partner';
    const kids = [
      ...f.children.filter((c) => people[c]).map((c) => ({ anc: true, slug: c, name: people[c].name, years: people[c].years, sort: people[c].sort, url: href.person(c) })),
      ...f.side.filter((x) => x.sib).map((x) => ({ ...relBox(x), anc: false, sort: x.sort })),
    ].sort((a, b) => (a.sort ?? 99999999) - (b.sort ?? 99999999));
    const next = p.child && people[p.child] ? p.child : null;
    gens.push({ person: s, spouse, spouseNote, family: f.id, kids, next });
    s = next;
  }
  return gens;
}

/** Rozpětí let pro přehledy: [1772, 1830] → „1772–1830“, [1905, 1905] → „1905“. */
export const span = (s) => (!s ? '' : s[0] === s[1] ? String(s[0]) : `${s[0]}–${s[1]}`);

/** Sortable number from dates like "12. 5. 1811", "3/1867", "12/1790", "1797". */
export function dateKey(date) {
  const y = (date.match(/\d{4}/) || ['9999'])[0];
  const parts = date.replace(y, '').match(/\d+/g) || [];
  const [d, m] = parts.length >= 2 ? [parts[0], parts[1]] : [0, parts[0] || 0];
  return Number(y) * 10000 + Number(m) * 100 + Number(d);
}

export const genName = (g) =>
  ['výchozí osoba', 'rodiče', 'prarodiče', 'praprarodiče'][g] ?? `${g}. generace (${'pra'.repeat(g - 1)}rodiče)`;

export const statusClass = (st) => ({ doc: 'st-doc', prob: 'st-prob', fam: 'st-fam', mh: 'st-mh' })[st] ?? 'st-unk';

/** Krátký popisek narození z řadicího klíče rrrrmmdd: 18900601 → „* 1. 6. 1890“, 18920000 → „* 1892“. */
export const birthLabel = (k) => (!k || k >= 99999999 ? '' : `* ${k % 100 ? `${k % 100}. ${Math.floor(k / 100) % 100}. ` : ''}${Math.floor(k / 10000)}`);
