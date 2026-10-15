"""Haalt pakketten, onderdelen en afbeeldingen uit de Wijlhuizen transportkoeling-catalogus (PDF).

Gebruik: python3 tools/extract_catalogus.py <catalogus.pdf> <uitvoermap>
Schrijft <uitvoermap>/raw.json en afbeeldingen naar <uitvoermap>/img/.
De ruwe uitvoer wordt daarna met tools/build_data.py (handmatige correcties) omgezet naar data/catalogus.json.
"""
import json, re, sys, os, hashlib
import pymupdf
from PIL import Image

RED, BLUE, BLACK, WHITE = 0xE02528, 0x008CD2, 0x000000, 0xFFFFFF
ART_RE = re.compile(r'^(?:art\.nr\.:\s*)?([0-9]{2}\.[0-9A-Za-z][0-9A-Za-z .\-]*)$', re.I)
PAGE_TOP, PAGE_BOTTOM = 95, 812

pdf, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'img'), exist_ok=True)
doc = pymupdf.open(pdf)


def lines_of(page):
    """Tekstregels met positie/kleur, spans op dezelfde regel en dicht bij elkaar samengevoegd."""
    res = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            # splits op grote horizontale gaten (kolommen binnen een regel)
            groups, cur = [], [spans[0]]
            for s in spans[1:]:
                if s['bbox'][0] - cur[-1]['bbox'][2] > 25 or s['color'] != cur[-1]['color']:
                    groups.append(cur); cur = [s]
                else:
                    cur.append(s)
            groups.append(cur)
            for g in groups:
                text = ' '.join(s['text'].strip() for s in g)
                text = re.sub(r'\s+', ' ', text).strip()
                res.append(dict(x=g[0]['bbox'][0], y=g[0]['bbox'][1], x1=g[-1]['bbox'][2], y1=g[-1]['bbox'][3],
                                size=g[0]['size'], color=g[0]['color'], bold='Bold' in g[0]['font'], text=text))
    res.sort(key=lambda r: (round(r['y']), r['x']))
    return res


def merge_bullets(ls):
    """'»»' + tekst op dezelfde hoogte -> één regel met bullet=True."""
    out_, skip = [], set()
    for i, l in enumerate(ls):
        if i in skip:
            continue
        if l['text'] in ('»»', '»'):
            for j, m in enumerate(ls):
                if j != i and j not in skip and abs(m['y'] - l['y']) < 2 and 0 < m['x'] - l['x'] < 15:
                    m = dict(m); m['bullet'] = True; m['x'] = l['x']
                    out_.append(m); skip.add(j); break
            continue
        if l['text'].startswith('»» ') or l['text'].startswith('» '):
            l = dict(l); l['text'] = l['text'].lstrip('» ').strip(); l['bullet'] = True
        out_.append(l)
    for k in skip:
        pass
    return [l for idx, l in enumerate(out_)]


def render(page, rect, name, zoom=3):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False)
    name = name.rsplit('.', 1)[0] + '.webp'
    Image.frombytes('RGB', (pix.width, pix.height), pix.samples).save(os.path.join(out, 'img', name), 'WEBP', quality=82)
    return 'img/' + name


def save_xref(xref, name, page=None, rect=None):
    """Originele afbeelding (met transparantiemasker) op witte achtergrond opslaan als WebP."""
    if not xref:
        return render(page, rect, name, zoom=3)
    name = name.rsplit('.', 1)[0] + '.webp'
    path = os.path.join(out, 'img', name)
    if os.path.exists(path):
        return 'img/' + name
    info = doc.extract_image(xref)
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:  # CMYK -> RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    img = Image.frombytes('RGBA' if pix.alpha else 'RGB', (pix.width, pix.height), pix.samples)
    if info.get('smask'):
        mask = pymupdf.Pixmap(doc, info['smask'])
        m = Image.frombytes('L', (mask.width, mask.height), mask.samples).resize(img.size)
        bg = Image.new('RGB', img.size, 'white'); bg.paste(img.convert('RGB'), mask=m); img = bg
    elif img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, 'white'); bg.paste(img, mask=img.split()[3]); img = bg
    # spiegeling/rotatie in de PDF negeren we; afbeeldingen staan vrijwel altijd recht
    img.save(path, 'WEBP', quality=82)
    return 'img/' + name


LOGOS = []  # (vingerafdruk, voorbeeldbestand)


