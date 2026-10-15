"""Zet raw.json van extract_trailerbouw.py om naar data/trailerbouw.json + img/tb/.

Gebruik: python3 tools/build_trailerbouw.py <uitvoermap van extract_trailerbouw.py>
"""
import json, os, re, shutil, sys
from collections import Counter, OrderedDict

src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(src, 'raw.json')))

HOOFD = OrderedDict([('1', 'Hang- en sluitwerk'), ('2', 'Bovenbouw'), ('3', 'Onderbouw')])
groups = raw['groups']
subs = dict(raw['subgroups'])
name_to_sub = {v.lower(): k for k, v in subs.items()}
PAGE_OFFSET = 3  # pdf-pagina 4 = catalogusblad 1


def norm_sub(label):
    m = re.match(r'(\d+\.\d+\.\d+)\s+(.*)', label or '')
    if not m:
        return None, label
    code, name = m.groups()
    # CORRECTIE: catalogus heeft op blz. 349 '2.13.1 Reflectietape' (moet 2.13.2 zijn)
    if subs.get(code, name).lower() != name.lower() and name.lower() in name_to_sub:
        code = name_to_sub[name.lower()]
    subs.setdefault(code, name)
    return code, subs[code]


def title_of(b, sub_name):
    vals = []
    for t in b['tables']:
        if 'Omschrijving' in t['cols']:
            i = t['cols'].index('Omschrijving')
            vals += [r['cells'][i] for r in t['rows'] if not r['section'].lower().startswith('toebehoren') and i < len(r['cells']) and r['cells'][i]]
    # 'Scharnierbout links' + 'Scharnierbout rechts' -> 'Scharnierbout'
    clean = [re.sub(r'\s+(links|rechts|l|r|lv|rv|la|ra)$', '', v, flags=re.I) for v in vals]
    uniq = list(OrderedDict.fromkeys(clean))
    lijn_title = re.split(r'\s{2,}', b['lijn'])[0] if b['lijn'] else ''
    exploded = any('Afb.' in t['cols'] for t in b['tables'])
    if exploded and len(uniq) > 2:  # onderdelentekening (bijv. Edscha schuifdak): de productlijn is de titel
        return ('Onderdelen ' + lijn_title) if lijn_title else ('Onderdelen ' + sub_name)
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
        if lijn_title:
            return lijn_title
        return ' / '.join(uniq[:2]) + ' e.a.'
    if b['lijn']:
        return re.split(r'\s{2,}', b['lijn'])[0]
    return sub_name


products, seen, used_imgs = [], Counter(), set()
for b in raw['blocks']:
    code, sub_name = norm_sub(b['subgroep'])
    if not code:
        continue
    g = '.'.join(code.split('.')[:2])
    arts = [r['artnr'] for t in b['tables'] for r in t['rows']]
    if not arts:
        continue
    pid = arts[0]
    seen[pid] += 1
    if seen[pid] > 1:
        pid = f'{pid}-{seen[pid]}'
    lijn = re.sub(r'\s{2,}', ' · ', b['lijn'] or '')
    tables = []
    for t in b['tables']:
        # lege kolommen weglaten (bijv. kolom zonder waarden)
        keep = [i for i, c in enumerate(t['cols']) if any(i < len(r['cells']) and r['cells'][i] for r in t['rows'])]
        tables.append(dict(cols=[t['cols'][i] for i in keep],
                           rows=[dict(c=[r['cells'][i] if i < len(r['cells']) else '' for i in keep], a=r['artnr'], s=r['section']) for r in t['rows']],
                           notes=t['notes']))
    imgs = []
    for im in b['images']:
        dst = 'img/tb/' + os.path.basename(im)
        imgs.append(dst); used_imgs.add((im, dst))
    products.append(dict(id=pid, h=code.split('.')[0], g=g, s=code, lijn=lijn, title=title_of(b, sub_name),
                         img=imgs, tables=tables, page=b['page'] - PAGE_OFFSET))

# boom
tree = []
for h, hname in HOOFD.items():
    gs = []
    for g in sorted({p['g'] for p in products if p['h'] == h}, key=lambda c: [int(x) for x in c.split('.')]):
        ss = []
        for s in sorted({p['s'] for p in products if p['g'] == g}, key=lambda c: [int(x) for x in c.split('.')]):
            ps = [p for p in products if p['s'] == s]
            lijnen = list(OrderedDict.fromkeys(p['lijn'] for p in ps if p['lijn']))
            thumb = next((p['img'][0] for p in ps if p['img']), '')
            ss.append(dict(code=s, name=subs.get(s, s), count=len(ps), articles=sum(len(r['rows']) for p in ps for r in p['tables']),
                           lines=lijnen, img=thumb, page=min(p['page'] for p in ps)))
        gs.append(dict(code=g, name=groups.get(g, g), subs=ss))
    tree.append(dict(code=h, name=hname, groups=gs))

os.makedirs(os.path.join(root, 'img', 'tb'), exist_ok=True)
for a, b in used_imgs:
    shutil.copy(os.path.join(src, a), os.path.join(root, b))
out = dict(meta=dict(source='Wijlhuizen catalogus Trailerbouwdelen (2017)', pages=505), tree=tree, products=products)
json.dump(out, open(os.path.join(root, 'data', 'trailerbouw.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(products), 'producten', sum(len(r['rows']) for p in products for r in p['tables']), 'artikelregels',
      sum(len(g['subs']) for h in tree for g in h['groups']), 'subgroepen', len(used_imgs), 'afbeeldingen')
