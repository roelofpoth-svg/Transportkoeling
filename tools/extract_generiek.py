"""Generieke uitlezer voor Wijlhuizen-catalogi in de huisstijl (blauwe paginatitel, rode tabelkoppen, blauwe artikelnummers).

Gebruik: python3 tools/extract_generiek.py <catalogus.pdf> <uitvoermap>
Schrijft <uitvoermap>/raw.json en afbeeldingen naar <uitvoermap>/img/.

Werkt per catalogusbladzijde; PDF-pagina's met twee bladzijden naast elkaar (spreads) worden in tweeën gesplitst.
Per blok (foto's + tabel) wordt vastgelegd:
  title      paginatitel, opgesplitst in delen per kleur (bijv. ['Mercedes', 'Sprinter', '1995 - 2006'])
  side       tekst van de zijtab (bijv. 'Motor(bediening)')
  section    rode sectiekop (bijv. 'Spanners & rollen' of '1.1.1 Bordscharnieren')
  lijn       blauwe productlijnbalk (bijv. 'Hella · 013.236 serie')
  tables     kolommen, rijen (cellen, artikelnummer, sectie zoals 'Toebehoren', afbeelding bij 'Afb.'-letter), opmerkingen
  images     foto's / tekeningen van het blok
"""
import json, os, re, sys
import pymupdf
from PIL import Image

ART_RE = re.compile(r'^\d{2}\.[0-9A-Z][0-9A-Z.\-/ ]{2,}$', re.I)
LETTER_RE = re.compile(r'^[A-Z]{1,2}[0-9¹²³⁴⁵⁶⁷⁸⁹]{0,2}$')
TOP, BOTTOM = 72, 792
MAX_IMG = 520

pdf, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'img'), exist_ok=True)
doc = pymupdf.open(pdf)


def rgb(c):
    return (c >> 16) & 255, (c >> 8) & 255, c & 255


def is_red(c):
    r, g, b = rgb(c)
    return r > 190 and g < 90 and b < 90


def is_blue(c):
    r, g, b = rgb(c)
    return r < 40 and 110 < g < 170 and b > 180


def is_white(c):
    return c == 0xFFFFFF


def cells_of(page, x0, x1):
    res = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            vertical = l['dir'] != (1.0, 0.0)
            cur = None
            for s in l['spans']:
                t = s['text'].replace('\t', ' ')
                if not t.strip():
                    if cur:
                        cur['gap'] = True
                    continue
                if not (x0 - 2 <= s['bbox'][0] < x1 - 1):
                    continue
                if cur and s['color'] == cur['color'] and abs(s['size'] - cur['size']) < .5 and s['bbox'][0] - cur['x1'] < 6 and not vertical:
                    cur['text'] += (' ' + t.strip()) if (cur.get('gap') or s['bbox'][0] - cur['x1'] > 1.5) else t
                    cur['x1'] = s['bbox'][2]; cur.pop('gap', None)
                    continue
                if cur:
                    res.append(cur)
                cur = dict(x=s['bbox'][0] - x0, y=s['bbox'][1], x1=s['bbox'][2] - x0, y1=s['bbox'][3], size=round(s['size'], 1),
                           color=s['color'], bold='Bold' in s['font'], text=t, vertical=vertical)
            if cur:
                res.append(cur)
    out_ = []
    for c in res:
        c['text'] = re.sub(r'\s+', ' ', c['text']).strip()
        c.pop('gap', None)
        if not c['text']:
            continue
        # 'Verg. OE-nr.Artikelnummer' (één span) -> twee koppen
        m = re.match(r'^(.+?)(Artikelnummer|Art\.\s?nr\.?)$', c['text'])
        if m and is_red(c['color']) and c['size'] < 9.5:
            w = c['x1'] - c['x']
            cut = c['x'] + w * len(m.group(1)) / len(c['text'])
            out_.append(dict(c, text=m.group(1).strip(), x1=cut))
            out_.append(dict(c, text=m.group(2), x=cut + 1))
            continue
        out_.append(c)
    return out_


def rows_by_y(items, tol=2.5):
    rows = []
    for c in sorted(items, key=lambda c: (c['y'], c['x'])):
        if rows and abs(rows[-1][0]['y'] - c['y']) < tol:
            rows[-1].append(c)
        else:
            rows.append([c])
    return [sorted(r, key=lambda c: c['x']) for r in rows]