def logo_hash(page, rect):
    """Merklogo in een pakketregel herkennen: bijsnijden tot inkt, verkleinen, clusteren op verschil."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), clip=rect, alpha=False)
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    g = img.convert('L').point(lambda v: 255 if v > 200 else 0)
    box = Image.eval(g, lambda v: 255 - v).getbbox()
    if not box:
        return None
    fp = list(img.crop(box).convert('L').resize((32, 12)).get_flattened_data())
    for i, (ref, _) in enumerate(LOGOS):
        if sum(abs(a - b) for a, b in zip(fp, ref)) / len(fp) < 28:
            return i
    fn = f'logo_{len(LOGOS)}.png'
    img.crop(box).save(os.path.join(out, fn))
    LOGOS.append((fp, fn))
    return len(LOGOS) - 1


def join_specs(cell_lines):
    """Bullets + vervolgregels samenvoegen tot specificaties."""
    specs = []
    blue = [l for l in cell_lines if l['color'] == BLUE]
    cols = sorted({round(l['x']) for l in blue if l.get('bullet')})
    def col(l):
        c = [x for x in cols if x <= l['x'] + 1]
        return c[-1] if c else round(l['x'])
    for l in sorted(blue, key=lambda l: (col(l), l['y'])):
        if False:
            continue
        if l.get('bullet'):
            specs.append(dict(text=l['text'], x=l['x'], y=l['y']))
        elif specs and abs(l['x'] - (specs[-1]['x'] + 8.5)) < 4 and 0 < l['y'] - specs[-1]['y'] < 40:
            specs[-1]['text'] += ' ' + l['text']; specs[-1]['y'] = l['y']
        else:
            specs.append(dict(text=l['text'], x=l['x'], y=l['y'], loose=True))
    for s in specs:
        s['text'] = re.sub(r'\s+', ' ', s['text']).replace('- ', '-' if False else '- ').strip()
    return specs


packages, products = [], []
logo_rects = {}

for pno in range(1, 71):  # pagina 2..71 (0-based 1..70)
    page = doc[pno]
    P = pno + 1
    ls = merge_bullets(lines_of(page))
    ls = [l for l in ls if PAGE_TOP < l['y'] < PAGE_BOTTOM and l['color'] != WHITE]
    imgs = [dict(xref=i['xref'], bbox=pymupdf.Rect(i['bbox'])) for i in page.get_image_info(xrefs=True)]
    imgs = [i for i in imgs if PAGE_TOP < i['bbox'].y0 < PAGE_BOTTOM and i['bbox'].width > 8 and i['bbox'].height > 8]

    # titels (rood, groot); meerregelige titels samenvoegen
    titles = []
    for l in ls:
        if l['color'] == RED and l['size'] > 20:
            prev = [t for t in titles if abs(t['x'] - l['x']) < 2 and 0 < l['y'] - t['ylast'] < 40]
            if prev:
                t = prev[-1]
                t['text'] = t['text'][:-1] + l['text'] if t['text'].endswith('-') else t['text'] + ' ' + l['text']
                t['ylast'] = l['y']
            else:
                titles.append(dict(x=l['x'], y=l['y'], ylast=l['y'], text=l['text']))
    if P == 71:
        continue  # koudemiddeltabel apart

    # cellen bepalen
    for t in titles:
        below = [u['y'] for u in titles if (abs(u['x'] - t['x']) < 30 or u['x'] < t['x']) and u['y'] > t['y'] + 5]
        t['y1'] = min(below) if below else PAGE_BOTTOM
    for t in titles:
        right = [u['x'] for u in titles if u['x'] > t['x'] + 50 and u['y'] < t['y1'] - 5 and u['y1'] > t['y'] + 5]
        t['x1'] = min(right) - 2 if right else 596
        t['x0'] = t['x'] - 6
    for t in titles:
        rect = pymupdf.Rect(t['x0'], t['y'] - 2, t['x1'], t['y1'] - 2)
        cell = [l for l in ls if rect.contains(pymupdf.Point(l['x'] + 1, l['y'] + 1)) and not (l['color'] == RED and l['size'] > 20)]
        cimgs = [i for i in imgs if rect.contains(pymupdf.Point((i['bbox'].x0 + i['bbox'].x1) / 2, (i['bbox'].y0 + i['bbox'].y1) / 2))]
        title = t['text']
        is_pkg = 'pakket' in title.lower()
        if is_pkg:
            # pakket
            head = [l for l in cell if l['y'] < min([c['y'] for c in cell if c['text'].startswith('Inhoud set')])]
            specs = join_specs(head)
            arts = [l for l in cell if l['color'] == BLACK and l['text'].lower().startswith('art.nr.')]
            pkg_art = None
            items, section = [], 'inhoud'
            sec_lines = sorted([l for l in cell if l['color'] == RED and l['bold']], key=lambda l: l['y'])
            blues = [l for l in cell if l['color'] == BLUE and not l.get('bullet') and l['x'] > t['x'] + 60 and l['y'] > sec_lines[0]['y']]
            for l in arts:
                if l['x'] < t['x'] + 60 or l['text'].startswith('art.nr.'):
                    if l['text'].startswith('art.nr.') and pkg_art is None:
                        pkg_art = l['text'].split(':', 1)[1].strip(); continue
            item_arts = [l for l in cell if l['color'] == BLACK and l['text'].startswith('Art.nr.')]
            for b in sorted(blues, key=lambda l: l['y']):
                a = min(item_arts, key=lambda a: abs(a['y'] - b['y'] - 15) + abs(a['x'] - b['x']))
                sec = 'inhoud'
                for s in sec_lines:
                    if s['y'] < b['y'] and s['text'].startswith('Optie'):
                        sec = 'optie'
                row = pymupdf.Rect(t['x0'], b['y'] - 10, t['x1'], a['y1'] + 10)
                cy = (b['y'] + a['y1']) / 2
                thumb = sorted([i for i in cimgs if i['bbox'].x1 < b['x'] and row.intersects(i['bbox'])],
                               key=lambda i: abs((i['bbox'].y0 + i['bbox'].y1) / 2 - cy))
                logo_r = pymupdf.Rect(t['x0'] + (t['x1'] - t['x0']) * 0.70, b['y'] - 1, t['x0'] + (t['x1'] - t['x0']) * 0.855, a['y1'] + 1)
                lh = logo_hash(page, logo_r)
                th = None
                if thumb:
                    tb = thumb[0]['bbox']
                    th = save_xref(thumb[0]['xref'], f'item_{a["text"].split(":")[1].strip()}.png', page, tb)
                items.append(dict(name=b['text'], artnr=a['text'].split(':', 1)[1].strip(), section=sec, logo=lh, thumb=th))
            big = [i for i in cimgs if i['bbox'].width > 150]
            photo = None
            if big:
                if len(big) == 1:
                    photo = save_xref(big[0]['xref'], f'pakket_{pkg_art}.png', page, big[0]['bbox'])
                else:
                    r = big[0]['bbox']
                    for i in big[1:]:
                        r |= i['bbox']
                    photo = render(page, r, f'pakket_{pkg_art}.png', zoom=2)
            packages.append(dict(page=P, title=title, art=pkg_art, specs=[s['text'] for s in specs], items=items, photo=photo))
        else:
            specs = join_specs(cell)
            art_lines = [l for l in cell if l['color'] == BLACK and ART_RE.match(l['text'])]
            variants = []
            for a in art_lines:
                m = ART_RE.match(a['text'])
                code = m.group(1).strip()
                extra = ''
                if '(' in code:
                    code, extra = code.split('(', 1)[0].strip(), '(' + code.split('(', 1)[1]
                same_row = [l for l in cell if l['color'] == BLUE and abs(l['y'] - a['y']) < 3 and l['x'] > a['x']]
                label = ' '.join(l['text'] for l in same_row)
                if not label and len(art_lines) > 1:
                    prev = [l for l in cell if l['color'] == BLUE and 0 < a['y'] - l['y'] < 18 and abs(l['x'] - a['x']) < 12]
                    if prev:
                        label = prev[-1]['text']
                variants.append(dict(artnr=code, label=label, note=extra))
            # tabelregels/labels niet als spec
            used = {v['label'] for v in variants if v['label']}
            specs = [s['text'] for s in specs if s['text'] not in used]
            photo = None
            big = [i for i in cimgs if i['bbox'].width > 25 and i['bbox'].height > 25]
            if big:
                im = max(big, key=lambda i: i['bbox'].width * i['bbox'].height)
                photo = save_xref(im['xref'], f'p{P}_{im["xref"]}.png', page, im['bbox'])
            extra_imgs = [i for i in big if photo and i['bbox'].width * i['bbox'].height > 0.25 * im['bbox'].width * im['bbox'].height and i is not im]
            products.append(dict(page=P, title=title, specs=specs, variants=variants, photo=photo,
                                 cell=[round(t['x0']), round(t['y']), round(t['x1']), round(t['y1'])], nimgs=len(cimgs),
                                 extra=[save_xref(i['xref'], f'p{P}_{i["xref"]}.png', page, i['bbox']) for i in (extra_imgs if photo else [])]))

json.dump(dict(packages=packages, products=products, logos=[f for _, f in LOGOS]), open(os.path.join(out, 'raw.json'), 'w'), indent=1, ensure_ascii=False)
print(len(packages), 'pakketten', len(products), 'producten', len(LOGOS), 'logo-varianten')
