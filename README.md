# Wijlhuizen Onderdelenzoeker

Online selectietool die de papieren catalogi vervangt. Eén tool, één zoekbalk over alle 14 catalogi
(zoeken op artikelnummer, OE-nummer, type of omschrijving).

**Online:** https://roelofpoth-svg.github.io/Wijlhuizenonderdelenzoeker/

## Catalogi

| Catalogus | Zoekboom | Producten | Artikelnummers |
|---|---|---:|---:|
| Transportkoeling | merk → type koelunit (eigen weergave) | 186 | – |
| Trailerbouwdelen | hoofdgroep → groep → subgroep | 1.790 | 4.078 |
| Koelingsdelen truck | merk → model + bouwjaren → onderdeelgroep | 895 | 1.743 |
| Truckschadedelen | merk → model + bouwjaren → groep | 912 | 2.463 |
| Scania P/G/R-serie | hoofdstuk → onderdeelgroep | 638 | 2.989 |
| Verlichting | lamptype → truck/trailer → merk | 3.004 | 8.478 |
| Elektra & installatie | hoofdstuk → groep | 1.372 | 3.403 |
| Luchtremkoppelingen | systeem (Raufoss, Voss, …) | 875 | 3.775 |
| Luchtbalgen | soort balg → fabrikant/type | 611 | 486 |
| Aanhanger- & trailerasdelen | asfabrikant → schijf-/trommelrem/gereedschap | 322 | 2.617 |
| Voertuig op- & aanbouwdelen | hoofdstuk | 687 | 3.496 |
| Laadklepdelen | merk laadklep → onderdeelgroep | 1.627 | 2.473 |
| Bevestigingsmaterialen | soort → norm | 572 | 8.415 |
| Werkplaatsbenodigdheden | hoofdstuk → groep | 1.165 | 1.978 |

Controle per catalogus: alle blauwe artikelnummers uit de PDF komen in de data voor, behalve 4 van de 490 bij
Luchtbalgen. Bij tabellen met fotoletters (A, B, C …) heeft elke regel zijn eigen foto.
Vergelijkende OE-nummers staan als kolom in de tabellen en zijn doorzoekbaar.

Eerder beschreven catalogi:

- **Transportkoeling (editie 48)**: kies *merk → type koelunit* en zie de passende onderhouds- en filterpakketten,
  losse filters/riemen en overige onderdelen.
- **Trailerbouwdelen (2017)**: zoekboom *hoofdgroep → groep → subgroep (→ productlijn) → product*, met foto,
  maattekening, alle uitvoeringen en artikelnummers.

Overal met Wijlhuizen-artikelnummers, kopieerknop en link naar de webshop. Geen prijzen.

## Trailerbouwdelen

| | |
|---|---|
| Hoofdgroepen | 1 Hang- en sluitwerk · 2 Bovenbouw · 3 Onderbouw |
| Productgroepen | 24 groepen, 91 subgroepen (zoals in de inhoudsopgave van de catalogus) |
| Producten | 1.804 productblokken met 4.756 artikelregels (4.078 unieke artikelnummers) |
| Afbeeldingen | ~2.000 foto's en maattekeningen (WebP) |

- Zijbalk met de volledige boom; op telefoon inklapbaar.
- Subgroepen met productlijnen (bijv. Edscha Ultraline II, Kinnegrip K20, Roweko kisten) hebben filterknoppen.
- Zoeken op artikelnummer opent het product en markeert de juiste regel in de tabel.
- Bij elk product staat het catalogus-paginanummer, handig bij twijfel.

Controle: van de 4.765 artikelnummers in de PDF worden er 4.757 automatisch uitgelezen. Niet meegenomen
(staan los van een tabel in de PDF): 51.01.0592/0593 (blz. 159–160), 51.17.0001 (blz. 233), 51.08.0524/0567 (blz. 370),
51.05.0048 (blz. 461). Die kunnen handmatig in `data/trailerbouw.json` worden toegevoegd.

## Transportkoeling