def to_img(pix):
    if pix.colorspace and pix.colorspace.n == 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    if pix.n == 1:
        return Image.frombytes('L', (pix.width, pix.height), pix.samples).convert('RGB')
    return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def save_xref(xref, page, bbox):
    name = f'x{xref}.webp'
    path = os.path.join(out, 'img', name)
    if os.path.exists(path):
        return 'img/' + name
    try:
        info = doc.extract_image(xref)
        img = to_img(pymupdf.Pixmap(doc, xref))
        if info.get('smask'):
            m = pymupdf.Pixmap(doc, info['smask'])
            mask = Image.frombytes('L', (m.width, m.height), m.samples).resize(img.size)
            bg = Image.new('RGB', img.size, 'white'); bg.paste(img, mask=mask); img = bg
    except Exception:
        img = to_img(page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), clip=bbox, alpha=False))
    img.thumbnail((MAX_IMG, MAX_IMG))
    img.save(path, 'WEBP', quality=72, method=5)
    return 'img/' + name


def render_clip(page, clip, name):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), clip=clip, alpha=False)
    im = to_img(pix)
    w, h = im.size
    if w < 30 or h < 30:
        return None
    im = im.crop((6, 6, w - 6, h - 6))
    px = im.load()
    for yy in range(im.size[1]):
        for xx in range(im.size[0]):
            r_, g_, b_ = px[xx, yy]
            if b_ > 150 and r_ < 110 and 90 < g_ < 200:
                px[xx, yy] = (255, 255, 255)
    ink = im.convert('L').point(lambda v: 0 if v > 232 else 255)
    box = ink.getbbox()
    if not box or (box[2] - box[0]) < 40 or (box[3] - box[1]) < 40:
        return None
    bw, bh = box[2] - box[0], box[3] - box[1]
    filled = sum(ink.crop(box).histogram()[255:]) / float(bw * bh)
    if bw / bh > 5 or filled < 0.025:
        return None  # vrijwel leeg of alleen een kopbalk
    im = im.crop(box)
    # rode kopbalken en blauwe tekst zonder tekening zijn geen productafbeelding
    small = im.resize((40, 40))
    px_ = list(small.getdata())
    red = sum(1 for r, g, b in px_ if r > 190 and g < 90 and b < 90) / 1600
    if red > 0.12:
        return None
    im.thumbnail((MAX_IMG, MAX_IMG))
    im.save(os.path.join(out, 'img', name), 'WEBP', quality=72, method=5)
    return 'img/' + name


state = dict(title=[], side='', section='', lijn='')
blocks, pages_seen = [], 0


