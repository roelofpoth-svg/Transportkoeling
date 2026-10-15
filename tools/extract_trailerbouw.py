"""Haalt alle producten uit de Wijlhuizen catalogus Trailerbouwdelen (PDF, 2017).

Gebruik: python3 tools/extract_trailerbouw.py <catalogus.pdf> <uitvoermap>
Schrijft <uitvoermap>/raw.json en afbeeldingen naar <uitvoermap>/img/.

Opbouw van een catalogusblad:
  blauwe kop (hoofdgroep) · rode balk "1.1.1 Bordscharnieren" (subgroep) · zijtab "1.1 Scharnieren" (groep)
  optioneel een smalle blauwe balk met een productlijn ("Edscha Ultraline II  vanaf 2009")
  blokken: foto (+ maattekening) met rechts of eronder een of meer tabellen
  (rode kolomkoppen, rijen, blauwe artikelnummers), "Toebehoren:" en opmerkingen ("» ...").
"""
import json, os, re, sys
import pymupdf
from PIL import Image

RED = {0xE32528, 0xE02528, 0xED2024}
BLUE = 0x008CD1
WHITE = 0xFFFFFF
ART_RE = re.compile(r'^\d{2}\.[0-9A-Z][0-9A-Z.\-/ ]{2,}$', re.I)
TOP, BOTTOM = 92, 792
MAX_IMG = 560

pdf, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'img'), exist_ok=True)
doc = pymupdf.open(pdf)


def cells_of(page):
    """Tekststukken (spans op één regel die aan elkaar grenzen) met positie en opmaak."""
    res = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            if l['dir'] != (1.0, 0.0):
                continue  # verticale zijtab-tekst
            cur = None
            for s in l['spans']:
                t = s['text'].replace('\t', ' ')
                if not t.strip():
                    if cur:
                        cur['gap'] = True
                    continue
                if cur and s['color'] == cur['color'] and abs(s['size'] - cur['size']) < .5 and s['bbox'][0] - cur['x1'] < 6:
                    cur['text'] += ('' if cur['text'].endswith(' ') else ' ') + t.strip() if cur.get('gap') or s['bbox'][0] - cur['x1'] > 1.5 else t
                    cur['x1'] = s['bbox'][2]; cur.pop('gap', None)
                    continue
                if cur:
                    res.append(cur)
                cur = dict(x=s['bbox'][0], y=s['bbox'][1], x1=s['bbox'][2], y1=s['bbox'][3], size=round(s['size'], 1),
                           color=s['color'], bold='Bold' in s['font'], text=t)
            if cur:
                res.append(cur)
    for c in res:
        c['text'] = re.sub(r'\s+', ' ', c['text']).strip()
        c.pop('gap', None)
    return [c for c in res if c['text']]


def save_xref(xref, page, bbox):
    name = f'x{xref}.webp'
    path = os.path.join(out, 'img', name)
    if os.path.exists(path):
        return 'img/' + name
    try:
        info = doc.extract_image(xref)
        pix = pymupdf.Pixmap(doc, xref)
        if pix.colorspace and pix.colorspace.n == 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.n - pix.alpha == 1:
            img = Image.frombytes('L', (pix.width, pix.height), pix.samples if not pix.alpha else pymupdf.Pixmap(pix, 0).samples).convert('RGB')
        else:
            img = Image.frombytes('RGBA' if pix.alpha else 'RGB', (pix.width, pix.height), pix.samples)
        if info.get('smask'):
            m = pymupdf.Pixmap(doc, info['smask'])
            mask = Image.frombytes('L', (m.width, m.height), m.samples).resize(img.size)
            bg = Image.new('RGB', img.size, 'white'); bg.paste(img.convert('RGB'), mask=mask); img = bg
        elif img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, 'white'); bg.paste(img, mask=img.split()[3]); img = bg
    except Exception:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), clip=bbox, alpha=False)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    img.thumbnail((MAX_IMG, MAX_IMG))
    img.save(path, 'WEBP', quality=74, method=5)
    return 'img/' + name


def rows_by_y(items, tol=2.5):
    rows = []
    for c in sorted(items, key=lambda c: (c['y'], c['x'])):
        if rows and abs(rows[-1][0]['y'] - c['y']) < tol:
            rows[-1].append(c)
        else:
            rows.append([c])
    return [sorted(r, key=lambda c: c['x']) for r in rows]


state = dict(hoofdgroep='', groep='', subgroep='', lijn='')
blocks = []
toc_groups = {}
toc_subs = {}

