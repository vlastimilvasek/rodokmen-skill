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
};

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