def process(page, X0, X1, P, label):
    cells = cells_of(page, X0, X1)
    W = X1 - X0

    # paginatitel (grote witte/rode tekst bovenaan), in delen per kleur
    tparts = [c for c in cells if c['y'] < 75 and c['size'] >= 11 and not c['vertical'] and (is_white(c['color']) or is_red(c['color']))]
    if any(c['size'] >= 18 for c in tparts):
        parts = [c['text'] for c in sorted(tparts, key=lambda c: c['x'])]
        state['title'] = parts
    # zijtab (verticale tekst aan de rand, of korte tekst in de rand)
    side = [c for c in cells if c['vertical'] and c['size'] >= 9 and (c['x'] < 25 or c['x'] > W - 30)]
    side = [c for c in side if not re.fullmatch(r'[\d.]+', c['text'])]
    if side:
        state['side'] = max(side, key=lambda c: len(c['text']))['text']
    side_num = [c for c in cells if not c['vertical'] and c['size'] >= 11.5 and (c['x'] < 25 or c['x'] > W - 30) and re.fullmatch(r'\d+(\.\d+)*', c['text'])]

    if any(re.search(r'index|inhoudsopgave|crossreferentie|register', t_, re.I) for t_ in state['title']) and any(c['size'] >= 18 and c['y'] < 75 for c in cells):
        return  # register-/indexpagina's
    body = [c for c in cells if TOP < c['y'] < BOTTOM and c['size'] < 16 and not c['vertical'] and 25 < c['x'] < W - 30 and c['size'] >= 7.5]

    # balken: gevulde rechthoeken (rood = sectie, blauw = productlijn)
    bars = []  # (y0, x0, x1, kind, text)
    for dr in page.get_drawings():
        r, f = dr['rect'], dr.get('fill')
        if not f or not (8 < r.height < 24 and r.width > 90 and TOP - 25 < r.y0 < BOTTOM):
            continue
        rx0, rx1 = r.x0 - X0, r.x1 - X0
        if rx1 < 0 or rx0 > W:
            continue
        kind = 'blue' if (f[2] > .7 and f[0] < .2 and f[1] < .7) else 'red' if (f[0] > .75 and f[1] < .35 and f[2] < .35) else None
        if not kind:
            continue
        txt = [c for c in cells if is_white(c['color']) and rx0 - 2 <= c['x'] <= rx1 and r.y0 - 3 <= c['y'] <= r.y1 and not c['vertical']]
        if txt:
            bars.append((r.y0, rx0, rx1, kind, '  '.join(c['text'] for c in sorted(txt, key=lambda c: c['x']))))
    # rode bars met wit (trailerbouw-stijl) én losse rode koppen van 9.5-11 pt (koelingsdelen-stijl) zijn sectiekoppen
    sections = [(b[0], b[1], b[2], b[4]) for b in bars if b[3] == 'red']
    for r in rows_by_y([c for c in body if is_red(c['color']) and c['bold'] and 9.6 <= c['size'] <= 12]):
        # koppen naast elkaar (tegelrasters) zijn aparte secties voor hun eigen kolom
        groups_, cur = [], [r[0]]
        for c in r[1:]:
            if c['x'] - cur[-1]['x1'] > 25:
                groups_.append(cur); cur = [c]
            else:
                cur.append(c)
        groups_.append(cur)
        for gi, g in enumerate(groups_):
            txt = ' '.join(c['text'] for c in g)
            if txt.endswith(':') or not re.search(r'[A-Za-zÀ-ÿ]{3}', txt):
                continue
            gx1 = groups_[gi + 1][0]['x'] - 6 if gi + 1 < len(groups_) else W
            sections.append((g[0]['y'] - 4, g[0]['x'] - 6, gx1, txt))
    lines_ = [(b[0], b[1], b[2], b[4]) for b in bars if b[3] == 'blue']

    # tabellen
    blue_arts = [c for c in body if is_blue(c['color']) and ART_RE.match(c['text'])]
    is_art_name = lambda c: re.match(r'(Artikel\s?nummer|Art\.\s?nr\.?|Artikelnr\.?)', c['text'], re.I)
    headers = []
    for r in rows_by_y([c for c in body if is_red(c['color']) and c['bold'] and c['size'] < 9.6 and not c['text'].endswith(':')]):
        # kolom is een artikelnummerkolom als er blauwe artikelnummers onder staan (of de kop zo heet)
        flags = []
        for k, c in enumerate(r):
            nx = r[k + 1]['x'] - 2 if k + 1 < len(r) else c['x'] + 120
            hits = [a for a in blue_arts if c['x'] - 5 <= a['x'] < nx and 0 < a['y'] - c['y'] < 90]
            flags.append(bool(hits) or bool(is_art_name(c)))
        if not any(flags) or (len(r) < 2 and not is_art_name(r[0])):
            continue
        seg, seg_flags = [], []
        for k, c in enumerate(r):
            # nieuwe tabel naast de vorige: kop herhaalt zich na een artikelnummerkolom
            if seg and any(seg_flags) and (c['text'] == seg[0]['text'] or (not flags[k] and seg_flags[-1] and is_art_name(seg[-1]) and k + 1 < len(r))):
                headers.append((seg, seg_flags)); seg, seg_flags = [], []
            seg.append(c); seg_flags.append(flags[k])
        if seg and any(seg_flags):
            headers.append((seg, seg_flags))
    art_flag = {id(c): f for h, fl in headers for c, f in zip(h, fl)}
    headers = [h for h, _ in headers]
    is_art_head = lambda c: art_flag.get(id(c), False)
    head_ids = {id(c) for h in headers for c in h}
    tables = []
    for h in headers:
        hx0 = h[0]['x'] - 6
        art_heads = [c for c in h if is_art_head(c)]
        art_col = art_heads[0]
        last_col = art_heads[-1] if art_heads[-1] is h[-1] else h[-1]
        right = [g[0]['x'] for g in headers if abs(g[0]['y'] - h[0]['y']) < 3 and g[0]['x'] > h[0]['x'] + 5]
        hx1 = min([max(c['x1'] for c in h) + 80] + [x - 4 for x in right])
        nxt = [g[0]['y'] for g in headers if g is not h and g[0]['y'] > h[0]['y'] + 3 and g[0]['x'] < art_col['x1'] - 5 and max(c['x1'] for c in g) > hx0 + 10]
        nxt += [y for y, bx0, bx1, _ in lines_ + sections if y > h[0]['y'] + 3 and bx0 < art_col['x1'] - 5 and bx1 > hx0 + 10]
        ylim = min(nxt) - 2 if nxt else BOTTOM
        cols = [(c['x'] - 3, c['text']) for c in h if not is_art_head(c)]
        if not cols:
            cols = [(hx0, 'Omschrijving')]
        art_x = [(c['x'] - 5, (h[h.index(c) + 1]['x'] - 2) if h.index(c) + 1 < len(h) else hx1, c) for c in art_heads]
        mine = [c for c in body if h[0]['y'] + 3 < c['y'] < ylim and hx0 <= c['x'] <= hx1 and id(c) not in head_ids]
        rows, notes, section, last_y = [], [], '', h[0]['y']
        for r in rows_by_y(mine):
            if r[0]['y'] - last_y > 54 and rows:
                break
            last_y = r[0]['y']
            txt = ' '.join(c['text'] for c in r)
            if is_red(r[0]['color']) and r[0]['bold']:
                section = txt.rstrip(':'); continue
            arts = [c for c in r if is_blue(c['color']) and ART_RE.match(c['text']) and any(x0 <= c['x'] < x1 for x0, x1, _ in art_x)]
            if txt.startswith('»') or txt.startswith('›'):
                notes.append(txt.lstrip('»› ').strip()); continue
            if arts:
                vals = [''] * len(cols)
                for c in r:
                    if c in arts:
                        continue
                    k = max([j for j, (x, _) in enumerate(cols) if x <= c['x'] + 2] or [0])
                    vals[k] = (vals[k] + ' ' + c['text']).strip()
                for a in arts:
                    var = ''
                    hh = next(c for x0, x1, c in art_x if x0 <= a['x'] < x1)
                    if len(art_heads) > 1 or not is_art_name(hh):
                        var = re.sub(r'^(Artikel\s?nummer|Art\.?\s*nr\.?)\s*', '', hh['text'], flags=re.I)
                    rows.append(dict(cells=list(vals), artnr=a['text'].replace(' ', ''), section=(section + ' ' + var).strip(), y=r[0]['y']))
            elif rows and r[0]['y'] - rows[-1]['y'] < 34 and not notes and r[0]['y'] - last_row_y(rows, mine) < 12.5:
                for c in r:
                    k = max([j for j, (x, _) in enumerate(cols) if x <= c['x'] + 2] or [0])
                    cell = rows[-1]['cells'][k]
                    sep = ' | ' if k > 0 and cell else ' '
                    for row in rows[-len(arts_of_last(rows)):]:
                        row['cells'][k] = (row['cells'][k] + (sep if row['cells'][k] else '') + c['text']).strip()
                rows[-1]['ycont'] = r[0]['y']
            else:
                notes.append(txt)
        if rows:
            tables.append(dict(y=h[0]['y'], x0=hx0, x1=hx1, cols=[t for _, t in cols], rows=rows, notes=notes, ybottom=last_y))

    used = [(t['x0'], t['x1'], t['y'], max(r_['y'] for r_ in t['rows']) + 2) for t in tables]
    for c in body:
        if is_red(c['color']) and c['bold'] and (c['text'].rstrip().endswith(':') or re.match(r'^(Onderdelen|Toebehoren|Accessoires|Losse onderdelen|Reserveonderdelen)$', c['text'], re.I)) and not any(x0 <= c['x'] <= x1 and y0 <= c['y'] <= y1 for x0, x1, y0, y1 in used):
            rights = [o['x'] for o in body if abs(o['y'] - c['y']) < 3 and o['x'] > c['x'] + 40 and is_red(o['color'])]
            lx1 = min(rights) - 4 if rights else W
            # lijst kan in twee kolommen staan; neem alles tot het volgende rode label/kop
            rows, last = [], c['y']
            for r in rows_by_y([n for n in body if c['x'] - 3 <= n['x'] < lx1 and n['y'] > c['y'] + 3 and n['size'] >= 7.5]):
                if r[0]['y'] - last > 22 or (is_red(r[0]['color']) and r[0]['bold']):
                    break
                last = r[0]['y']
                # per regel kunnen meerdere (omschrijving, artikelnummer)-paren staan
                pair = []
                for n in r:
                    if is_blue(n['color']) and ART_RE.match(n['text']):
                        rows.append(dict(cells=[' '.join(p['text'] for p in pair)], artnr=n['text'].replace(' ', ''), section=c['text'].rstrip(':'), y=r[0]['y'])); pair = []
                    else:
                        pair.append(n)
            if rows:
                tables.append(dict(y=c['y'], x0=c['x'] - 6, x1=lx1, cols=['Omschrijving'], rows=rows, notes=[], ybottom=last))

    # kaarten (luchtbalgen): 'WH' + artikelnummer, daaronder OE / VC / BT kruisverwijzingen, rechts tekeningen
    whs = [(c, a) for c in body if c['bold'] and not is_blue(c['color']) and c['text'] == 'WH'
           for a in body if is_blue(c['color']) is False and is_blue(a['color']) and ART_RE.match(a['text'].strip()) and abs(a['y'] - c['y']) < 3 and 0 < a['x'] - c['x'] < 30]
    whs.sort(key=lambda p_: (p_[0]['x'] > W / 2, p_[0]['y']))
    for i, (c, a) in enumerate(whs):
        nxt = [o[0]['y'] for o in whs if abs(o[0]['x'] - c['x']) < 20 and o[0]['y'] > c['y'] + 5]
        nxt += [y for y, bx0, bx1, _ in lines_ + sections if y > c['y'] + 5 and bx0 < c['x'] + 50 and bx1 > c['x']]
        y1 = min(nxt + [BOTTOM]) - 4
        labels = [l for l in body if l['bold'] and not is_blue(l['color']) and re.fullmatch(r'[A-Z]{2,3}', l['text']) and abs(l['x'] - c['x']) < 3 and c['y'] + 5 < l['y'] < y1]
        cols, vals = [], []
        for l in labels:
            v = [o['text'] for o in body if abs(o['y'] - l['y']) < 3 and l['x'] + 8 < o['x'] < l['x'] + 120 and not o['bold']]
            cols.append(l['text']); vals.append(' '.join(v))
        notes = []
        for r in rows_by_y([o for o in body if c['y'] - 3 < o['y'] < y1 and o['x'] > c['x'] + 110 and o['size'] >= 7.5 and not is_red(o['color']) and not is_blue(o['color'])]):
            for o in r:
                t_ = o['text'].lstrip('» ').strip()
                if t_ and t_ != '»»':
                    notes.append(t_)
        tables.append(dict(y=c['y'], x0=c['x'] - 6, x1=W, cols=cols or ['Omschrijving'], rows=[dict(cells=vals or [''], artnr=a['text'].replace(' ', ''), section='', y=a['y'])],
                           notes=notes, ybottom=y1, card=(c['x'] + 120, c['y'] - 6, W - 28, min([o['y'] for o in body if o['text'].startswith('»') and c['y'] < o['y'] < y1] + [y1]) - 4)))

    # tegels: rode titel met direct eronder een artikelnummer
    for c in body:
        if is_red(c['color']) and c['bold'] and 7.5 <= c['size'] <= 10.5 and id(c) not in head_ids and not c['text'].endswith(':'):
            if any(t['x0'] - 2 <= c['x'] <= t['x1'] and t['y'] <= c['y'] <= t['ybottom'] + 5 for t in tables):
                continue
            below = [a for a in body if is_blue(a['color']) and ART_RE.match(a['text']) and abs(a['x'] - c['x']) < 4 and 8 < a['y'] - c['y'] < 30]
            if not below:
                continue
            a = below[0]
            right = [t['x'] for t in body if abs(t['y'] - c['y']) < 3 and t['x'] > c['x'] + 30 and is_red(t['color'])]
            x1 = min(right) - 4 if right else W
            notes, last = [], a['y']
            for r in rows_by_y([n for n in body if c['x'] - 3 <= n['x'] < x1 and n['y'] > a['y'] + 3 and not is_blue(n['color']) and n['size'] >= 8]):
                if r[0]['y'] - last > 16 or is_red(r[0]['color']):
                    break
                last = r[0]['y']; t_ = ' '.join(n['text'] for n in r)
                if t_.startswith('»') or not notes:
                    notes.append(t_.lstrip('» ').strip())
                else:
                    notes[-1] += ' ' + t_
            tables.append(dict(y=c['y'], x0=c['x'] - 6, x1=x1, cols=['Omschrijving'], rows=[dict(cells=[c['text']], artnr=a['text'].replace(' ', ''), section='', y=a['y'])], notes=notes, ybottom=last, loose=None))

    # vangnet: losse blauwe artikelnummers in tegels (kleurstalen, rasters met OE-nummers)
    taken = {(round(r['y']), r['artnr']) for t in tables for r in t['rows']}
    rects = []
    for dr in page.get_drawings():
        r = dr['rect']
        if 40 < r.width < 320 and 25 < r.height < 320:
            rects.append((pymupdf.Rect(r.x0 - X0, r.y0, r.x1 - X0, r.y1), bool(dr.get('fill')), dr.get('fill')))
    for a in blue_arts:
        if not a['bold'] or (round(a['y']), a['text'].replace(' ', '')) in taken or any((abs(round(a['y']) - y) <= 1 and n == a['text'].replace(' ', '')) for y, n in taken):
            continue
        frame = [r for r, filled, f in rects if r.contains(pymupdf.Point(a['x'] + 1, a['y'] + 2)) and not (filled and f and f[2] > .7 and f[0] < .2)]
        frame = min(frame, key=lambda r: r.width * r.height) if frame else None
        x_lo, x_hi = (frame.x0, frame.x1) if frame else (a['x'] - 4, a['x'] + 90)
        y_lo, y_hi = (frame.y0, frame.y1) if frame else (a['y'] - 30, a['y'] + 24)
        near = [c for c in body if c is not a and x_lo - 2 <= c['x'] < x_hi and y_lo - 2 <= c['y'] <= y_hi and not is_red(c['color']) and not (is_blue(c['color']) and ART_RE.match(c['text']))]
        above = [c['text'] for c in sorted(near, key=lambda c: c['y']) if c['y'] < a['y'] - 2 and abs(c['x'] - a['x']) < 6]
        below = [c['text'] for c in sorted(near, key=lambda c: (c['y'], c['x'])) if c['y'] > a['y'] + 2]
        name = ' '.join(above)
        clip = None
        if frame:
            clip = pymupdf.Rect(frame.x0 + X0, frame.y0, frame.x1 + X0, frame.y1)
        else:
            sw = [r for r, filled, f in rects if filled and r.x0 - 6 <= a['x'] <= r.x1 and 0 < a['y'] - r.y1 < 60]
            if sw:
                r = max(sw, key=lambda r: r.y1); clip = pymupdf.Rect(r.x0 + X0, r.y0, r.x1 + X0, r.y1)
        tables.append(dict(y=a['y'] - 1, x0=a['x'] - 6, x1=x_hi, cols=['Omschrijving', 'Info'],
                           rows=[dict(cells=[name, ' · '.join(below)], artnr=a['text'].replace(' ', ''), section='', y=a['y'])],
                           notes=[], ybottom=a['y'] + 10, loose=clip, card=None))
        taken.add((round(a['y']), a['text'].replace(' ', '')))

    # afbeeldingen
    imgs = []
    for info in page.get_image_info(xrefs=True):
        bb = pymupdf.Rect(info['bbox']) & page.rect
        bb = pymupdf.Rect(bb.x0 - X0, bb.y0, bb.x1 - X0, bb.y1)
        cx = (bb.x0 + bb.x1) / 2
        if not (0 <= cx <= W) or bb.y0 < TOP - 12 or bb.y1 > BOTTOM + 20 or bb.width < 18 or bb.height < 14 or info['xref'] == 0:
            continue
        if bb.width > W * 0.9 and bb.height > 600:
            continue  # paginavullende achtergrond
        imgs.append(dict(xref=info['xref'], bb=bb, abs=pymupdf.Rect(bb.x0 + X0, bb.y0, bb.x1 + X0, bb.y1)))
    # 'Afb.'-letters onder/in de foto's
    letters = [c for c in body if is_blue(c['color']) and c['bold'] and LETTER_RE.match(c['text'].strip()) and not any(t['x0'] <= c['x'] <= t['x1'] and t['y'] <= c['y'] <= t['ybottom'] + 3 for t in tables)]
    letter_img = {}
    for c in letters:
        cand = [im for im in imgs if im['bb'].x0 - 15 <= c['x'] <= im['bb'].x1 + 5 and im['bb'].y0 - 10 <= c['y'] <= im['bb'].y1 + 30]
        if cand:
            im = min(cand, key=lambda im: abs(c['y'] - im['bb'].y1) + abs(c['x'] - im['bb'].x0) * .3)
            letter_img[(round(c['y'] / 400), c['text'].strip())] = im  # meerdere rasters per blad: y-zone als sleutel
            im.setdefault('letters', []).append(c['text'].strip())

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
            if r.y0 - 48 <= t['y'] <= r.y1 + 4 and r.x1 <= t['x0'] + 30:
                s = (t['x0'] - r.x1) + 0.2 * abs(t['y'] - (r.y0 - 25))
            elif r.y1 <= t['y'] + 6 and r.x0 < t['x1'] and r.x1 > t['x0']:
                s = 200 + (t['y'] - r.y1)
            else:
                continue
            if s < score:
                best, score = k, s
        return best

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
        afb = 'Afb.' in t['cols'] or any(LETTER_RE.match((r['cells'][0] if r['cells'] else '') or '') for r in t['rows'][:3])
        if t.get('card') or 'loose' in t:
            k = f'card{t["y"]:.0f}_{t["x0"]:.0f}'
        elif afb:
            k = f'afb{t["y"]:.0f}_{t["x0"]:.0f}'
        elif k is None:
            above = [u for u in tables if u['y'] < t['y'] and abs(u['x0'] - t['x0']) < 25 and id(u) in key_of and t['y'] - u['ybottom'] < 40]
            k = key_of[id(max(above, key=lambda u: u['y']))] if above else f't{t["y"]:.0f}_{t["x0"]:.0f}'
        key_of[id(t)] = k
        groups.setdefault(k, []).append(t)

    for k, ts in groups.items():
        cl = clusters[k] if isinstance(k, int) else None
        ytop = min([t['y'] for t in ts] + ([cl['bb'].y0] if cl else []))
        bx0 = min([t['x0'] for t in ts] + ([cl['bb'].x0] if cl else []))
        bx1 = max([t['x1'] for t in ts] + ([cl['bb'].x1] if cl else []))
        pics, row_img = [], {}
        if isinstance(k, str) and k.startswith('afb'):
            # raster met letters: alle afbeeldingen in de band boven de tabel (tot vorige tabel/sectie)
            t0 = ts[0]
            prev = [u['ybottom'] + 8 for u in tables if u['ybottom'] < t0['y'] - 5 and u['x0'] < t0['x1'] and u['x1'] > t0['x0']]
            prev += [y for y, sx0, sx1, _ in sections if y < t0['y'] - 5 and sx0 < t0['x1'] and sx1 > t0['x0']]
            y0 = max(prev + [TOP - 12])
            band = [im for im in imgs if y0 - 4 <= im['bb'].y0 and im['bb'].y1 <= t0['y'] + 4 and im['bb'].x1 > t0['x0'] - 20 and im['bb'].x0 < t0['x1'] + 20]
            band.sort(key=lambda im: (round(im['bb'].y0 / 30), im['bb'].x0))
            for im in band:
                src = save_xref(im['xref'], page, im['abs'])
                pics.append(src)
                for L in im.get('letters', []):
                    row_img[L] = src
            if not band:  # vectortekening
                clip = pymupdf.Rect(30 + X0, y0, X0 + min(t0['x1'], W - 25), t0['y'] - 6)
                if clip.height > 40:
                    r_ = render_clip(page, clip, f'r{P}_{label}_{int(t0["y"])}.webp')
                    if r_:
                        pics.append(r_)
        elif cl:
            for im in sorted(cl['imgs'], key=lambda i: i['bb'].x0):
                bb = im['bb']
                if (bb.height < 34 and bb.width / max(bb.height, 1) > 2.2) or bb.width * bb.height < 1400:
                    continue  # merklogo
                pics.append(save_xref(im['xref'], page, im['abs']))
        if not pics and 'loose' in ts[0]:
            t0 = ts[0]; ax, ay = t0['x0'] + 6, t0['rows'][0]['y']
            # tegel begrenzen door de buurtegels (volgende artikelnummer rechts / eronder)
            right_ = [b_['x'] for b_ in blue_arts if abs(b_['y'] - ay) < 12 and b_['x'] > ax + 20]
            down_ = [b_['y'] for b_ in blue_arts if abs(b_['x'] - ax) < 15 and b_['y'] > ay + 15]
            reg = pymupdf.Rect(ax - 8, ay - 8, min([ax + 135] + [x - 8 for x in right_]), min([ay + 95] + [y - 8 for y in down_]))
            near_imgs = [im for im in imgs if reg.contains(pymupdf.Point((im['bb'].x0 + im['bb'].x1) / 2, (im['bb'].y0 + im['bb'].y1) / 2))]
            for im in near_imgs[:2]:
                pics.append(save_xref(im['xref'], page, im['abs']))
            if not pics and not t0['loose']:
                t0['loose'] = pymupdf.Rect(reg.x0 + X0, reg.y0, reg.x1 + X0, reg.y1)
        if not pics and ts[0].get('loose'):
            cl_ = ts[0]['loose']
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=cl_, alpha=False)
            im_ = to_img(pix); im_.thumbnail((MAX_IMG, MAX_IMG))
            nm = f'l{P}_{label}_{int(cl_.y0)}_{int(cl_.x0)}.webp'
            im_.save(os.path.join(out, 'img', nm), 'WEBP', quality=72, method=5)
            pics.append('img/' + nm)
        if not pics and ts[0].get('card'):
            cx0, cy0, cx1, cy1 = ts[0]['card']
            r_ = render_clip(page, pymupdf.Rect(cx0 + X0, cy0, cx1 + X0, cy1), f'r{P}_{label}_{int(cy0)}.webp')
            if r_:
                pics.append(r_)
        if not pics:
            tx0 = min(t['x0'] for t in ts)
            if tx0 > 150:
                later = [u['y'] for u in tables if u['y'] > ytop + 20 and abs(u['x0'] - tx0) < 25 and u not in ts]
                ybot = min([max(t['ybottom'] for t in ts) + 80] + [y - 14 for y in later] + [BOTTOM])
                clip = pymupdf.Rect(30 + X0, ytop - 8, X0 + tx0 - 8, ybot)
                if not any(clip.contains(pymupdf.Point(c['x'] + X0 + 1, c['y'] + 1)) for c in body if is_red(c['color']) or is_blue(c['color'])):
                    r_ = render_clip(page, clip, f'r{P}_{label}_{int(ytop)}.webp')
                    if r_:
                        pics.append(r_)
        if not pics:  # tekening onder de tabel (bijv. explosietekening onder een asentabel)
            t_last = max(ts, key=lambda t: t['ybottom'])
            below_t = [u['y'] for u in tables if u['y'] > t_last['ybottom'] + 5 and u['x0'] < t_last['x1'] and u['x1'] > t_last['x0']]
            below_t += [y for y, sx0, sx1, _ in sections + lines_ if y > t_last['ybottom'] + 5 and sx0 < t_last['x1'] and sx1 > t_last['x0']]
            y0, y1 = t_last['ybottom'] + 14, min(below_t + [BOTTOM]) - 6
            if y1 - y0 > 120:
                words_ = [c for c in body if y0 <= c['y'] <= y1 and t_last['x0'] - 5 <= c['x'] <= t_last['x1'] and c['size'] >= 8.5 and re.search(r'[A-Za-z]{3}', c['text'])]
                if len(words_) <= 3:
                    r_ = render_clip(page, pymupdf.Rect(max(30, t_last['x0']) + X0, y0, X0 + min(W - 25, t_last['x1']), y1), f'b{P}_{label}_{int(y0)}.webp')
                    if r_:
                        pics.append(r_)
        # koppen voor dit blok
        sec = sorted([s for s in sections if s[0] < ytop + 5 and s[1] < bx1 - 10 and s[2] > bx0 + 10])
        if sec:
            state['section'] = sec[-1][3]; state['lijn'] = ''
        ln = sorted([b for b in lines_ if b[0] < ytop + 5 and b[1] < bx1 - 10 and b[2] > bx0 + 10])
        if ln and (not sec or ln[-1][0] > sec[-1][0]):
            state['lijn'] = ln[-1][3]
        out_tables = []
        for t in sorted(ts, key=lambda t: (t['y'], t['x0'])):
            rows = []
            for r in t['rows']:
                d = dict(cells=r['cells'], artnr=r['artnr'], section=r['section'])
                if 'Afb.' in t['cols']:
                    L = r['cells'][t['cols'].index('Afb.')].strip()
                    if L in row_img:
                        d['img'] = row_img[L]
                rows.append(d)
            out_tables.append(dict(cols=t['cols'], rows=rows, notes=t['notes']))
        blocks.append(dict(page=label, pdfpage=P, title=list(state['title']), side=state['side'], section=state['section'], lijn=state['lijn'],
                           sidenum=side_num[0]['text'] if side_num else '', images=pics, tables=out_tables))
    if sections:
        state['section'] = max(sections)[3]


