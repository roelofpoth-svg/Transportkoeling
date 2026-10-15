"""Zet de ruwe PDF-extractie (raw.json) om naar data/catalogus.json voor de selectietool.

Gebruik: python3 tools/build_data.py <uitvoermap van extract_catalogus.py>
Handmatige correcties op de catalogus staan in dit bestand (zoek op 'CORRECTIE').
"""
import json, re, sys, os, shutil

src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(src, 'raw.json')))

LOGO_BRANDS = ['MANN-FILTER', 'WIX Filters', 'Optibelt', 'Gates', 'Donaldson', 'Schmitz Cargobull']

MAKES = {
    'carrier': 'Carrier Transicold',
    'thermoking': 'Thermo King',
    'schmitz': 'Schmitz Cargobull',
}


def make_of(text):
    t = text.lower()
    res = []
    if 'carrier' in t:
        res.append('carrier')
    if 'thermo' in t:
        res.append('thermoking')
    if 'schmitz' in t:
        res.append('schmitz')
    return res


def canon(model, make):
    m = re.sub(r'\s+', ' ', model.strip().rstrip('.,'))
    if make == 'carrier':
        m = m.upper().replace('CITY', 'City')
        m = re.sub(r'(\d)MT\b', r'\1 MT', m)
        m = re.sub(r'(\d)U(MT)?\b', lambda x: x.group(1) + ' U' + (' MT' if x.group(2) else ''), m)
    elif make == 'thermoking':
        m = re.sub(r'^(SLXe|SLX|SLe|SL|MD|TS|T|B|V)[ -]?(\d)', r'\1-\2', m)
        m = re.sub(r'^(SLXe|SLX|SLe|SL|TS)[ -]?Spectrum', r'\1-Spectrum', m, flags=re.I)
        m = m.replace('SPECTRUM', 'Spectrum')
        m = re.sub(r'(SL|SLX)-Spectrum', r'\1-Spectrum', m)
        m = re.sub(r'(\d)R Spectrum', r'\1R Spectrum', m)
    return m


def key(model):
    return re.sub(r'[^a-z0-9]', '', model.lower())


def series_of(model, make):
    if make == 'carrier':
        return model.split()[0]
    if make == 'schmitz':
        return 'T.KM'
    m = re.match(r'^(SLXe|SLX|SLe|SL|MD|TS|T|B|V)-', model)
    s = m.group(1) if m else model.split('-')[0]
    return {'SLXe': 'SLX', 'SLe': 'SL', 'T': 'T-serie', 'TS': 'TS', 'B': 'B-serie', 'V': 'V-serie'}.get(s, s)


QUAL_RE = re.compile(r'\s+(?=(vanaf|tot|bouwjaar|\(|220V))', re.I)


def parse_fits(text, make):
    """'MAXIMA 1000, MAXIMA 1200 & MAXIMA 1300 vanaf serienummer X' -> modellen + voorwaarde."""
    text = re.sub(r'^(O\.a\. )?(geschikt voor|t\.b\.v\.):\s*', '', text.strip(), flags=re.I)
    cond = ''
    m = QUAL_RE.search(text)
    if m:
        text, cond = text[:m.start()], text[m.start():].strip()
    parts = [p for p in re.split(r',\s*|\s+&\s+', text) if p.strip()]
    return [canon(p, make) for p in parts], cond


models = {}  # key -> model


def add_model(name, make):
    k = make + ':' + key(name)
    if k not in models:
        models[k] = dict(id=re.sub(r'[^a-z0-9]+', '-', (make + '-' + name).lower()).strip('-'), name=name, make=make,
                         series=series_of(name, make))
    return models[k]['id']


# ---------- pakketten ----------
packages = []
for p in raw['packages']:
    make_txt = next(s for s in p['specs'] if s.lower().startswith('t.b.v.'))
    make = make_of(make_txt)[0]
    fits_txt = next(s for s in p['specs'] if s is not make_txt)
    names, cond = parse_fits(fits_txt, make)
    if make == 'schmitz':  # CORRECTIE: 'T.KM ONE R404A, R432A MT-2Kammer & R452A' = één model in varianten
        names, cond = ['T.KM ONE'], 'o.a. R404A, R432A MT-2Kammer & R452A'
    fits = [dict(model=add_model(n, make), condition=cond) for n in names]
    items = [dict(artnr=i['artnr'], name=i['name'], optional=i['section'] == 'optie',
                  brand=LOGO_BRANDS[i['logo']] if i['logo'] is not None else '', img=i['thumb']) for i in p['items']]
    packages.append(dict(id=p['art'], artnr=p['art'], type=p['title'], make=make, fits=fits, fitsText=fits_txt.split(':', 1)[1].strip(),
                         items=items, img=p['photo'], page=p['page']))
