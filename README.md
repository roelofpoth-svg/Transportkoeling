# Wijlhuizen Transportkoeling selector

Online selectietool die de papieren catalogus *Transportkoeling (editie 48)* vervangt.
Kies **merk → type koelunit** en zie direct de passende onderhoudspakketten, filterpakketten,
losse filters/riemen en overige onderdelen, met Wijlhuizen-artikelnummers, foto's en een link naar de webshop.

## Wat zit erin

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
<script src="https://<adres-van-de-tool>/embed.js" async></script>
```

De tool wordt als iframe geladen en groeit automatisch mee in hoogte (geen dubbele scrollbalk).
Direct bij een merk, type of categorie beginnen kan met `data-start`, bijvoorbeeld:

```html
<div id="wijlhuizen-transportkoeling" data-start="#/merk/thermoking"></div>
```

Alternatief zonder script: `<iframe src="https://<adres-van-de-tool>/" style="width:100%;height:1200px;border:0"></iframe>`.

Zie `voorbeeld-embed.html` voor een werkend voorbeeld.

### Directe links
Elke pagina heeft een eigen link die je kunt delen of in de webshop kunt plaatsen:

- `#/merk/carrier` – alle Carrier-types
- `#/type/carrier-supra-950` – alles voor de SUPRA 950
- `#/pakket/61.01.0008` – één pakket
- `#/zoek?q=46.51391` – zoekresultaat
- `#/onderdelen/filters` – categorie
- `#/koudemiddel` – koudemiddeltabel

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

Handmatige correcties staan in `tools/build_data.py` (zoek op `CORRECTIE`). Kleine wijzigingen
(artikel toevoegen, omschrijving aanpassen) kunnen ook direct in `data/catalogus.json`.

### Opvallend in de bron-catalogus
- `51.26.0018` staat zowel bij Flappengordijn "FIX" als "Side" (laatste i.c.m. rail 51.26.0021).
- Dichtingsring `31.11.1003` hoort bij zowel filterdroger 31.11.0002 als 31.11.0003.
- Filterpakketten `61.01.0038` en `61.01.0039` hebben dezelfde omschrijving; ze verschillen alleen in luchtfilter.
