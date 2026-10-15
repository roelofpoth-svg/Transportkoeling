"""Bouwt de generieke catalogusdata voor de onderdelenzoeker.

Gebruik: python3 tools/build_catalogi.py <map met uitvoer van extract_generiek.py per catalogus> [<trailerbouw raw-map>]

Voor elke catalogus in CATALOGI hieronder wordt <bron>/o_<bestandsnaam>/raw.json gelezen en omgezet naar
data/catalogi/<id>.json (boom + producten) en img/c/<id>/. data/catalogi.json bevat de lijst met catalogi.
De keuze van de boomniveaus per catalogus staat in LEVELS.
"""
import json, os, re, shutil, sys
from collections import Counter, OrderedDict

src = sys.argv[1]
tb_src = sys.argv[2] if len(sys.argv) > 2 else None
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CATALOGI = [
    # id, naam, bestand, korte omschrijving
    ('koelingsdelen', 'Koelingsdelen truck', '00.01.0016 - Koelingsdelen', 'Radiateurs, intercoolers, waterpompen, riemen, filters en aircodelen per merk en type truck.'),
    ('truckschadedelen', 'Truckschadedelen', 'WH Truckschadedelen_2021', 'Verlichting, spiegels, carrosseriedelen en accessoires per merk en type truck.'),
    ('scania-pgr', 'Scania P/G/R-serie', '00.01.0017 - Scania-PGR-serie', 'Onderdelen voor Scania P-, G- en R-serie: motor, koeling, remmen, cabine, carrosserie en meer.'),
    ('verlichting', 'Verlichting', '00.01.0023 - Verlichting', 'Markerings-, achter-, knipper-, werk- en koplampen voor truck en trailer.'),
    ('elektra', 'Elektra & installatie', '00.01.0028 - Elektra-en-installatie', 'Kabels, spiralen, stekkers, connectoren, zekeringen, schakelaars en installatiemateriaal.'),
    ('luchtremkoppelingen', 'Luchtremkoppelingen', 'Luchtremkoppelingen', 'Raufoss, Voss, Norgren, Legris en andere koppelingen, leidingen en luchtremdelen.'),
    ('luchtbalgen', 'Luchtbalgen', '00.01.0031 - Luchtbalgen', 'Trailer-, truck- en busbalgen met OE- en kruisverwijzingen.'),
    ('aanhanger-asdelen', 'Aanhanger- & trailerasdelen', '00.01.0018 - Aanhanger-trailerasdelen', 'Rem- en asdelen voor BPW, SAF, Meritor, Gigant, Schmitz, SMB en meer.'),
    ('voertuig-opbouw', 'Voertuig op- & aanbouwdelen', '00.01.0025 - Voertuig-op-en-aanbouwdelen', 'Koppelingen, trekogen, schotels, steunpoten, wissellaadbakpoten en toebehoren.'),
    ('laadklepdelen', 'Laadklepdelen', '00.01.0029 - Laadklepdelen_0', 'Cilinders, pompen, schakelaars en onderdelen per merk laadklep.'),
    ('bevestigingsmaterialen', 'Bevestigingsmaterialen', '00.01.0030 - Bevestigingsmaterialen', 'Bouten, schroeven, moeren, ringen, klinknagels en assortimentskoffers.'),
    ('werkplaats', 'Werkplaatsbenodigdheden', '00.01.0032 - Werkplaatsbenodigdheden', 'Smeermiddelen, onderhoudsproducten, lijmen, kitten, tapes en reiniging.'),
]


def clean(s):
    s = re.sub(r'\s+', ' ', (s or '').replace('  ', ' ')).strip(' |·-:')
    return re.sub(r'\bElectrospriralen\b', 'Electrospiralen', s)


def side_split(side):
    """'Trailer - Markeringslampen' / 'Markeringslampen - Trailer' -> ('Markeringslampen', 'Trailer')"""
    parts = [p.strip() for p in re.split(r'\s+-\s+', side or '') if p.strip()]
    app = [p for p in parts if re.fullmatch(r'(Truck|Trailer|Bus|Bestel|Algemeen|Universeel)', p, re.I)]
    rest = [p for p in parts if p not in app]
    return (rest[0] if rest else ''), (app[0] if app else '')


