/* Foto-zoeker server (Cloudflare Worker).
 * - bewaart de Anthropic API-sleutel (geheim, komt nooit in de browser)
 * - laat alleen medewerkers met een geldige toegangscode door
 * - geeft Claude de werkinstructie en het gereedschap; het zoeken zelf gebeurt in de browser
 *   (in de catalogusdata van de Onderdelenzoeker), de browser stuurt de zoekresultaten terug. */

const SYSTEM = `Je bent de Foto-zoeker van Wijlhuizen B.V. Truck & Trailerdelen. Je helpt de binnendienst om onderdelen te herkennen op foto's (vaak WhatsApp-foto's of screenshots van monteurs en klanten) en het juiste Wijlhuizen-artikelnummer (WH-nummer) te vinden in de Wijlhuizen catalogi.

Catalogi die je kunt doorzoeken: Transportkoeling (Carrier, Thermo King, Schmitz: pakketten en onderdelen per type), Trailerbouwdelen, Koelingsdelen, Truckschadedelen, Scania P/G/R, Verlichting, Elektra, Luchtremkoppelingen, Luchtbalgen, Aanhanger asdelen, Voertuig opbouw (o.a. JOST steunpoten, koppelingen), Laadklepdelen, Bevestigingsmaterialen, Werkplaats.

Werkwijze:
1. Bekijk alle foto's goed. Lees ALLE tekst letterlijk: typeplaatjes, artikelnummers, OE-nummers, merk, type, codes, maten, ingestempelde nummers. Een screenshot van een chat kan ook vraag/context bevatten (bijv. "mag ik deze 20x?").
2. Zoek met zoek_catalogus. Begin met letterlijke nummers en typecodes van de foto (ook zonder puntjes of in delen), daarna met merk + type, daarna met een omschrijving in het Nederlands (bijv. "luchtbalg BPW 30", "steunpoot JOST Modul", "spatscherm", "achterlicht Truck-Lite"). Doe gerust meerdere zoekopdrachten.
3. Gebruik bekijk_product om tabellen met maten en varianten te lezen en zo te kiezen tussen varianten (links/rechts, hoogte, aansluiting, voltage, enz.). Typecodes op plaatjes zijn vaak opgebouwd uit maten (bijv. JOST Modul B0302 = Modul B, montagehoogte-code 03, montageplaat-code 02).
4. Sluit ALTIJD af met geef_resultaat.

Harde regels:
- Noem als kandidaat ALLEEN WH-artikelnummers die letterlijk in de resultaten van zoek_catalogus of bekijk_product stonden. Verzin nooit een nummer.
- Staat het nummer of type van de foto niet letterlijk in de catalogi? Zeg dat eerlijk ("niet gevonden in de catalogi") en geef de letterlijke code als webshop_zoekterm, zodat de medewerker in de webshop zoekt (daar staan ook nieuwere artikelen). Stel dan geen vergelijkbaar artikel voor alsof het hetzelfde is; een alternatief mag alleen met zekerheid "laag" en met uitleg waarom het misschien past.
- Zekerheid: "hoog" = nummer/type letterlijk gevonden of eenduidig; "middel" = sterk vermoeden maar één gegeven ontbreekt; "laag" = alleen gelijkend.
- Kun je niet kiezen tussen varianten, geef dan de kandidaten en vraag in vervolgvraag precies welk gegeven nodig is (welke maat, waar te meten, welk nummer op het plaatje), kort en praktisch.
- Prijzen en levertijden weet je niet; daarvoor verwijs je naar de webshop.
- Antwoord altijd in het Nederlands, kort en zakelijk, zoals een collega aan de balie.`;