# CORRECTIE: 61.01.0038 en 61.01.0039 hebben dezelfde omschrijving; verschil zit in het luchtfilter
for pk in packages:
    if pk['artnr'] == '61.01.0038':
        pk['note'] = 'Met luchtfilter 46.822686 (Mann). Uitvoering met Donaldson-luchtfilter 46.782868: zie 61.01.0039.'
    if pk['artnr'] == '61.01.0039':
        pk['note'] = 'Met luchtfilter 46.782868 (Donaldson). Uitvoering met luchtfilter 46.822686: zie 61.01.0038.'

# ---------- losse onderdelen ----------
CATS = [
    ('filters', 'Filters', r'filter(?! droger)|luchtfilterhuis|slang elleboog'),
    ('riemen', 'Riemen & spanners', r'riem|spanrol|riemspanner'),
    ('koppelingen', 'Koppelingen', r'centrifugaal|reparatie set'),
    ('elektrisch', 'Elektrisch', r'startmotor|dynamo|magneetspoel|stuurunit'),
    ('brandstof', 'Brandstofsysteem & tanks', r'pomp|tank|tankdop|tankbeugel|tanksteun|tankmeter|aftapplug|dichtstop'),
    ('accus', "Accu's", r'^accu'),
    ('koeltechniek', 'Koeltechniek & airco', r'filter droger|dichtingsring|koudemiddel|compressorolie|uv-vloeistof|airco|snelkoppeling r134a|vulslangen|snelkoppelingen'),
    ('meetgereedschap', 'Gereedschap & meetapparatuur', r'gereedschap|lamp|thermometer|lekzoeker|uv-bril'),
    ('pneumatiek', 'Snelinsteekkoppelingen', r'snelinsteek|blindplug|vergrendelclip|insteeknippel'),
    ('gordijnen', 'Flappengordijnen', r'flappengordijn|^rail$'),
    ('kleding', 'Werkkleding & bescherming', r'muts|handschoen|sokken|jas|overall|huidbeschermer'),
    ('overig', 'Overig', r'.'),
]


def cat_of(title):
    t = title.lower()
    for cid, _, rx in CATS:
        if re.search(rx, t):
            return cid


parts, seen = [], {}
for p in raw['products']:
    specs, makes, fits, rel = [], [], [], []
    for s in p['specs']:
        low = s.lower()
        if low.startswith('t.b.v.') or low.startswith('t.b.v '):
            val = s.split(':', 1)[1].strip() if ':' in s else s[6:].strip()
            arts = re.findall(r'\b\d{2}\.\d{2}\.\d{4}\b', val)
            mk = make_of(val)
            if arts and not mk:
                rel += arts
            if mk:
                makes += mk
            if re.search(r'maxima', low):  # CORRECTIE: 'Carrier Maxima'
                fits += [dict(model=add_model(n, 'carrier'), condition='') for n in ['MAXIMA 1000', 'MAXIMA 1200', 'MAXIMA 1200 MT', 'MAXIMA 1300', 'MAXIMA 1300 MT']]
            if re.search(r'vector 1850/1950', low):  # CORRECTIE: 'Carrier Vector 1850/1950'
                fits += [dict(model=add_model(n, 'carrier'), condition='') for n in ['VECTOR 1850', 'VECTOR 1950']]
        if re.match(r'^(o\.a\. )?geschikt voor:', low) and 'biodiesel' not in low and not re.search(r'r134a|formeergas', low):
            mk = makes[0] if makes else 'thermoking'
            if mk == 'schmitz':
                fits.append(dict(model=add_model('T.KM ONE', 'schmitz'), condition='o.a. R404A, R432A MT-2Kammer & R452A'))
            else:
                names, cond = parse_fits(s, mk)
                for n in names:
                    nmk = 'carrier' if re.match(r'(MAXIMA|VECTOR|SUPRA)', n, re.I) else ('thermoking' if 'thermoking' in makes else mk)
                    fits.append(dict(model=add_model(canon(n, nmk), nmk), condition=cond))
        specs.append(s)
    makes = sorted(set(makes))
    variants = [dict(artnr=v['artnr'], label=v['label'] or '', note=v['note'] or '') for v in p['variants']]
    title = p['title']
    # CORRECTIES per artikel
    if variants[0]['artnr'] == '75.AT7040':
        variants[0]['label'], variants[1]['label'] = 'Automotive Tools', 'Hazet'
    if variants[0]['artnr'] == '51.26.0018' and variants[0]['label']:
        variants[0]['note'], variants[0]['label'] = 'i.c.m. rail 51.26.0021', ''
    if variants[0]['artnr'].endswith('.maat'):
        variants[0]['artnr'] = variants[0]['artnr'][:-5]
        variants[0]['note'] = 'Artikelnummer aanvullen met de maat'
    pid = variants[0]['artnr']
    if pid in seen:
        seen[pid] += 1; pid = f'{pid}-{seen[pid]}'
    else:
        seen[pid] = 1
    parts.append(dict(id=pid, title=title, category=cat_of(title), makes=makes, fits=fits, related=rel, specs=specs,
                      variants=variants, img=p['photo'], extraImgs=p.get('extra', []), page=p['page']))