def levels_for(cid, b):
    t = [clean(x) for x in b['title'] if clean(x) and not re.fullmatch(r'\d+', clean(x))]
    side, sec, lijn = clean(b['side']), clean(b['section']), clean(b['lijn'])
    if cid == 'koelingsdelen':
        return [side or (t[0] if t else ''), ' '.join(t[1:]) if len(t) > 1 else ' '.join(t), sec]
    if cid == 'truckschadedelen':
        model = ' '.join(t)
        if side and model.lower().startswith(side.lower()):
            model = model[len(side):].strip()
        return [side, model, sec]
    if cid == 'scania-pgr':
        return [side.replace('(', '').replace(')', ''), sec]
    if cid == 'aanhanger-asdelen':
        return [t[0] if t else side, ' '.join(t[1:]).capitalize() if len(t) > 1 else '']
    if cid == 'verlichting':
        typ, app = side_split(side)
        return [typ or ' '.join(t), app or 'Algemeen', sec]
    if cid == 'laadklepdelen':
        return [side or (t[-1] if t else ''), sec]
    if cid in ('bevestigingsmaterialen', 'luchtbalgen'):
        return [sec or side, lijn]
    if cid in ('voertuig-opbouw', 'luchtremkoppelingen'):
        return [' '.join(t)]
    return [' '.join(t), sec]  # elektra, werkplaats


def lijn_for(cid, b):
    if cid in ('bevestigingsmaterialen', 'luchtbalgen'):
        return ''  # zit al in de boom
    return clean(b['lijn'])


def title_of(b, fallback):
    vals = []
    for t in b['tables']:
        if 'Omschrijving' in t['cols']:
            i = t['cols'].index('Omschrijving')
            vals += [r['cells'][i] for r in t['rows'] if not r['section'].lower().startswith(('toebehoren', 'onderdelen')) and i < len(r['cells']) and r['cells'][i]]
    vals = [re.split(r'\s\|\s', v)[0] for v in vals]
    clean_ = [re.sub(r'\s+(links|rechts|l|r|lv|rv|la|ra)$', '', v, flags=re.I) for v in vals]
    uniq = list(OrderedDict.fromkeys(clean_))
    lijn_title = re.split(r'\s{2,}', b['lijn'])[0] if b['lijn'] else ''
    many_afb = any('Afb.' in t['cols'] or 'Pos.' in t['cols'] or 'Positie' in t['cols'] for t in b['tables'])
    if many_afb and len(uniq) > 2:
        return lijn_title or fallback
    if uniq and len(uniq) <= 2:
        return ' / '.join(uniq)
    if uniq:
        words = [u.split() for u in uniq]
        common = []
        for ws in zip(*words):
            if len(set(w.lower() for w in ws)) == 1:
                common.append(ws[0])
            else:
                break
        if common and len(' '.join(common)) > 3:
            return ' '.join(common)
        return lijn_title or fallback
    return lijn_title or fallback


def slug(s):
    s = s.lower()
    for a, b_ in (('ä', 'a'), ('ö', 'o'), ('ü', 'u'), ('é', 'e'), ('è', 'e'), ('ë', 'e'), ('&', 'en')):
        s = s.replace(a, b_)
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:60] or 'x'