const TOOLS = [
  {
    name: 'zoek_catalogus',
    description: 'Zoek in alle Wijlhuizen catalogi op artikelnummer (WH), OE-nummer, merk, type of omschrijving (Nederlands). Geeft max. 25 regels: [ref] catalogus | titel | details. Gebruik de ref met bekijk_product.',
    input_schema: { type: 'object', properties: { zoekterm: { type: 'string', description: 'Bijv. "05.429.40.03.0", "OPT800", "luchtbalg BPW 30", "spatscherm"' } }, required: ['zoekterm'] },
  },
  {
    name: 'bekijk_product',
    description: 'Toon alle gegevens van één product of groep: tabellen met kolommen, maten, varianten en WH-artikelnummers.',
    input_schema: { type: 'object', properties: { ref: { type: 'string', description: 'De ref tussen [ ] uit zoek_catalogus, bijv. "#/c/luchtbalgen/p/33.412"' } }, required: ['ref'] },
  },
  {
    name: 'geef_resultaat',
    description: 'Geef het eindantwoord aan de medewerker. Altijd als laatste stap gebruiken.',
    input_schema: {
      type: 'object',
      properties: {
        samenvatting: { type: 'string', description: 'Wat je op de foto ziet en wat je gevonden hebt, 1-4 zinnen.' },
        kandidaten: {
          type: 'array', description: 'WH-artikelnummers die letterlijk in de zoekresultaten stonden, beste eerst. Leeg als niets gevonden.',
          items: {
            type: 'object',
            properties: {
              artnr: { type: 'string' },
              omschrijving: { type: 'string' },
              zekerheid: { type: 'string', enum: ['hoog', 'middel', 'laag'] },
              toelichting: { type: 'string', description: 'Waarom dit (of welke variant/maat).' },
            },
            required: ['artnr', 'zekerheid'],
          },
        },
        vervolgvraag: { type: 'string', description: 'Welk gegeven nog nodig is om zeker te kiezen (optioneel).' },
        webshop_zoekterm: { type: 'string', description: 'Letterlijke code/type van de foto om in de webshop te zoeken (optioneel).' },
      },
      required: ['samenvatting', 'kandidaten'],
    },
  },
];

const MAX_BODY = 25 * 1024 * 1024;

export default {
  async fetch(request, env) {
    const origin = request.headers.get('origin') || '';
    const allowed = String(env.TOEGESTANE_ORIGINS || '').split(',').map((s) => s.trim()).filter(Boolean);
    const okOrigin = allowed.includes(origin);
    const cors = okOrigin ? { 'access-control-allow-origin': origin, 'access-control-allow-headers': 'content-type, x-toegangscode', 'access-control-allow-methods': 'POST, OPTIONS', vary: 'origin' } : {};
    const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json', ...cors } });

    const url = new URL(request.url);
    if (url.pathname !== '/api/fotozoeker') return json({ error: 'niet gevonden' }, 404);
    if (request.method === 'OPTIONS') return new Response(null, { status: okOrigin ? 204 : 403, headers: cors });
    if (request.method !== 'POST') return json({ error: 'alleen POST' }, 405);
    if (!okOrigin) return json({ error: 'website niet toegestaan' }, 403);

    const codes = String(env.TOEGANGSCODES || '').split(',').map((s) => s.trim()).filter(Boolean);
    const code = request.headers.get('x-toegangscode') || '';
    if (!codes.length || !codes.includes(code)) return json({ error: 'toegangscode klopt niet' }, 401);
    if (!env.ANTHROPIC_API_KEY) return json({ error: 'server mist ANTHROPIC_API_KEY' }, 500);

    if (Number(request.headers.get('content-length') || 0) > MAX_BODY) return json({ error: 'te groot, stuur minder foto’s' }, 413);
    let body;
    try { body = await request.json(); } catch (_) { return json({ error: 'ongeldig verzoek' }, 400); }
    const messages = Array.isArray(body && body.messages) ? body.messages : null;
    if (!messages || !messages.length || messages.length > 80) return json({ error: 'ongeldig gesprek' }, 400);

    // cache op het laatste bericht: vervolgstappen in hetzelfde gesprek (met dezelfde foto's) worden zo goedkoper
    const msgs = structuredClone(messages);
    const last = msgs[msgs.length - 1];
    if (Array.isArray(last.content) && last.content.length) last.content[last.content.length - 1].cache_control = { type: 'ephemeral' };

    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({
        model: env.MODEL || 'claude-opus-5-5',
        max_tokens: 4096,
        system: [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }],
        tools: TOOLS,
        messages: msgs,
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return json({ error: (data.error && data.error.message) || `Claude antwoordde ${r.status}` }, 502);
    return json({ content: data.content || [], stop_reason: data.stop_reason, usage: data.usage });
  },
};