# 'T.b.v.: 61.02.0001' -> merk overnemen van het gerelateerde artikel
by_art = {v['artnr']: q for q in parts for v in q['variants']}
for q in parts:
    if not q['makes'] and q['related']:
        mk = set()
        for a in q['related']:
            if a in by_art:
                mk |= set(by_art[a]['makes'])
        q['makes'] = sorted(mk)

# Merk bij losse onderdelen afleiden uit de pakketten waarin ze zitten (V-riemen, filters)
in_pkgs = {}
for pk in packages:
    for it in pk['items']:
        in_pkgs.setdefault(it['artnr'], []).append(pk['id'])

# ---------- koudemiddeltabel ----------
import pymupdf  # noqa: E402  (alleen voor deze ene pagina)
refrigerant = []
txt = open(os.path.join(src, 'p71.txt')).read() if os.path.exists(os.path.join(src, 'p71.txt')) else ''
for line in txt.splitlines():
    for m in re.finditer(r'(\S[\w\- /.]*?)\s{2,}(R\d+\w*)\s+(\d+,\d+)', line):
        refrigerant.append(dict(type=m.group(1).strip(), refrigerant=m.group(2), kg=m.group(3)))
half = None
for i, r in enumerate(refrigerant):
    pass
# links = Thermo King, rechts = Carrier (op volgorde per regel: TK eerst)
tk, ca = [], []
for line in txt.splitlines():
    ms = list(re.finditer(r'(\S[\w\- /.]*?)\s{2,}(R\d+\w*)\s+(\d+,\d+)', line))
    if not ms:
        continue
    for m in ms:
        row = dict(type=m.group(1).strip(), refrigerant=m.group(2), kg=m.group(3))
        (tk if m.start() < 40 else ca).append(row)
for r in tk:
    r['make'] = 'thermoking'; r['type'] = canon(r['type'], 'thermoking')
for r in ca:
    r['make'] = 'carrier'; r['type'] = canon(r['type'], 'carrier')
refrigerant = tk + ca
for r in refrigerant:
    k = r['make'] + ':' + key(r['type'])
    if k in models:
        models[k].setdefault('refrigerant', []).append(dict(refrigerant=r['refrigerant'], kg=r['kg']))

# ---------- afbeeldingen kopiëren ----------
img_out = os.path.join(root, 'img')
os.makedirs(img_out, exist_ok=True)
used = set()
for pk in packages:
    used.add(pk['img']); used |= {i['img'] for i in pk['items']}
for q in parts:
    used.add(q['img']); used |= set(q['extraImgs'])
for u in used:
    if u:
        shutil.copy(os.path.join(src, u), os.path.join(root, u))

out = dict(
    meta=dict(source='Wijlhuizen catalogus Transportkoeling, editie 48', generated='automatisch uit PDF + correcties in tools/build_data.py'),
    makes=[dict(id=k, name=v) for k, v in MAKES.items()],
    categories=[dict(id=c, name=n) for c, n, _ in CATS],
    models=sorted(models.values(), key=lambda m: (m['make'], m['series'], [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', m['name'])])),
    packages=packages,
    parts=parts,
    refrigerant=refrigerant,
)
json.dump(out, open(os.path.join(root, 'data', 'catalogus.json'), 'w'), ensure_ascii=False, indent=1)
print(len(out['models']), 'types,', len(packages), 'pakketten,', len(parts), 'onderdelen,', len(refrigerant), 'koudemiddelregels,', len(used), 'afbeeldingen')