def last_row_y(rows, mine):
    return rows[-1].get('ycont', rows[-1]['y'])


def arts_of_last(rows):
    # rijen die bij dezelfde fysieke regel horen (meerdere artikelnummerkolommen)
    y = rows[-1]['y']
    return [r for r in rows if r['y'] == y]


ONLY = {int(x) for x in os.environ.get('PAGES', '').split(',') if x}
for pno in range(len(doc)):
    if ONLY and pno + 1 not in ONLY:
        continue
    page = doc[pno]
    W = page.rect.width
    halves = [(0, W / 2), (W / 2, W)] if W > 1000 else [(0, W)]
    before = len(blocks)
    per_half = []
    for hi, (x0, x1) in enumerate(halves):
        # paginanummer onderaan deze helft
        nums = [s for s in page.get_text('dict')['blocks'] for l in s.get('lines', []) for s in l['spans']
                if s['bbox'][1] > 795 and x0 <= s['bbox'][0] < x1 and re.fullmatch(r'\d{1,4}', s['text'].strip())]
        label = int(nums[0]['text'].strip()) if nums else (pno + 1) * len(halves) - (len(halves) - 1 - hi)
        n0 = len(blocks)
        process(page, x0, x1, pno + 1, label)
        per_half.append((x0, x1, blocks[n0:]))
    # spread: tekening op de ene helft (zonder artikelnummers), tabel op de andere -> tekening koppelen
    if len(per_half) == 2:
        for (ax0, ax1, bl), (bx0, bx1, other) in ((per_half[0], per_half[1]), (per_half[1], per_half[0])):
            if bl and not other and any(not b['images'] for b in bl) and page.get_images():
                r_ = render_clip(page, pymupdf.Rect(bx0 + 28, TOP + 8, bx1 - 28, BOTTOM - 4), f'h{pno + 1}_{int(bx0)}.webp')
                if r_:
                    for b in bl:
                        if not b['images']:
                            b['images'] = [r_]

json.dump(dict(source=os.path.basename(pdf), blocks=blocks), open(os.path.join(out, 'raw.json'), 'w'), ensure_ascii=False, indent=0)
n = sum(len(t['rows']) for b in blocks for t in b['tables'])
print(len(blocks), 'blokken', n, 'artikelregels', len(os.listdir(os.path.join(out, 'img'))), 'afbeeldingen')