def build(cid, name, desc, products_in, level_names=None):
    """products_in: lijst dicts met path (lijst namen), lijn, title, img, tables, page. Bouwt boom + schrijft json."""
    tree = OrderedDict()  # pad-tuple -> node
    nodes = {}

    def node(path):
        key = tuple(path)
        if key not in nodes:
            pid = '/'.join(slug(p) for p in path)
            nodes[key] = dict(id=pid, name=path[-1], children=[], count=0, articles=0, img='', page=None)
            if len(path) > 1:
                parent = node(path[:-1])
                parent['children'].append(nodes[key])
            else:
                tree[key] = nodes[key]
        return nodes[key]

    products, seen, sigs = [], Counter(), set()
    for p in products_in:
        sig = (tuple(p['path']), p['title'], tuple(r['a'] for t in p['tables'] for r in t['rows']))
        if sig in sigs:
            continue  # zelfde product nogmaals (linker- en rechterpagina van een spread)
        sigs.add(sig)
        path = [x for x in p['path'] if x]
        if not path:
            path = ['Overig']
        arts = [r['a'] for t in p['tables'] for r in t['rows']]
        if not arts:
            continue
        leaf = node(path)
        pid = arts[0]
        seen[pid] += 1
        if seen[pid] > 1:
            pid = f'{pid}-{seen[pid]}'
        p = dict(p, id=pid, n=leaf['id'])
        p.pop('path', None)
        products.append(p)
        for k in range(1, len(path) + 1):
            nd = nodes[tuple(path[:k])]
            nd['count'] += 1
            nd['articles'] += len(arts)
            if not nd['img'] and p['img']:
                nd['img'] = p['img'][0]
            nd['page'] = p['page'] if nd['page'] is None else min(nd['page'], p['page']) if isinstance(p['page'], int) and isinstance(nd['page'], int) else nd['page']
    # lijnen per blad
    for nd in nodes.values():
        if not nd['children']:
            nd['lines'] = list(OrderedDict.fromkeys(p['lijn'] for p in products if p['n'] == nd['id'] and p['lijn']))
    data = dict(id=cid, name=name, desc=desc, levels=level_names or [], tree=list(tree.values()), products=products)
    os.makedirs(os.path.join(root, 'data', 'catalogi'), exist_ok=True)
    json.dump(data, open(os.path.join(root, 'data', 'catalogi', f'{cid}.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    n_art = len({r['a'] for p in products for t in p['tables'] for r in t['rows']})
    return dict(id=cid, name=name, desc=desc, products=len(products), articles=n_art, groups=len(tree),
                img=next((p['img'][0] for p in products if p['img']), ''), top=[n['name'] for n in tree.values()][:14])


def copy_img(cid, srcdir, rel):
    if not rel:
        return ''
    dst = f'img/c/{cid}/{os.path.basename(rel)}'
    full = os.path.join(root, dst)
    if not os.path.exists(full):
        os.makedirs(os.path.dirname(full), exist_ok=True)
        shutil.copy(os.path.join(srcdir, rel), full)
    return dst


index = []
for cid, name, fname, desc in CATALOGI:
    d = os.path.join(src, 'o_' + fname.replace(' ', '_'))
    raw = json.load(open(os.path.join(d, 'raw.json')))
    items = []
    for b in raw['blocks']:
        path = levels_for(cid, b)
        tables = []
        for t in b['tables']:
            keep = [i for i, c in enumerate(t['cols']) if any(i < len(r['cells']) and r['cells'][i] for r in t['rows'])]
            rows = []
            for r in t['rows']:
                row = dict(c=[r['cells'][i] if i < len(r['cells']) else '' for i in keep], a=r['artnr'], s=r['section'])
                if r.get('img'):
                    row['i'] = copy_img(cid, d, r['img'])
                rows.append(row)
            notes = []
            for n_ in t['notes']:
                for part in re.split(r'\s*»+\s*', n_):
                    part = part.strip()
                    if part and part not in notes:
                        notes.append(part)
            tables.append(dict(cols=[t['cols'][i] for i in keep], rows=rows, notes=notes))
        fallback = clean(b['lijn']) or (path[-1] if path and path[-1] else name)
        items.append(dict(path=path, lijn=lijn_for(cid, b), title=title_of(b, fallback),
                          img=[copy_img(cid, d, x) for x in b['images']], tables=tables, page=b['page']))
    # geen eigen afbeelding: neem de afbeelding over van het vorige product in dezelfde groep (zelfde of vorige bladzijde)
    last = {}
    for it in items:
        key = (tuple(it['path']), it['lijn'])
        single = sum(len(t['rows']) for t in it['tables']) <= 1
        if it['img']:
            last[key] = (it['img'], it['page'])
        elif not single and key in last and isinstance(it['page'], int) and isinstance(last[key][1], int) and 0 <= it['page'] - last[key][1] <= 1:
            it['img'] = last[key][0][:1]
    # en andersom: tabel vóór de tekening (bijv. tekening op de rechterpagina)
    nxt = {}
    for it in reversed(items):
        key = tuple(it['path'])
        single = sum(len(t['rows']) for t in it['tables']) <= 1
        if it['img']:
            nxt[key] = (it['img'], it['page'])
        elif not single and key in nxt and isinstance(it['page'], int) and isinstance(nxt[key][1], int) and 0 <= nxt[key][1] - it['page'] <= 1:
            it['img'] = nxt[key][0][:1]
    index.append(build(cid, name, desc, items))
    print(f'{cid:24} {index[-1]["products"]:5} producten {index[-1]["articles"]:6} artikelnummers {index[-1]["groups"]:3} hoofdgroepen')

# Trailerbouwdelen (eigen uitlezer) in hetzelfde formaat
tb = json.load(open(os.path.join(root, 'data', 'trailerbouw.json')))
items = []
names = {}
for h in tb['tree']:
    names[h['code']] = f"{h['code']} {h['name']}"
    for g in h['groups']:
        names[g['code']] = f"{g['code']} {g['name']}"
        for s_ in g['subs']:
            names[s_['code']] = f"{s_['code']} {s_['name']}"
for p in tb['products']:
    items.append(dict(path=[names[p['h']], names[p['g']], names[p['s']]], lijn=p['lijn'], title=p['title'], img=p['img'], tables=p['tables'], page=p['page'], code=p['s']))
tbi = build('trailerbouw', 'Trailerbouwdelen', 'Hang- en sluitwerk, bovenbouw en onderbouw: scharnieren, sluitingen, ladingzekering, schuifzeilen en -daken, rongen, markering, spatschermen, kisten en meer.', items)
index.insert(0, tbi)
print(f'trailerbouw              {tbi["products"]:5} producten {tbi["articles"]:6} artikelnummers')
json.dump(index, open(os.path.join(root, 'data', 'catalogi.json'), 'w'), ensure_ascii=False, indent=1)
