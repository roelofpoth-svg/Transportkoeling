/* Wijlhuizen Transportkoeling selectietool — statische single-page app, geen build-stap nodig. */
(function () {
  'use strict';

  const CFG = Object.assign({ webshopUrl: '', webshopLabel: 'Bekijk in webshop', webshopNewTab: true }, window.TK_CONFIG || {});
  const app = document.getElementById('app');
  const crumbs = document.getElementById('crumbs');
  const searchForm = document.getElementById('search');
  const searchInput = document.getElementById('q');
  const toastEl = document.getElementById('toast');
  const EMBEDDED = window.self !== window.top;

  let D; // catalogusdata
  const byModel = {}, byMake = {}, byArt = {}, partById = {}, pkgById = {}, catById = {};

  /* ---------- hulpfuncties ---------- */
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const compact = (s) => norm(s).replace(/[^a-z0-9]/g, '');
  const enc = encodeURIComponent;
  const natural = (a, b) => a.localeCompare(b, 'nl', { numeric: true, sensitivity: 'base' });

  const ICON = {
    cart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5.2 4l.6 3H21l-2.2 8.2a2 2 0 0 1-1.9 1.5H8.4a2 2 0 0 1-2-1.6L4.1 2H1V0h4.8l.4 2"/></svg>',
    copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1Zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Zm0 16H8V7h11v14Z"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M11 7h2v2h-2V7Zm0 4h2v6h-2v-6Zm1-9a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Z"/></svg>',
  };

  function webshopLink(artnr, small) {
    if (!CFG.webshopUrl) return '';
    const url = CFG.webshopUrl.replace('{artnr}', enc(artnr));
    const target = CFG.webshopNewTab ? ' target="_blank" rel="noopener"' : '';
    return `<a class="btn${small ? ' small' : ''}" href="${esc(url)}"${target} title="${esc(CFG.webshopLabel)}: ${esc(artnr)}">${ICON.cart}<span>${small ? 'Webshop' : esc(CFG.webshopLabel)}</span></a>`;
  }
  function copyBtn(artnr) {
    return `<button class="btn ghost icon" type="button" data-copy="${esc(artnr)}" title="Kopieer ${esc(artnr)}" aria-label="Kopieer artikelnummer ${esc(artnr)}">${ICON.copy}</button>`;
  }
  const img = (src, alt, cls) => src ? `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy"${cls ? ` class="${cls}"` : ''}>` : '';
  const modelUrl = (m) => `#/type/${enc(m.id)}`;
  const makeName = (id) => (D.makes.find((m) => m.id === id) || {}).name || id;

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => toastEl.classList.remove('show'), 1600);
  }

  /* ---------- index opbouwen ---------- */
  function indexData() {
    D.models.forEach((m) => { byModel[m.id] = m; (byMake[m.make] = byMake[m.make] || []).push(m); });
    D.categories.forEach((c) => { catById[c.id] = c; });
    const addArt = (artnr, entry) => { (byArt[artnr] = byArt[artnr] || []).push(entry); };
    D.packages.forEach((p) => {
      pkgById[p.id] = p;
      addArt(p.artnr, { kind: 'package', pkg: p });
      p.items.forEach((it) => addArt(it.artnr, { kind: 'item', pkg: p, item: it }));
    });
    D.parts.forEach((q) => {
      partById[q.id] = q;
      q.variants.forEach((v) => addArt(v.artnr, { kind: 'part', part: q, variant: v }));
    });
  }

  const packagesFor = (modelId) => D.packages.filter((p) => p.fits.some((f) => f.model === modelId));
  const partsFor = (modelId) => D.parts.filter((q) => q.fits.some((f) => f.model === modelId));
  const genericPartsFor = (make) => D.parts.filter((q) => q.makes.includes(make) && !q.fits.length);
  const modelsOfPkg = (p) => p.fits.map((f) => byModel[f.model]).filter(Boolean);

  /* ---------- weergave-onderdelen ---------- */
  function setCrumbs(list) {
    if (list[0] && list[0][0] === 'Transportkoeling') list = [['Catalogus', '#/'], ['Transportkoeling', '#/koeling'], ...list.slice(1)];
    else if (list[0] && list[0][0] !== 'Catalogus') list = [['Catalogus', '#/'], ...list];
    crumbs.innerHTML = list.map((c, i) => (i < list.length - 1 && c[1]
      ? `<a href="${c[1]}">${esc(c[0])}</a><span class="sep">›</span>` : `<span>${esc(c[0])}</span>`)).join('');
  }

  function stepper(n) {
    const s = ['Kies merk', 'Kies type', 'Bekijk onderdelen'];
    return `<div class="steps" aria-hidden="true">${s.map((t, i) => `<span class="step${i < n ? ' on' : ''}"><b>${i + 1}</b>${t}</span>`).join('')}</div>`;
  }

  function itemRow(it) {
    const known = byArt[it.artnr] && byArt[it.artnr].some((e) => e.kind === 'part');
    return `<li class="item">
      ${it.img ? img(it.img, it.name, 'thumb') : '<span></span>'}
      <div>
        <div class="i-name"><a href="#/artikel/${enc(it.artnr)}">${esc(it.name)}</a></div>
        <div class="i-meta"><span class="artnr">${esc(it.artnr)}</span>${it.brand ? ` · ${esc(it.brand)}` : ''}${known ? ' · ook los in catalogus' : ''}</div>
      </div>
      <div class="i-actions">${copyBtn(it.artnr)}${webshopLink(it.artnr, true)}</div>
    </li>`;
  }

  function packageCard(p, modelId) {
    const fit = modelId ? p.fits.find((f) => f.model === modelId) : null;
    const cond = fit && fit.condition;
    const base = p.items.filter((i) => !i.optional), opt = p.items.filter((i) => i.optional);
    return `<article class="card pkg" id="pkg-${esc(p.id)}">
      <div class="pkg-head">
        <h3>${esc(p.type)}</h3>
        <div class="actions">${copyBtn(p.artnr)}${webshopLink(p.artnr)}</div>
        <div class="pkg-cond">
          <div class="artnr-big">art.nr. ${esc(p.artnr)}</div>
          ${cond ? `<p style="margin:8px 0 0"><span class="badge warn">${ICON.info} Let op: ${esc(cond)}</span></p>` : ''}
          <p class="fits" style="margin-top:8px">${esc(makeName(p.make))}: ${esc(p.fitsText)}</p>
        </div>
      </div>
      ${p.img ? `<div class="pkg-photo">${img(p.img, p.type + ' ' + p.artnr)}</div>` : ''}
      <div class="pkg-body">
        <div class="set-label">Inhoud set (${base.length})</div>
        <ul class="items">${base.map(itemRow).join('')}</ul>
        ${opt.length ? `<div class="set-label">Optie</div><ul class="items">${opt.map(itemRow).join('')}</ul>` : ''}
        ${p.note ? `<p class="pkg-note">${esc(p.note)}</p>` : ''}
      </div>
    </article>`;
  }

  function partCard(q, modelId) {
    const fit = modelId ? q.fits.find((f) => f.model === modelId) : null;
    const variants = q.variants.map((v) => `<div class="variant">
        <span><span class="artnr">${esc(v.artnr)}</span>${v.label ? ` <span class="v-label">· ${esc(v.label)}</span>` : ''}${v.note ? `<br><span class="v-label">${esc(v.note)}</span>` : ''}</span>
        <span class="actions">${copyBtn(v.artnr)}${webshopLink(v.artnr, true)}</span>
      </div>`).join('');
    return `<article class="card part">
      <a class="part-img" href="#/onderdeel/${enc(q.id)}" tabindex="-1" aria-hidden="true">${img(q.img, q.title)}</a>
      <div class="part-body">
        <h3 class="part-title"><a href="#/onderdeel/${enc(q.id)}">${esc(q.title)}</a></h3>
        ${fit && fit.condition ? `<span class="badge warn">${esc(fit.condition)}</span>` : ''}
        <ul class="specs compact">${q.specs.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
        <div class="variants">${variants}</div>
      </div>
    </article>`;
  }

  function partsByCategory(list, modelId) {
    const groups = {};
    list.forEach((q) => { (groups[q.category] = groups[q.category] || []).push(q); });
    return D.categories.filter((c) => groups[c.id]).map((c) =>
      `<div class="cat-title">${esc(c.name)}</div><div class="grid parts">${groups[c.id].map((q) => partCard(q, modelId)).join('')}</div>`).join('');
  }

  /* ---------- pagina's ---------- */
  function pageCatalogs() {
    setCrumbs([['Catalogus']]);
    const tb = window.TB && window.TB.stats();
    app.innerHTML = `
      <h1>Welke onderdelen zoek je?</h1>
      <p class="lead">Kies een catalogus, of zoek direct op artikelnummer, type of omschrijving in alle catalogi via de zoekbalk bovenaan.</p>
      <div class="grid catalogs">
        <a class="card catalog" href="#/koeling">
          <div class="cat-kicker">Catalogus</div>
          <div class="make-name">Transportkoeling</div>
          <p class="make-series">Onderhouds- en filterpakketten, filters, riemen en onderdelen voor Carrier Transicold, Thermo King en Schmitz. Zoek per merk en type koelunit.</p>
          <p class="cat-stats">${D.models.length} types · ${D.packages.length} pakketten · ${D.parts.length} onderdelen</p>
          <span class="make-go">Naar transportkoeling ›</span>
        </a>
        <a class="card catalog" href="#/trailer">
          <div class="cat-kicker">Catalogus</div>
          <div class="make-name">Trailerbouwdelen</div>
          <p class="make-series">Hang- en sluitwerk, bovenbouw en onderbouw: scharnieren, sluitingen, ladingzekering, schuifzeilen en -daken, rongen, markering, spatschermen, kisten en meer.</p>
          <p class="cat-stats">${tb ? `${tb.subs} productgroepen · ${tb.products} producten · ${tb.articles} artikelnummers` : 'Laden…'}</p>
          <span class="make-go">Naar trailerbouwdelen ›</span>
        </a>
      </div>`;
  }

  function pageHome() {
    setCrumbs([['Transportkoeling']]);
    const makes = D.makes.map((mk) => {
      const ms = byMake[mk.id] || [];
      const series = [...new Set(ms.map((m) => m.series))];
      return `<a class="card make" href="#/merk/${mk.id}">
        <div class="make-name">${esc(mk.name)}</div>
        <p class="make-series">${ms.length} types · ${esc(series.join(', '))}</p>
        <span class="make-go">Kies type ›</span>
      </a>`;
    }).join('');
    const cats = D.categories.map((c) => {
      const n = D.parts.filter((q) => q.category === c.id).length;
      return n ? `<a class="card tile" href="#/onderdelen/${c.id}"><div class="tile-name">${esc(c.name)}</div><div class="tile-sub">${n} artikelen</div></a>` : '';
    }).join('');
    app.innerHTML = `
      ${stepper(0)}
      <h1>Welke koelunit heeft de klant?</h1>
      <p class="lead">Kies het merk en het type koelaggregaat. Je ziet direct de passende onderhouds- en filterpakketten, de losse filters en riemen, en overige onderdelen. Zoek je een artikelnummer of type? Gebruik dan de zoekbalk bovenaan.</p>
      <div class="grid makes" style="margin-top:18px">${makes}</div>
      <h2>Losse onderdelen &amp; toebehoren</h2>
      <div class="grid tiles">${cats}
        <a class="card tile" href="#/koudemiddel"><div class="tile-name">Koudemiddel volumes</div><div class="tile-sub">Per type aggregaat</div></a>
      </div>`;
  }

  function pageMake(makeId, series) {
    const mk = D.makes.find((m) => m.id === makeId);
    if (!mk) return pageNotFound();
    setCrumbs([['Transportkoeling', '#/'], [mk.name]]);
    const ms = byMake[makeId] || [];
    const allSeries = [...new Set(ms.map((m) => m.series))];
    const active = allSeries.includes(series) ? series : '';
    const tabs = allSeries.length > 1 ? `<div class="series-tabs" role="group" aria-label="Serie">
        <a class="chip${active ? '' : ' on'}" href="#/merk/${makeId}">Alle series</a>
        ${allSeries.map((s) => `<a class="chip${s === active ? ' on' : ''}" href="#/merk/${makeId}/${enc(s)}">${esc(s)}</a>`).join('')}
      </div>` : '';
    const shown = active ? [active] : allSeries;
    const blocks = shown.map((s) => {
      const list = ms.filter((m) => m.series === s).sort((a, b) => natural(a.name, b.name));
      return `${shown.length > 1 ? `<div class="series-label">${esc(s)}</div>` : ''}
        <div class="grid models">${list.map((m) => {
          const np = packagesFor(m.id).length, nq = partsFor(m.id).length;
          const sub = [np ? `${np} pakket${np > 1 ? 'ten' : ''}` : '', nq ? `${nq} onderdel${nq > 1 ? 'en' : ''}` : ''].filter(Boolean).join(' · ');
          return `<a class="card model-btn" href="${modelUrl(m)}"><div class="m-name">${esc(m.name)}</div><div class="m-sub">${sub || 'onderdelen'}</div></a>`;
        }).join('')}</div>`;
    }).join('');
    const generic = genericPartsFor(makeId).length;
    app.innerHTML = `
      ${stepper(1)}
      <h1>${esc(mk.name)}</h1>
      <p class="lead">Kies het type koelunit. Staat het type er niet tussen? Bekijk dan de <a href="#/merk-onderdelen/${makeId}">${generic} algemene ${esc(mk.name)}-onderdelen</a> of zoek op artikelnummer.</p>
      ${tabs}${blocks}`;
  }

  function pageModel(modelId) {
    const m = byModel[modelId];
    if (!m) return pageNotFound();
    const mk = makeName(m.make);
    setCrumbs([['Transportkoeling', '#/'], [mk, `#/merk/${m.make}`], [m.series, `#/merk/${m.make}/${enc(m.series)}`], [m.name]]);
    const pkgs = packagesFor(modelId);
    const onderhoud = pkgs.filter((p) => /onderhoud/i.test(p.type));
    const filter = pkgs.filter((p) => !/onderhoud/i.test(p.type));
    const specific = partsFor(modelId);
    const generic = genericPartsFor(m.make);
    const conds = (list) => new Set(list.map((p) => (p.fits.find((f) => f.model === modelId) || {}).condition || '')).size > 1;
    const needsChoice = conds(onderhoud) || conds(filter) || filter.length > 1 || onderhoud.length > 1;
    const facts = [
      `<div class="fact">Merk<b>${esc(mk)}</b></div>`,
      `<div class="fact">Serie<b>${esc(m.series)}</b></div>`,
      ...(m.refrigerant || []).map((r) => `<div class="fact">Koudemiddel<b>${esc(r.refrigerant)} · ${esc(r.kg)} kg</b></div>`),
    ].join('');
    app.innerHTML = `
      ${stepper(3)}
      <div class="type-head">
        <div><h1>${esc(m.name)}</h1><p class="lead">${esc(mk)} koelunit</p></div>
        <div class="facts">${facts}</div>
      </div>
      ${needsChoice ? `<div class="notice">${ICON.info}<div>Voor dit type zijn meerdere uitvoeringen. Kies op basis van <b>serienummer, bouwjaar of motoruitvoering</b> (zie de oranje labels), of vraag het typeplaatje van de unit op.</div></div>` : ''}
      ${onderhoud.length ? `<h2>Onderhoudspakketten <span class="count">${onderhoud.length}</span></h2><div class="grid packages">${onderhoud.map((p) => packageCard(p, modelId)).join('')}</div>` : ''}
      ${filter.length ? `<h2>Filterpakketten <span class="count">${filter.length}</span></h2><div class="grid packages">${filter.map((p) => packageCard(p, modelId)).join('')}</div>` : ''}
      ${specific.length ? `<h2>Onderdelen voor ${esc(m.name)} <span class="count">${specific.length}</span></h2><div class="grid parts">${specific.map((q) => partCard(q, modelId)).join('')}</div>` : ''}
      ${!pkgs.length && !specific.length ? `<div class="notice">${ICON.info}<div>Voor dit type staan geen pakketten in de catalogus. Bekijk hieronder de algemene ${esc(mk)}-onderdelen.</div></div>` : ''}
      ${generic.length ? `<details class="more"${!pkgs.length && !specific.length ? ' open' : ''}><summary>Overige ${esc(mk)}-onderdelen <span class="count">${generic.length}</span></summary>
        <div class="more-body"><p class="lead" style="margin-top:12px">Deze onderdelen zijn geschikt voor ${esc(mk)}, maar zonder vast type in de catalogus. Controleer de specificaties (maten, spanning, draadmaat).</p>${partsByCategory(generic, modelId)}</div></details>` : ''}`;
  }

  function pageMakeParts(makeId) {
    const mk = D.makes.find((m) => m.id === makeId);
    if (!mk) return pageNotFound();
    setCrumbs([['Transportkoeling', '#/'], [mk.name, `#/merk/${makeId}`], ['Algemene onderdelen']]);
    const list = genericPartsFor(makeId);
    app.innerHTML = `<h1>${esc(mk.name)}: algemene onderdelen</h1>
      <p class="lead">Onderdelen voor ${esc(mk.name)} zonder vast type in de catalogus. Controleer de specificaties.</p>${partsByCategory(list)}`;
  }

  function pageParts(catId) {
    const cat = catById[catId];
    setCrumbs([['Transportkoeling', '#/'], ['Onderdelen', cat ? '#/onderdelen' : null], ...(cat ? [[cat.name]] : [])]);
    const chips = `<div class="cats">${[`<a class="chip${cat ? '' : ' on'}" href="#/onderdelen">Alle</a>`,
      ...D.categories.filter((c) => D.parts.some((q) => q.category === c.id))
        .map((c) => `<a class="chip${cat && cat.id === c.id ? ' on' : ''}" href="#/onderdelen/${c.id}">${esc(c.name)}</a>`)].join('')}</div>`;
    const list = cat ? D.parts.filter((q) => q.category === cat.id) : D.parts;
    app.innerHTML = `<h1>${cat ? esc(cat.name) : 'Alle onderdelen'}</h1>${chips}
      ${cat ? `<div class="grid parts" style="margin-top:14px">${list.map((q) => partCard(q)).join('')}</div>` : partsByCategory(list)}`;
  }

  function usedInHtml(artnr, exceptPkg) {
    const uses = (byArt[artnr] || []).filter((e) => e.kind === 'item' && e.pkg.id !== exceptPkg);
    if (!uses.length) return '';
    const models = new Map();
    uses.forEach((u) => modelsOfPkg(u.pkg).forEach((m) => models.set(m.id, m)));
    return `<div class="used-in"><h2 style="margin-top:20px">Zit in ${uses.length} pakket${uses.length > 1 ? 'ten' : ''}</h2>
      <div class="table-wrap"><table class="vt"><thead><tr><th>Pakket</th><th>Art.nr.</th><th>Geschikt voor</th></tr></thead><tbody>
      ${uses.map((u) => `<tr><td><a href="#/pakket/${enc(u.pkg.id)}">${esc(u.pkg.type)}</a>${u.item.optional ? ' <span class="badge">optie</span>' : ''}</td><td class="artnr">${esc(u.pkg.artnr)}</td><td>${esc(u.pkg.fitsText)}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="series-label">Types</div><div class="model-links">${[...models.values()].sort((a, b) => natural(a.name, b.name)).map((m) => `<a class="chip" href="${modelUrl(m)}">${esc(m.name)}</a>`).join('')}</div></div>`;
  }

  function pagePart(id) {
    const q = partById[id];
    if (!q) return pageNotFound();
    const cat = catById[q.category];
    setCrumbs([['Transportkoeling', '#/'], ['Onderdelen', '#/onderdelen'], [cat.name, `#/onderdelen/${cat.id}`], [q.title]]);
    const fitModels = q.fits.map((f) => ({ m: byModel[f.model], c: f.condition })).filter((x) => x.m);
    const related = q.related.map((a) => (byArt[a] || []).find((e) => e.kind === 'part')).filter(Boolean);
    app.innerHTML = `<article class="card detail">
      <div><div class="detail-img">${img(q.img, q.title)}</div>
        ${q.extraImgs.length ? `<div class="detail-extra">${q.extraImgs.map((s) => img(s, q.title)).join('')}</div>` : ''}</div>
      <div>
        <h1 style="margin-top:0">${esc(q.title)}</h1>
        ${q.makes.length ? `<p class="lead">Voor ${q.makes.map((mk) => `<a href="#/merk/${mk}">${esc(makeName(mk))}</a>`).join(' en ')}</p>` : ''}
        <ul class="specs">${q.specs.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
        <div class="table-wrap"><table class="vt"><thead><tr><th>Artikelnummer</th><th>Uitvoering</th><th></th></tr></thead><tbody>
          ${q.variants.map((v) => `<tr><td class="artnr">${esc(v.artnr)}</td><td>${esc([v.label, v.note].filter(Boolean).join(' · ')) || '–'}</td><td><div class="actions" style="justify-content:flex-end">${copyBtn(v.artnr)}${webshopLink(v.artnr, true)}</div></td></tr>`).join('')}
        </tbody></table></div>
        ${fitModels.length ? `<div class="series-label">Geschikt voor</div><div class="model-links">${fitModels.map((x) => `<a class="chip" href="${modelUrl(x.m)}">${esc(x.m.name)}</a>`).join('')}</div>` : ''}
        ${related.length ? `<div class="series-label">Hoort bij</div><div class="model-links">${related.map((e) => `<a class="chip" href="#/onderdeel/${enc(e.part.id)}">${esc(e.part.title)} ${esc(e.variant.artnr)}</a>`).join('')}</div>` : ''}
        ${q.variants.map((v) => usedInHtml(v.artnr)).join('')}
      </div></article>`;
  }

  function pagePackage(id) {
    const p = pkgById[id];
    if (!p) return pageNotFound();
    setCrumbs([['Transportkoeling', '#/'], [makeName(p.make), `#/merk/${p.make}`], [`${p.type} ${p.artnr}`]]);
    const models = modelsOfPkg(p);
    app.innerHTML = `<div style="margin-top:12px" class="grid packages">${packageCard(p)}</div>
      <div class="series-label">Geschikt voor</div><div class="model-links">${models.map((m) => `<a class="chip" href="${modelUrl(m)}">${esc(m.name)}</a>`).join('')}</div>`;
  }

  // Artikelnummer uit een pakket (filter/riem) dat niet als los catalogusartikel bestaat
  function pageArticle(artnr) {
    const entries = byArt[artnr] || [];
    const part = entries.find((e) => e.kind === 'part');
    if (part) { location.replace(`#/onderdeel/${enc(part.part.id)}`); return; }
    const pkg = entries.find((e) => e.kind === 'package');
    if (pkg) { location.replace(`#/pakket/${enc(pkg.pkg.id)}`); return; }
    const items = entries.filter((e) => e.kind === 'item');
    if (!items.length) return pageNotFound();
    const it = items[0].item;
    setCrumbs([['Transportkoeling', '#/'], [`${it.name} ${artnr}`]]);
    const bigImg = items.map((e) => e.item.img).find(Boolean);
    app.innerHTML = `<article class="card detail">
      <div class="detail-img">${img(bigImg, it.name, 'upscale')}</div>
      <div>
        <h1 style="margin-top:0">${esc(it.name)}</h1>
        ${it.brand ? `<p class="lead">Merk: ${esc(it.brand)}</p>` : ''}
        <div class="actions"><span class="artnr-big">art.nr. ${esc(artnr)}</span>${copyBtn(artnr)}${webshopLink(artnr)}</div>
        ${usedInHtml(artnr)}
      </div></article>`;
  }

  function pageRefrigerant(filter) {
    setCrumbs([['Transportkoeling', '#/'], ['Koudemiddel volumes']]);
    const f = compact(filter);
    const col = (make) => {
      const rows = D.refrigerant.filter((r) => r.make === make && (!f || compact(r.type).includes(f)));
      return `<div class="card"><h3>${esc(makeName(make))}</h3><div class="table-wrap"><table class="vt"><thead><tr><th>Type aggregaat</th><th>Koudemiddel</th><th>Volume (kg)</th></tr></thead><tbody>
        ${rows.map((r) => {
          const m = byModel[`${make}-${r.type}`.toLowerCase().replace(/[^a-z0-9]+/g, '-')];
          return `<tr><td>${m ? `<a href="${modelUrl(m)}">${esc(r.type)}</a>` : esc(r.type)}</td><td>${esc(r.refrigerant)}</td><td>${esc(r.kg)}</td></tr>`;
        }).join('') || '<tr><td colspan="3">Geen resultaten</td></tr>'}
      </tbody></table></div></div>`;
    };
    app.innerHTML = `<h1>Koudemiddel volumes</h1>
      <p class="lead">Vulhoeveelheid koudemiddel per type aggregaat.</p>
      <input class="ref-filter" id="ref-filter" type="search" placeholder="Filter op type, bijv. SLX of SUPRA" value="${esc(filter || '')}" aria-label="Filter op type">
      <div class="ref-cols">${col('thermoking')}${col('carrier')}</div>`;
    const inp = document.getElementById('ref-filter');
    inp.addEventListener('input', () => {
      history.replaceState(null, '', `#/koudemiddel?f=${enc(inp.value)}`);
      const pos = inp.selectionStart;
      pageRefrigerant(inp.value);
      const n = document.getElementById('ref-filter'); n.focus(); n.setSelectionRange(pos, pos);
    });
  }

  /* ---------- zoeken ---------- */
  function search(q) {
    const nq = norm(q).trim(), cq = compact(q);
    if (!cq) return [];
    const words = nq.split(/\s+/).filter(Boolean);
    const hit = (text) => { const t = norm(text); return words.every((w) => t.includes(w)) || compact(text).includes(cq); };
    const res = [];
    if (window.TB) res.push(...window.TB.search(q));
    D.models.forEach((m) => { if (hit(m.name) || hit(makeName(m.make) + ' ' + m.name)) res.push({ score: compact(m.name) === cq ? 100 : 80, kind: 'Type', title: m.name, sub: makeName(m.make), href: modelUrl(m) }); });
    D.packages.forEach((p) => {
      const artHit = compact(p.artnr).includes(cq);
      if (artHit || hit(`${p.type} ${p.fitsText} ${makeName(p.make)}`)) res.push({ score: artHit ? 90 : 50, kind: p.type, title: `${p.type} ${p.artnr}`, sub: `${makeName(p.make)}: ${p.fitsText}`, href: `#/pakket/${enc(p.id)}`, img: p.img, art: p.artnr });
    });
    D.parts.forEach((q2) => {
      const artHit = q2.variants.some((v) => compact(v.artnr).includes(cq));
      if (artHit || hit(`${q2.title} ${q2.specs.join(' ')} ${q2.variants.map((v) => v.label).join(' ')}`)) {
        res.push({ score: artHit ? 85 : 40, kind: catById[q2.category].name, title: q2.title, sub: `${q2.variants.map((v) => v.artnr).join(', ')} · ${q2.specs.slice(0, 2).join(' · ')}`, href: `#/onderdeel/${enc(q2.id)}`, img: q2.img, art: q2.variants[0].artnr });
      }
    });
    const seenItems = new Set();
    D.packages.forEach((p) => p.items.forEach((it) => {
      if (seenItems.has(it.artnr) || (byArt[it.artnr] || []).some((e) => e.kind === 'part')) return;
      const artHit = compact(it.artnr).includes(cq);
      if (artHit || hit(`${it.name} ${it.brand}`)) {
        seenItems.add(it.artnr);
        const n = byArt[it.artnr].filter((e) => e.kind === 'item').length;
        res.push({ score: artHit ? 85 : 30, kind: 'Uit pakket', title: `${it.name}`, sub: `${it.artnr}${it.brand ? ' · ' + it.brand : ''} · in ${n} pakket${n > 1 ? 'ten' : ''}`, href: `#/artikel/${enc(it.artnr)}`, img: it.img, art: it.artnr });
      }
    }));
    return res.sort((a, b) => b.score - a.score || natural(a.title, b.title));
  }

  function mark(text, q) {
    const s = esc(text);
    const words = norm(q).split(/\s+/).filter((w) => w.length > 1).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    return words.length ? s.replace(new RegExp(`(${words.join('|')})`, 'gi'), '<mark>$1</mark>') : s;
  }

  function pageSearch(q) {
    setCrumbs([[`Zoeken: ${q}`]]);
    searchInput.value = q;
    const res = search(q);
    // precies één artikelnummer of type gevonden? direct openen
    app.innerHTML = `<h1>Zoekresultaten</h1><p class="lead">${res.length} resultaten voor “${esc(q)}”</p>
      <div class="results">${res.slice(0, 150).map((r) => `<a class="card result" href="${r.href}">
        ${r.img ? img(r.img, r.title) : '<span></span>'}
        <div><div class="r-kind">${esc(r.kind)}</div><div class="r-title">${mark(r.title, q)}</div><div class="r-sub">${mark(r.sub, q)}</div></div>
      </a>`).join('') || `<div class="empty">Niets gevonden. Probeer een deel van het typenummer (bijv. “SUPRA 950” of “SL-400”), een omschrijving (bijv. “scharnier”) of een artikelnummer zonder puntjes.</div>`}</div>
      ${res.length > 150 ? `<p class="lead" style="margin-top:12px">De eerste 150 resultaten worden getoond. Maak je zoekopdracht specifieker.</p>` : ''}`;
  }

  function pageNotFound() {
    setCrumbs([['Niet gevonden']]);
    app.innerHTML = `<div class="empty"><h1>Niet gevonden</h1><p>Deze pagina bestaat niet (meer). <a href="#/">Terug naar het begin</a>.</p></div>`;
  }

  /* ---------- router ---------- */
  function route() {
    const hash = location.hash.replace(/^#\/?/, '');
    const [path, qs] = hash.split('?');
    const params = new URLSearchParams(qs || '');
    const seg = path.split('/').map((s) => decodeURIComponent(s));
    switch (seg[0]) {
      case '': pageCatalogs(); break;
      case 'koeling': pageHome(); break;
      case 'trailer': if (window.TB) window.TB.route(seg.slice(1), params); else pageNotFound(); break;
      case 'merk': pageMake(seg[1], seg[2]); break;
      case 'merk-onderdelen': pageMakeParts(seg[1]); break;
      case 'type': pageModel(seg[1]); break;
      case 'pakket': pagePackage(seg[1]); break;
      case 'onderdeel': pagePart(seg[1]); break;
      case 'artikel': pageArticle(seg[1]); break;
      case 'onderdelen': pageParts(seg[1]); break;
      case 'koudemiddel': pageRefrigerant(params.get('f') || ''); break;
      case 'zoek': pageSearch(params.get('q') || ''); break;
      default: pageNotFound();
    }
    if (seg[0] !== 'zoek') searchInput.value = '';
    if (seg[0] !== 'koudemiddel' || !params.get('f')) {
      window.scrollTo(0, 0);
      if (EMBEDDED) parent.postMessage({ type: 'tk-selector:navigate' }, '*');
    }
  }

  /* ---------- events ---------- */
  searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = searchInput.value.trim();
    if (!q) return;
    const res = search(q);
    const exact = res.filter((r) => r.score >= 85 && (compact(r.art || '') === compact(q) || compact(r.title) === compact(q)));
    location.hash = exact.length === 1 ? exact[0].href : `#/zoek?q=${enc(q)}`;
  });

  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    e.preventDefault();
    const t = b.getAttribute('data-copy');
    const done = () => toast(`${t} gekopieerd`);
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done, () => fallbackCopy(t, done));
    else fallbackCopy(t, done);
  });
  function fallbackCopy(t, done) {
    const ta = document.createElement('textarea');
    ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (_) { toast(t); }
    ta.remove();
  }

  // In een iframe: hoogte doorgeven aan de pagina die de tool insluit (zie embed.js)
  if (EMBEDDED) {
    document.body.classList.add('embedded');
    const send = () => parent.postMessage({ type: 'tk-selector:height', height: document.documentElement.scrollHeight }, '*');
    new ResizeObserver(send).observe(document.body);
    window.addEventListener('load', send);
  }

  // gedeelde hulpfuncties voor andere catalogusmodules (trailerbouw.js)
  window.TKH = { esc, enc, norm, compact, natural, img, copyBtn, webshopLink, setCrumbs, mark, app, ICON, notFound: () => pageNotFound() };

  window.addEventListener('hashchange', route);
  const V = (document.querySelector('script[src*="app.js"]').src.split('v=')[1] || '');
  const getJson = (u) => fetch(u + (V ? '?v=' + V : '')).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  Promise.all([getJson('data/catalogus.json'), getJson('data/trailerbouw.json').catch(() => null)])
    .then(([d, tb]) => { D = d; indexData(); if (tb && window.TB) window.TB.init(tb); route(); })
    .catch(() => { app.innerHTML = '<div class="empty">De catalogus kon niet worden geladen. Probeer het later opnieuw.</div>'; });
})();
