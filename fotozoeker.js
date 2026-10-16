/* Foto-zoeker voor de binnendienst: chatvenster rechtsonder waarin je foto's en info gooit.
 * Claude kijkt naar de foto's en zoekt zelf in de catalogi van deze tool (zoeken gebeurt hier in de browser).
 * De verbinding met Claude loopt via een kleine eigen server (worker/fotozoeker-worker.js) die de API-sleutel
 * bewaart en de toegangscode van medewerkers controleert. Zie README, kopje "Foto-zoeker". */
(function () {
  'use strict';
  const CFG = window.TK_CONFIG || {};
  const API = (CFG.fotoZoekerApi || '').replace(/\/$/, '');
  const KEY = 'wh-fotozoeker-code';
  const MAX_FOTOS = 6, MAX_PX = 1568, MAX_STAPPEN = 14;
  const H = () => window.TKH;

  const store = {
    get() { try { return localStorage.getItem(KEY) || ''; } catch (_) { return ''; } },
    set(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (_) { /* privévenster */ } },
  };

  let root, list, form, txt, fileIn, thumbs, sendBtn;
  let pending = [];      // foto's die nog verstuurd moeten worden: {data, type, url}
  let messages = [];     // gesprek in API-vorm
  let busy = false;

  const ICON = {
    cam: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 3 7.2 5H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3.2L15 3H9Zm3 5a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m6.4 5 5.6 5.6L17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6l5.6-5.6L5 6.4 6.4 5Z"/></svg>',
    clip: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.5 6.5v10a4.5 4.5 0 0 1-9 0V6a3 3 0 0 1 6 0v9.5a1.5 1.5 0 0 1-3 0V7H9v8.5a3 3 0 0 0 6 0V6a4.5 4.5 0 0 0-9 0v10.5a6 6 0 0 0 12 0v-10h-1.5Z"/></svg>',
    big: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M14 3h7v7h-2V6.4l-5.3 5.3-1.4-1.4L17.6 5H14V3ZM3 14h2v3.6l5.3-5.3 1.4 1.4L6.4 19H10v2H3v-7Z"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M2 21 23 12 2 3v7l15 2-15 2v7Z"/></svg>',
  };

  /* ---------- opbouw ---------- */
  function build() {
    if (root) return;
    root = document.createElement('div');
    root.className = 'fz';
    root.innerHTML = `
      <button class="fz-launch" type="button" aria-label="Foto-zoeker openen" title="Foto-zoeker: onderdeel herkennen op foto">${ICON.cam}</button>
      <section class="fz-panel" role="dialog" aria-label="Foto-zoeker" hidden>
        <header class="fz-head">
          <img class="fz-av" src="assets/beeldmerk.png" alt="">
          <div class="fz-ttl"><b>Foto-zoeker</b><span>Binnendienst · onderdeel herkennen</span></div>
          <button type="button" class="fz-new" title="Nieuw gesprek">Nieuw</button>
          <button type="button" class="fz-big" aria-label="Groter of kleiner venster" title="Groter / kleiner">${ICON.big}</button>
          <button type="button" class="fz-x" aria-label="Sluiten">${ICON.close}</button>
        </header>
        <div class="fz-list" aria-live="polite"></div>
        <form class="fz-form">
          <div class="fz-thumbs"></div>
          <div class="fz-row">
            <label class="fz-attach" title="Foto's toevoegen">${ICON.clip}<input type="file" accept="image/*" multiple hidden></label>
            <textarea rows="1" placeholder="Foto's plakken of info typen…" aria-label="Bericht"></textarea>
            <button class="fz-send" type="submit" aria-label="Versturen">${ICON.send}</button>
          </div>
        </form>
      </section>`;
    document.body.appendChild(root);
    list = root.querySelector('.fz-list');
    form = root.querySelector('.fz-form');
    txt = root.querySelector('textarea');
    fileIn = root.querySelector('input[type=file]');
    thumbs = root.querySelector('.fz-thumbs');
    sendBtn = root.querySelector('.fz-send');

    root.querySelector('.fz-launch').addEventListener('click', () => toggle(true));
    root.querySelector('.fz-x').addEventListener('click', () => toggle(false));
    root.querySelector('.fz-new').addEventListener('click', reset);
    root.querySelector('.fz-big').addEventListener('click', () => root.classList.toggle('big'));
    fileIn.addEventListener('change', () => { addFiles(fileIn.files); fileIn.value = ''; });
    form.addEventListener('submit', (e) => { e.preventDefault(); send(); });
    txt.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    txt.addEventListener('input', grow);
    const panel = root.querySelector('.fz-panel');
    panel.addEventListener('paste', (e) => {
      const files = [...(e.clipboardData || {}).files || []].filter((f) => f.type.startsWith('image/'));
      if (files.length) { e.preventDefault(); addFiles(files); }
    });
    panel.addEventListener('dragover', (e) => { e.preventDefault(); panel.classList.add('drag'); });
    panel.addEventListener('dragleave', (e) => { if (!panel.contains(e.relatedTarget)) panel.classList.remove('drag'); });
    panel.addEventListener('drop', (e) => { e.preventDefault(); panel.classList.remove('drag'); addFiles(e.dataTransfer.files); });
    thumbs.addEventListener('click', (e) => {
      const b = e.target.closest('[data-rm]');
      if (b) { pending.splice(+b.dataset.rm, 1); drawThumbs(); }
    });
    root.querySelector('.fz-list').addEventListener('click', (e) => {
      const a = e.target.closest('a[href^="#/"]');
      if (a && window.matchMedia('(max-width: 600px)').matches) toggle(false);
    });
    greet();
  }

  function greet() {
    list.innerHTML = '';
    if (!API) return bot(`<p><b>Nog niet gekoppeld.</b> De Foto-zoeker heeft een eigen server met een Anthropic API-sleutel nodig. Zie de README (kopje “Foto-zoeker”) en vul daarna <code>fotoZoekerApi</code> in <code>config.js</code> in.</p>`);
    if (!store.get()) return askCode();
    bot(`<p>Stuur een of meer foto's van het onderdeel (typeplaatje, nummers, het hele deel) en zet erbij wat je weet: merk, waar het zit, maten. Ik zoek het op in de catalogi.</p>`);
  }

  function askCode(msg) {
    const el = bot(`<p>${msg || 'Alleen voor medewerkers. Vul de toegangscode in.'}</p>
      <form class="fz-code"><input type="password" autocomplete="current-password" placeholder="Toegangscode" aria-label="Toegangscode"><button class="btn small" type="submit">Opslaan</button></form>`);
    const f = el.querySelector('form');
    f.addEventListener('submit', (e) => {
      e.preventDefault();
      const v = f.querySelector('input').value.trim();
      if (!v) return;
      store.set(v);
      showLauncher();
      greet();
    });
    setTimeout(() => f.querySelector('input').focus(), 30);
  }

  function toggle(open) {
    build();
    root.classList.toggle('open', open);
    root.querySelector('.fz-panel').hidden = !open;
    if (open) setTimeout(() => (root.querySelector('.fz-code input') || txt).focus(), 30);
  }
  function showLauncher() { build(); root.classList.add('on'); }

  function reset() {
    if (busy) return;
    messages = []; pending = []; drawThumbs(); txt.value = ''; grow();
    greet();
  }

  function grow() { txt.style.height = 'auto'; txt.style.height = Math.min(txt.scrollHeight, 120) + 'px'; }

  /* ---------- berichten in het venster ---------- */
  function bubble(cls, html) {
    const d = document.createElement('div');
    d.className = `fz-msg ${cls}`;
    d.innerHTML = html;
    list.appendChild(d);
    list.scrollTop = list.scrollHeight;
    return d;
  }
  const bot = (html) => bubble('bot', html);

  /* ---------- foto's ---------- */
  function addFiles(files) {
    const imgs = [...files].filter((f) => f.type.startsWith('image/'));
    imgs.slice(0, MAX_FOTOS - pending.length).forEach((f) => shrink(f).then((p) => { pending.push(p); drawThumbs(); }).catch(() => H().toast(`${f.name} kon niet worden gelezen`)));
    if (pending.length + imgs.length > MAX_FOTOS) H().toast(`Maximaal ${MAX_FOTOS} foto's per bericht`);
  }
  // verkleinen tot max. 1568 px (meer gebruikt Claude toch niet) en als JPEG versturen
  function shrink(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const im = new Image();
      im.onload = () => {
        const s = Math.min(1, MAX_PX / Math.max(im.naturalWidth, im.naturalHeight));
        const c = document.createElement('canvas');
        c.width = Math.round(im.naturalWidth * s); c.height = Math.round(im.naturalHeight * s);
        const g = c.getContext('2d');
        g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
        g.drawImage(im, 0, 0, c.width, c.height);
        const du = c.toDataURL('image/jpeg', 0.85);
        URL.revokeObjectURL(url);
        resolve({ type: 'image/jpeg', data: du.split(',')[1], url: du });
      };
      im.onerror = () => { URL.revokeObjectURL(url); reject(new Error('afbeelding')); };
      im.src = url;
    });
  }
  function drawThumbs() {
    const { esc } = H();
    thumbs.innerHTML = pending.map((p, i) => `<span class="fz-thumb"><img src="${esc(p.url)}" alt="Foto ${i + 1}"><button type="button" data-rm="${i}" aria-label="Foto ${i + 1} weghalen">×</button></span>`).join('');
  }

  /* ---------- gereedschap dat Claude hier in de browser laat uitvoeren ---------- */
  const TOOLS = {
    zoek_catalogus({ zoekterm }) {
      const res = H().search(String(zoekterm || '')).slice(0, 25);
      if (!res.length) return `Geen resultaten voor "${zoekterm}". Probeer een kortere of andere term (bijv. alleen het typenummer, of een omschrijving).`;
      return res.map((r) => `[${r.href}] ${r.kind} | ${r.title} | ${r.sub}`).join('\n');
    },
    bekijk_product({ ref }) {
      return H().detailText(ref, 150) || `Onbekende ref "${ref}". Gebruik een ref tussen [ ] uit zoek_catalogus.`;
    },
  };
  const toolLabel = (name, inp) => name === 'zoek_catalogus' ? `Zoekt: “${inp.zoekterm}”` : name === 'bekijk_product' ? 'Bekijkt productgegevens' : '';

  /* ---------- versturen + gesprekslus ---------- */
  async function send() {
    if (busy || !API) return;
    const code = store.get();
    if (!code) return askCode();
    const text = txt.value.trim();
    if (!text && !pending.length) return;
    const { esc } = H();
    const content = pending.map((p) => ({ type: 'image', source: { type: 'base64', media_type: p.type, data: p.data } }));
    content.push({ type: 'text', text: text || '(alleen foto’s, geen toelichting)' });
    bubble('me', `${pending.map((p) => `<img src="${esc(p.url)}" alt="">`).join('')}${text ? `<p>${esc(text)}</p>` : ''}`);
    pending = []; drawThumbs(); txt.value = ''; grow();
    messages.push({ role: 'user', content });

    busy = true; sendBtn.disabled = true;
    const work = bot('<div class="fz-steps"><span class="fz-dot"></span> Bekijkt de foto’s…</div>');
    const steps = work.querySelector('.fz-steps');
    const step = (t) => { const s = document.createElement('div'); s.textContent = t; steps.appendChild(s); list.scrollTop = list.scrollHeight; };
    try {
      if (window.CAT && !window.CAT.isLoaded()) await window.CAT.ensureAll();
      for (let i = 0; i < MAX_STAPPEN; i++) {
        const resp = await callApi(code, messages);
        messages.push({ role: 'assistant', content: resp.content });
        const uses = resp.content.filter((b) => b.type === 'tool_use');
        const final = uses.find((u) => u.name === 'geef_resultaat');
        if (final) {
          work.remove();
          renderResult(final.input);
          // het gesprek moet geldig blijven voor een vervolgvraag: elke tool_use krijgt een antwoord
          messages.push({ role: 'user', content: uses.map((u) => ({ type: 'tool_result', tool_use_id: u.id, content: u === final ? 'Getoond aan de medewerker.' : 'Overgeslagen.' })) });
          break;
        }
        if (!uses.length) {
          work.remove();
          const t = resp.content.filter((b) => b.type === 'text').map((b) => b.text).join('\n').trim();
          bot(`<p>${esc(t || 'Geen antwoord ontvangen.').replace(/\n/g, '<br>')}</p>`);
          break;
        }
        const results = uses.map((u) => {
          step(toolLabel(u.name, u.input || {}));
          let out;
          try { out = TOOLS[u.name] ? TOOLS[u.name](u.input || {}) : `Onbekend gereedschap ${u.name}`; } catch (e) { out = `Fout: ${e.message}`; }
          return { type: 'tool_result', tool_use_id: u.id, content: String(out).slice(0, 20000) };
        });
        messages.push({ role: 'user', content: results });
        if (i === MAX_STAPPEN - 1) { work.remove(); bot('<p>Ik kom er niet uit binnen het aantal zoekstappen. Stuur een extra foto of meer info (maten, nummers, waar het zit).</p>'); }
      }
    } catch (e) {
      work.remove();
      // het onbeantwoorde bericht weer uit het gesprek halen zodat opnieuw proberen kan
      while (messages.length && messages[messages.length - 1].role !== 'user') messages.pop();
      messages = trimToLastComplete(messages);
      if (e.status === 401) { store.set(''); askCode('Toegangscode klopt niet. Probeer opnieuw.'); }
      else bot(`<p class="fz-err">Er ging iets mis: ${esc(e.message)}. Probeer het opnieuw.</p>`);
    } finally {
      busy = false; sendBtn.disabled = false;
    }
  }
  // gesprek terugzetten tot het laatste afgeronde antwoord (na een fout)
  function trimToLastComplete(msgs) {
    for (let i = msgs.length - 1; i >= 0; i--) {
      const m = msgs[i];
      if (m.role === 'user' && m.content.every((b) => b.type === 'tool_result') && msgs[i - 1] && msgs[i - 1].content.some((b) => b.type === 'tool_use' && b.name === 'geef_resultaat')) return msgs.slice(0, i + 1);
    }
    return [];
  }

  async function callApi(code, msgs) {
    const r = await fetch(`${API}/api/fotozoeker`, {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-toegangscode': code },
      body: JSON.stringify({ messages: msgs }),
    });
    let j = null; try { j = await r.json(); } catch (_) { /* geen JSON */ }
    if (!r.ok) { const e = new Error((j && j.error) || `server antwoordde ${r.status}`); e.status = r.status; throw e; }
    return j;
  }

  /* ---------- resultaat tonen ---------- */
  const ZEKER = { hoog: 'Zeker', middel: 'Waarschijnlijk', laag: 'Mogelijk' };
  function renderResult(r) {
    const { esc, img, webshopLink, copyBtn } = H();
    const cands = Array.isArray(r.kandidaten) ? r.kandidaten : [];
    const shop = (CFG.webshopUrl || '').replace('{artnr}', encodeURIComponent(r.webshop_zoekterm || ''));
    const cards = cands.map((k) => {
      const a = String(k.artnr || '').trim();
      const hit = a && H().artLookup(a);
      const z = ZEKER[k.zekerheid] || 'Mogelijk';
      return `<div class="fz-cand${hit ? '' : ' unknown'}">
        ${hit && hit.img ? `<a href="${esc(hit.href)}" class="fz-ci">${img(hit.img, hit.title)}</a>` : '<span class="fz-ci"></span>'}
        <div class="fz-cb">
          <div class="fz-ct"><b>${esc(a)}</b> <span class="fz-z z-${esc(k.zekerheid || 'laag')}">${z}</span></div>
          <div class="fz-cn">${esc(hit ? hit.title : (k.omschrijving || ''))}${hit && hit.sub ? ` · <span>${esc(hit.sub)}</span>` : ''}</div>
          ${k.toelichting ? `<div class="fz-cr">${esc(k.toelichting)}</div>` : ''}
          ${hit ? '' : '<div class="fz-warn">Niet gevonden in de catalogi: controleer dit nummer.</div>'}
          <div class="fz-ca">${hit ? `<a class="btn small ghost" href="${esc(hit.href)}">Bekijk</a>` : ''}${a ? webshopLink(a, true) + copyBtn(a) : ''}</div>
        </div></div>`;
    }).join('');
    bot(`${r.samenvatting ? `<p>${esc(r.samenvatting).replace(/\n/g, '<br>')}</p>` : ''}
      ${cards ? `<div class="fz-cands">${cards}</div>` : ''}
      ${r.webshop_zoekterm && shop ? `<p class="fz-shop">Zoek ook in de webshop: <a href="${esc(shop)}" target="_blank" rel="noopener">${esc(r.webshop_zoekterm)}</a></p>` : ''}
      ${r.vervolgvraag ? `<p class="fz-q">${esc(r.vervolgvraag)}</p>` : ''}`);
  }

  /* ---------- start ---------- */
  function page() {
    // #/foto: medewerkers openen hiermee het venster (en vullen de code in); daarna blijft het rondje zichtbaar
    showLauncher();
    toggle(true);
    history.replaceState(null, '', '#/');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }

  window.FOTO = { page, open: () => toggle(true) };
  document.addEventListener('DOMContentLoaded', () => { if (store.get() || CFG.fotoZoekerAltijdTonen) showLauncher(); });
  if (document.readyState !== 'loading' && (store.get() || CFG.fotoZoekerAltijdTonen)) setTimeout(showLauncher, 0);
})();