for pno in range(len(doc)):
    page = doc[pno]
    P = pno + 1
    cells = cells_of(page)

    # inhoudsopgave: groepnamen (rode balken "1.1 Scharnieren")
    if P in (2, 3):
        for r in rows_by_y([c for c in cells if c['color'] == WHITE and c['size'] < 11]):
            for a, b in zip(r, r[1:]):
                if re.fullmatch(r'\d+\.\d+', a['text']) and not re.fullmatch(r'[\d.]+', b['text']):
                    toc_groups[a['text']] = b['text']
        for r in rows_by_y([c for c in cells if c['color'] in RED and c['bold']]):
            for a in r:
                if re.fullmatch(r'\d+\.\d+\.\d+', a['text']):
                    nxt = [c for c in cells if abs(c['y'] - a['y']) < 3 and a['x'] < c['x'] < a['x'] + 120 and c['color'] not in RED]
                    if nxt:
                        toc_subs[a['text']] = re.sub(r'\s*\.{2,}.*$', '', nxt[0]['text']).strip()
        continue

    # koppen
    for c in cells:
        if c['color'] == WHITE and c['size'] >= 20 and c['y'] < 60:
            state['hoofdgroep'] = c['text']
        if c['color'] == WHITE and c['size'] >= 11.5 and re.fullmatch(r'\d+\.\d+', c['text']):
            state['groep'] = c['text']
    sub_heads = []  # (y, code, naam)
    for r in rows_by_y([c for c in cells if c['color'] == WHITE and 9.5 <= c['size'] <= 10.5]):
        for a, b in zip(r, r[1:]):
            if re.fullmatch(r'\d+\.\d+\.\d+', a['text']) and not re.fullmatch(r'[\d.]+', b['text']):
                sub_heads.append((r[0]['y'], a['text'], b['text'])); break
    # productlijnbalken: blauwe gevulde rechthoeken, tekst = witte 9pt-tekst erin
    bars = []
    for dr in page.get_drawings():
        r, f = dr['rect'], dr.get('fill')
        if f and 8 < r.height < 22 and r.width > 100 and TOP < r.y0 < BOTTOM and f[2] > .7 and f[0] < .2 and f[1] < .7:
            txt = [c for c in cells if c['color'] == WHITE and r.x0 - 2 <= c['x'] <= r.x1 and r.y0 - 2 <= c['y'] <= r.y1]
            if txt:
                bars.append((r.y0, r.x0, r.x1, '  '.join(c['text'] for c in sorted(txt, key=lambda c: c['x']))))
    line_heads = [(y, t) for y, _, _, t in bars]

    body = [c for c in cells if TOP < c['y'] < BOTTOM and c['size'] >= 7.5 and c['color'] != WHITE
            and not (c['size'] >= 11.5)]
    is_art_head = lambda c: re.match(r'(Artikel|Art\.)', c['text'], re.I)
    headers = []
    for r in rows_by_y([c for c in body if c['color'] in RED and c['bold'] and c['size'] < 8.6]):
        seg = []
        for k, c in enumerate(r):  # tabellen naast elkaar: na de 'Artikelnummer'-kolom(men) begint een nieuwe tabel
            seg.append(c)
            if is_art_head(c) and not (k + 1 < len(r) and is_art_head(r[k + 1])):
                headers.append(seg); seg = []
    # tegels: rode titel met direct eronder een artikelnummer (geen tabelkop)
    head_cells = {id(c) for h in headers for c in h}
    tiles = []
    for c in body:
        if c['color'] in RED and c['bold'] and 7.5 <= c['size'] <= 10.5 and id(c) not in head_cells and not c['text'].endswith(':'):
            below = [a for a in body if a['color'] == BLUE and ART_RE.match(a['text']) and abs(a['x'] - c['x']) < 4 and 8 < a['y'] - c['y'] < 30]
            if below:
                tiles.append((c, below[0]))

    tables = []
    for i, h in enumerate(headers):
        hx0 = h[0]['x'] - 6
        art_col = next(c for c in h if is_art_head(c))
        right = [g[0]['x'] for g in headers if abs(g[0]['y'] - h[0]['y']) < 3 and g[0]['x'] > h[0]['x'] + 5]
        hx1 = min([art_col['x1'] + 75] + [x - 4 for x in right])
        # grens: volgende kop in dezelfde kolom, of een productlijnbalk
        nxt = [g[0]['y'] for g in headers if g is not h and g[0]['y'] > h[0]['y'] + 3 and g[0]['x'] < art_col['x1'] - 5 and max(c['x1'] for c in g) > hx0 + 10]
        nxt += [y for y, bx0, bx1, _ in bars if y > h[0]['y'] and bx0 < art_col['x1'] - 5 and bx1 > hx0 + 10] + [y for y, _, _ in sub_heads if y > h[0]['y']]
        ylim = min(nxt) - 2 if nxt else BOTTOM
        cols = [(c['x'] - 3, c['text']) for c in h if not is_art_head(c) or c is art_col]
        mine = [c for c in body if h[0]['y'] + 3 < c['y'] < ylim and hx0 <= c['x'] <= hx1 and c['size'] >= 8.5]
        rows, notes, section, last_y = [], [], '', h[0]['y']
        for r in rows_by_y(mine):
            if r[0]['y'] - last_y > 34 and rows:
                break  # te grote witruimte: ander blok
            last_y = r[0]['y']
            txt = ' '.join(c['text'] for c in r)
            if r[0]['color'] in RED and r[0]['bold']:
                section = txt.rstrip(':'); continue
            arts = [c for c in r if c['color'] == BLUE and ART_RE.match(c['text']) and c['x'] >= art_col['x'] - 15]
            if txt.startswith('»'):
                notes.append(txt.lstrip('» ').strip()); continue
            if arts:
                vals = [''] * len(cols)
                for c in r:
                    if c in arts:
                        continue
                    k = max([j for j, (x, _) in enumerate(cols) if x <= c['x'] + 2] or [0])
                    vals[k] = (vals[k] + ' ' + c['text']).strip()
                art_heads = [c for c in h if is_art_head(c)]
                for a in arts:
                    var = ''
                    if len(art_heads) > 1:  # bijv. 'Artikelnummer A' / 'Artikelnummer B'
                        hh = min(art_heads, key=lambda c: abs(c['x'] - a['x']))
                        var = re.sub(r'^(Artikelnummer|Art\.?\s*nr\.?)\s*', '', hh['text'], flags=re.I)
                    rows.append(dict(cells=vals, artnr=a['text'].replace(' ', ''), section=(section + ' ' + var).strip(), y=r[0]['y']))
            elif rows and r[0]['y'] - rows[-1]['y'] < 13 and not notes:
                for c in r:  # vervolgregel van de vorige rij
                    k = max([j for j, (x, _) in enumerate(cols) if x <= c['x'] + 2] or [0])
                    rows[-1]['cells'][k] = (rows[-1]['cells'][k] + ' ' + c['text']).strip()
            else:
                notes.append(txt)
        if rows:
            tables.append(dict(y=h[0]['y'], x0=hx0, x1=hx1, cols=[t for _, t in cols], rows=rows, notes=notes,
                               ybottom=max([last_y, rows[-1]['y']])))

    for c, a in tiles:
        right = [t[0]['x'] for t in tiles if abs(t[0]['y'] - c['y']) < 3 and t[0]['x'] > c['x'] + 5]
        x1 = min(right) - 4 if right else 580
        notes, last = [], a['y']
        for r in rows_by_y([n for n in body if c['x'] - 3 <= n['x'] < x1 and n['y'] > a['y'] + 3 and n['color'] != BLUE and n['size'] >= 8.5]):
            if r[0]['y'] - last > 16 or (r[0]['color'] in RED):
                break
            last = r[0]['y']; txt = ' '.join(n['text'] for n in r)
            if txt.startswith('»') or not notes:
                notes.append(txt.lstrip('» ').strip())
            else:
                notes[-1] += ' ' + txt
        tables.append(dict(y=c['y'], x0=c['x'] - 6, x1=x1, cols=['Omschrijving'], tile=True,
                           rows=[dict(cells=[c['text']], artnr=a['text'].replace(' ', ''), section='', y=a['y'])], notes=notes, ybottom=last))

    used_y = [(t['x0'], t['x1'], t['y'], t['ybottom'] + 14) for t in tables]
    for c in body:
        if c['color'] in RED and c['bold'] and c['text'].rstrip().endswith(':') and not any(x0 <= c['x'] <= x1 and y0 <= c['y'] <= y1 for x0, x1, y0, y1 in used_y):
            rows, last = [], c['y']
            for r in rows_by_y([n for n in body if c['x'] - 3 <= n['x'] < c['x'] + 260 and n['y'] > c['y'] + 3 and n['size'] >= 8.5]):
                if r[0]['y'] - last > 20 or r[0]['color'] in RED:
                    break
                last = r[0]['y']
                arts = [n for n in r if n['color'] == BLUE and ART_RE.match(n['text'])]
                if arts:
                    rows.append(dict(cells=[' '.join(n['text'] for n in r if n not in arts)], artnr=arts[0]['text'].replace(' ', ''), section=c['text'].rstrip(':'), y=r[0]['y']))
            if rows:
                tables.append(dict(y=c['y'], x0=c['x'] - 6, x1=c['x'] + 260, cols=['Omschrijving'], rows=rows, notes=[], ybottom=last))

    # losse tekst (intro's zoals "Omega profiel » Verzinkt ...") zonder tabel: als notitie bij dichtstbijzijnde tabel
    # afbeeldingen
    imgs = []
    for info in page.get_image_info(xrefs=True):
        bb = pymupdf.Rect(info['bbox']) & page.rect
        if bb.y0 < TOP - 10 or bb.y1 > BOTTOM + 20 or bb.width < 18 or bb.height < 14 or info['xref'] == 0:
            continue
        imgs.append(dict(xref=info['xref'], bb=bb))
    # clusters: afbeeldingen die naast elkaar staan in dezelfde rij
    clusters = []
    for im in sorted(imgs, key=lambda i: (i['bb'].y0, i['bb'].x0)):
        for cl in clusters:
            r = cl['bb']
            vov = min(r.y1, im['bb'].y1) - max(r.y0, im['bb'].y0)
            if vov > 0.5 * min(r.height, im['bb'].height) and im['bb'].x0 - r.x1 < 40 and im['bb'].x1 > r.x0 - 40:
                cl['imgs'].append(im); cl['bb'] = r | im['bb']; break
        else:
            clusters.append(dict(imgs=[im], bb=pymupdf.Rect(im['bb'])))

    def owner(t):
        best, score = None, 1e9
        for k, cl in enumerate(clusters):
            r = cl['bb']
            if r.y0 - 48 <= t['y'] <= r.y1 + 4 and r.x1 <= t['x0'] + 30:      # tabel rechts naast de foto (foto staat gecentreerd in een kader)
                s = (t['x0'] - r.x1) + 0.2 * abs(t['y'] - (r.y0 - 25))
            elif r.y1 <= t['y'] + 6 and r.x0 < t['x1'] and r.x1 > t['x0']:    # tabel onder de foto
                s = 200 + (t['y'] - r.y1)
            else:
                continue
            if s < score:
                best, score = k, s
        return best

    # foto's links van een gekozen kader (foto + maattekening naast elkaar) bij hetzelfde blok voegen
    owned = {owner(t) for t in tables} - {None}
    for k in sorted(owned):
        r = clusters[k]['bb']
        for j, cl in enumerate(clusters):
            if j in owned or j == k or cl.get('merged'):
                continue
            o = cl['bb']
            vov = min(r.y1, o.y1) - max(r.y0, o.y0)
            if o.x1 <= r.x0 + 5 and r.x0 - o.x1 < 120 and vov > 0.4 * min(r.height, o.height):
                clusters[k]['imgs'] = cl['imgs'] + clusters[k]['imgs']; clusters[k]['bb'] = r | o; cl['merged'] = True; cl['imgs'] = []
    groups, key_of = {}, {}
    for t in sorted(tables, key=lambda t: t['y']):
        k = owner(t)
        if k is None:  # bijv. een losse 'Toebehoren'-lijst onder een tabel: hoort bij de tabel erboven
            above = [u for u in tables if u['y'] < t['y'] and abs(u['x0'] - t['x0']) < 25 and id(u) in key_of and t['y'] - u['ybottom'] < 40]
            k = key_of[id(max(above, key=lambda u: u['y']))] if above else f't{t["y"]:.0f}_{t["x0"]:.0f}'
        key_of[id(t)] = k
        groups.setdefault(k, []).append(t)

    for k, ts in groups.items():
        cl = clusters[k] if isinstance(k, int) else None
        ytop = min([t['y'] for t in ts] + ([cl['bb'].y0] if cl else []))
        sub = [s for s in sub_heads if s[0] < ytop + 5]
        if sub:
            state['subgroep'] = f'{sub[-1][1]} {sub[-1][2]}'; state['lijn'] = ''
        bx0 = min([t['x0'] for t in ts] + ([cl['bb'].x0] if cl else []))
        bx1 = max([t['x1'] for t in ts] + ([cl['bb'].x1] if cl else []))
        lijn = sorted([b for b in bars if b[0] < ytop + 5 and b[1] < bx1 - 10 and b[2] > bx0 + 10])
        if lijn:
            state['lijn'] = lijn[-1][3]
        elif sub_heads and any(s[0] < ytop + 5 for s in sub_heads):
            state['lijn'] = ''
        pics, logos = [], []
        if cl:
            for im in sorted(cl['imgs'], key=lambda i: i['bb'].x0):
                bb = im['bb']
                (logos if (bb.height < 34 and bb.width / max(bb.height, 1) > 2.2) or bb.width * bb.height < 1400 else pics).append(
                    save_xref(im['xref'], page, bb))
        if not pics:  # geen foto: vectortekening (bijv. borden/stickers) uit het kader links van de tabel renderen
            tx0 = min(t['x0'] for t in ts)
            ybot = max(t['ybottom'] for t in ts) + 20
            later = [u['y'] for u in tables if u['y'] > ytop + 20 and abs(u['x0'] - tx0) < 25 and u not in ts]
            ybot = min([ybot + 60] + [y - 14 for y in later] + [BOTTOM])
            if tx0 <= 150:  # tabel over de volle breedte: afbeelding staat in de band erboven
                t0 = min(ts, key=lambda t: t['y'])
                prev = [u['ybottom'] + 12 for u in tables if u['ybottom'] < t0['y'] - 5] + [y + 18 for y, *_ in bars if y < t0['y'] - 5] + [TOP + 10]
                y0 = max(prev)
                band = [c for c in body if y0 <= c['y'] < t0['y'] - 4 and c['x'] > 150]
                bx1 = min([c['x'] for c in band] + [580]) - 8
                clip0 = pymupdf.Rect(30, y0, bx1, t0['y'] - 6)
                if band and not t0['notes']:
                    for r_txt in (' '.join(c['text'] for c in r) for r in rows_by_y(band)):
                        if r_txt.startswith('»') or not t0['notes']:
                            t0['notes'].append(r_txt.lstrip('» ').strip())
                        else:
                            t0['notes'][-1] += ' ' + r_txt
                tx0 = bx1 + 8
                ytop = y0 + 8
                ybot = t0['y'] - 6
            clip = pymupdf.Rect(30, ytop - 8, tx0 - 8, ybot)
            if tx0 > 150 and clip.height > 30 and not any(clip.contains(pymupdf.Point(c['x'] + 1, c['y'] + 1)) for c in body if c['color'] in RED or c['color'] == BLUE):
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), clip=clip, alpha=False)
                im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                w, h = im.size
                im = im.crop((8, 8, w - 8, h - 8))
                px = im.load()  # blauwe kaderlijnen wit maken
                for yy in range(im.size[1]):
                    for xx in range(im.size[0]):
                        r_, g_, b_ = px[xx, yy]
                        if b_ > 150 and r_ < 110 and 90 < g_ < 200:
                            px[xx, yy] = (255, 255, 255)
                gray = im.convert('L').point(lambda v: 0 if v > 232 else 255)
                box = gray.getbbox()
                if box and (box[2] - box[0]) > 40 and (box[3] - box[1]) > 40:
                    im = im.crop(box); im.thumbnail((MAX_IMG, MAX_IMG))
                    name = f'r{P}_{int(ytop)}_{int(tx0)}.webp'
                    im.save(os.path.join(out, 'img', name), 'WEBP', quality=74, method=5)
                    pics.append('img/' + name)
        # logo's die binnen het fotokader staan maar als losse afbeelding in een ander cluster vielen
        blocks.append(dict(page=P, hoofdgroep=state['hoofdgroep'], groep=state['groep'], subgroep=state['subgroep'],
                           lijn=state['lijn'], images=pics, logos=logos,
                           tables=[dict(cols=t['cols'], rows=[dict(cells=r['cells'], artnr=r['artnr'], section=r['section']) for r in t['rows']],
                                        notes=t['notes']) for t in sorted(ts, key=lambda t: (t['y'], t['x0']))]))
    # subgroep/lijn die onderaan de pagina begint zonder blok erna
    if sub_heads:
        s = sub_heads[-1]; state['subgroep'] = f'{s[1]} {s[2]}'
    if line_heads and blocks and blocks[-1]['page'] == P:
        pass

json.dump(dict(groups=toc_groups, subgroups=toc_subs, blocks=blocks), open(os.path.join(out, 'raw.json'), 'w'), ensure_ascii=False, indent=1)
n = sum(len(r['rows']) for b in blocks for r in b['tables'])
print(len(blocks), 'blokken', n, 'artikelregels', len(os.listdir(os.path.join(out, 'img'))), 'afbeeldingen')