| | |
|---|---|
| Merken | Carrier Transicold, Thermo King, Schmitz Cargobull |
| Types | 56 (MAXIMA, SUPRA, VECTOR, MD, SL, SLX, TS, T-serie, T.KM ONE) |
| Pakketten | 33 onderhoudspakketten + 12 filterpakketten, met inhoud en opties |
| Losse artikelen | 141 producten (filters, riemen, koppelingen, elektrisch, brandstof, accu's, koeltechniek, gereedschap, kleding, …) |
| Koudemiddeltabel | vulhoeveelheid per type aggregaat |

Functies:
- stap-voor-stap kiezen: merk → serie → type
- waarschuwing als een type meerdere uitvoeringen heeft (serienummer, bouwjaar, motor)
- zoeken op type, artikelnummer (ook zonder puntjes, bijv. `61010014`) of omschrijving
- per artikel: waar het in zit (welke pakketten en types)
- knop **Kopieer** (artikelnummer naar klembord) en **Webshop** (`wijlhuizenconnects.com`)
- geen prijzen (de catalogusprijzen uit 2021 zijn verouderd)
- werkt op telefoon, tablet en pc

## Insluiten op een website

Zet deze twee regels op de pagina waar de tool moet komen:

```html
<div id="wijlhuizen-transportkoeling"></div>
<script src="https://roelofpoth-svg.github.io/Wijlhuizenonderdelenzoeker/embed.js" async></script>
```

De tool wordt als iframe geladen en groeit automatisch mee in hoogte (geen dubbele scrollbalk).
Direct bij een merk, type of categorie beginnen kan met `data-start`, bijvoorbeeld:

```html
<div id="wijlhuizen-transportkoeling" data-start="#/merk/thermoking"></div>
<div id="wijlhuizen-transportkoeling" data-start="#/c/verlichting"></div>   <!-- direct in één catalogus -->
```

Alternatief zonder script: `<iframe src="https://roelofpoth-svg.github.io/Wijlhuizenonderdelenzoeker/" style="width:100%;height:1200px;border:0"></iframe>`.

Zie `voorbeeld-embed.html` voor een werkend voorbeeld.

### Directe links
Elke pagina heeft een eigen link die je kunt delen of in de webshop kunt plaatsen:

- `#/merk/carrier` – alle Carrier-types
- `#/type/carrier-supra-950` – alles voor de SUPRA 950
- `#/pakket/61.01.0008` – één pakket
- `#/zoek?q=46.51391` – zoekresultaat
- `#/onderdelen/filters` – categorie
- `#/koudemiddel` – koudemiddeltabel
- `#/c/<catalogus>` – een catalogus, bijv. `#/c/verlichting`, `#/c/koelingsdelen/n/daf`, `#/c/trailerbouw/p/51.02.0350`
- `#/trailer/...` – oude trailerbouwlinks blijven werken
- `#/koeling` – startpagina transportkoeling

## Hosten

Het is een statische site (HTML/CSS/JS + `data/catalogus.json`), zonder server of build-stap.
Elke webhost werkt: GitHub Pages, de eigen webserver, Netlify, enz.

**GitHub Pages:** Settings → Pages → *Deploy from a branch* → kies de branch en map `/ (root)`.
Let op: bij een privé-repository vereist GitHub Pages een betaald GitHub-abonnement; anders de repository
openbaar maken of de bestanden op de eigen webserver zetten.

## Instellingen

`config.js` bevat de webshoplink (`{artnr}` wordt vervangen door het artikelnummer).

## Data bijwerken

De data is automatisch uit de PDF-catalogus gehaald:

```bash
pip install pymupdf pillow
python3 tools/extract_catalogus.py catalogus.pdf /tmp/tk     # tekst, posities, foto's
pdftotext -f 71 -l 71 -layout catalogus.pdf /tmp/tk/p71.txt  # koudemiddeltabel
python3 tools/build_data.py /tmp/tk                          # -> data/catalogus.json + img/
```

Handmatige correcties staan in `tools/build_data.py` (zoek op `CORRECTIE`).

Trailerbouwdelen:

```bash
python3 tools/extract_trailerbouw.py trailerbouwdelen.pdf /tmp/tb   # blokken, tabellen, afbeeldingen
python3 tools/build_trailerbouw.py /tmp/tb                          # -> data/trailerbouw.json + img/tb/
``` Kleine wijzigingen
(artikel toevoegen, omschrijving aanpassen) kunnen ook direct in `data/catalogus.json`.

### Opvallend in de bron-catalogus
- `51.26.0018` staat zowel bij Flappengordijn "FIX" als "Side" (laatste i.c.m. rail 51.26.0021).
- Dichtingsring `31.11.1003` hoort bij zowel filterdroger 31.11.0002 als 31.11.0003.
- Filterpakketten `61.01.0038` en `61.01.0039` hebben dezelfde omschrijving; ze verschillen alleen in luchtfilter.

Overige catalogi (generiek, voor alle PDF's in de Wijlhuizen-huisstijl):

```bash
python3 tools/extract_generiek.py catalogus.pdf /tmp/cats/o_<bestandsnaam>   # per PDF
python3 tools/build_catalogi.py /tmp/cats                                   # -> data/catalogi/*.json + img/c/
```

De boomindeling per catalogus staat in `tools/build_catalogi.py` (`levels_for`). Een nieuwe catalogus toevoegen:
regel in `CATALOGI` erbij, eventueel een eigen `levels_for`-regel, en beide scripts draaien.

### Na een wijziging
Hoog in `index.html` het versienummer (`?v=...`) op bij `style.css`, `config.js`, `trailerbouw.js` en `app.js`.
Dan laden bezoekers meteen de nieuwe versie in plaats van een oude kopie uit de browsercache.
