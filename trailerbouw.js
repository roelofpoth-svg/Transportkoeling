/* Catalogus Trailerbouwdelen: zoekboom hoofdgroep → groep → subgroep (→ productlijn) → product. */
(function () {
  'use strict';
  let T, H; // data, hulpfuncties uit app.js
  const prodById = {}, subByCode = {}, groupByCode = {}, headByCode = {}, byArt = {};
  const sortCode = (a, b) => { const x = a.split('.').map(Number), y = b.split('.').map(Number); for (let i = 0; i < Math.max(x.length, y.length); i++) { if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); } return 0; };

  function init(data) {
    T = data;
    T.tree.forEach((h) => {
      headByCode[h.code] = h;
      h.groups.forEach((g) => { g.head = h; groupByCode[g.code] = g; g.subs.forEach((s) => { s.group = g; subByCode[s.code] = s; }); });
    });
    T.products.forEach((p) => {
      prodById[p.id] = p;
      p.tables.forEach((t) => t.rows.forEach((r) => { (byArt[r.a] = byArt[r.a] || []).push({ p, r, t }); }));
      // zoektekst één keer opbouwen
      const sub = subByCode[p.s];
      p._text = H0().norm([p.title, p.lijn, sub && sub.name, sub && sub.group.name,
        ...p.tables.flatMap((t) => [...t.notes, ...t.rows.flatMap((r) => [...r.c, r.s])])].join(' '));
    });
  }
  const H0 = () => H || (H = window.TKH);

  function stats() {
    if (!T) return null;
    return { subs: Object.keys(subByCode).length, products: T.products.length, articles: Object.keys(byArt).length };
  }

  /* ---------- boom (zijbalk) ---------- */
  function treeHtml(cur) {
    const { esc, enc } = H0();
    const curSub = cur && subByCode[cur], curGroup = curSub ? curSub.group : groupByCode[cur], curHead = curGroup ? curGroup.head : headByCode[cur];
    return `<nav class="tree" aria-label="Productgroepen">
      ${T.tree.map((h) => `<details${curHead === h ? ' open' : ''}><summary><span class="tree-code">${h.code}</span> ${esc(h.name)}</summary>
        ${h.groups.map((g) => `<details class="tree-g"${curGroup === g ? ' open' : ''}><summary><span class="tree-code">${g.code}</span> ${esc(g.name)}</summary>
          <ul>${g.subs.map((s) => `<li><a href="#/trailer/s/${enc(s.code)}"${s === curSub ? ' aria-current="page"' : ''}>${esc(s.name)} <span class="tree-n">${s.count}</span></a></li>`).join('')}</ul>
        </details>`).join('')}
      </details>`).join('')}
    </nav>`;
  }

  function layout(cur, content) {
    return `<div class="tb-layout">
      <aside class="tb-side"><details class="tb-side-toggle"${window.matchMedia('(min-width: 901px)').matches ? ' open' : ''}><summary>Productgroepen</summary>${treeHtml(cur)}</details></aside>
      <div class="tb-main">${content}</div>
    </div>`;
  }

  /* ---------- kaarten ---------- */
  function productCard(p) {
    const { esc, enc, img } = H0();
    const rows = p.tables.flatMap((t) => t.rows);
    const main = rows.filter((r) => !/^toebehoren/i.test(r.s));
    const notes = p.tables.flatMap((t) => t.notes).slice(0, 3);
    const spec = (r, t) => r.c.filter((v, i) => v && t.cols[i] !== 'Omschrijving' && t.cols[i] !== 'Afb.').join(' · ');
    const first = p.tables[0];
    const preview = main.slice(0, 3).map((r) => {
      const t = p.tables.find((tt) => tt.rows.includes(r));
      return `<li><span class="artnr">${esc(r.a)}</span> <span class="v-label">${esc(spec(r, t) || r.c[first.cols.indexOf('Omschrijving')] || '')}</span></li>`;
    }).join('');
    return `<a class="card tb-card" href="#/trailer/p/${enc(p.id)}">
      <div class="part-img">${p.img[0] ? img(p.img[0], p.title) : '<span class="noimg">geen afbeelding</span>'}</div>
      <div class="part-body">
        <h3 class="part-title">${esc(p.title)}</h3>
        ${p.lijn ? `<span class="badge">${esc(p.lijn)}</span>` : ''}
        ${notes.length ? `<ul class="specs">${notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
        <ul class="tb-preview">${preview}</ul>
        ${rows.length > 3 ? `<span class="v-label">+ ${rows.length - 3} meer uitvoering${rows.length - 3 > 1 ? 'en' : ''}</span>` : ''}
      </div>
    </a>`;
  }

  /* ---------- pagina's ---------- */
  function pageHome() {
    const { esc, enc, setCrumbs, app, img } = H0();
    setCrumbs([['Trailerbouwdelen']]);
    app.innerHTML = `<h1>Trailerbouwdelen</h1>
      <p class="lead">Kies een productgroep, of zoek op artikelnummer of omschrijving (bijv. “bordscharnier”, “Edscha”, “51.02.0350”).</p>
      ${T.tree.map((h) => `<h2><span class="h-code">${h.code}</span> ${esc(h.name)}</h2>
        <div class="grid groups">${h.groups.map((g) => {
          const thumb = (g.subs.find((s) => s.img) || {}).img;
          return `<section class="card group">
            <a class="group-head" href="#/trailer/g/${enc(g.code)}">${thumb ? img(thumb, g.name) : ''}<span><span class="tree-code">${g.code}</span><b>${esc(g.name)}</b></span></a>
            <ul>${g.subs.map((s) => `<li><a href="#/trailer/s/${enc(s.code)}">${esc(s.name)}</a> <span class="tree-n">${s.count}</span></li>`).join('')}</ul>
          </section>`;
        }).join('')}</div>`).join('')}`;
  }

  function pageGroup(code) {
    const { esc, enc, setCrumbs, app, img } = H0();
    const g = groupByCode[code];
    if (!g) return H0().notFound();
    setCrumbs([['Trailerbouwdelen', '#/trailer'], [g.head.name, '#/trailer'], [g.name]]);
    app.innerHTML = layout(code, `<h1>${esc(g.name)}</h1>
      <div class="grid subs">${g.subs.map((s) => `<a class="card sub" href="#/trailer/s/${enc(s.code)}">
        <div class="part-img">${s.img ? img(s.img, s.name) : ''}</div>
        <div class="part-body"><div class="tree-code">${s.code}</div><h3 class="part-title">${esc(s.name)}</h3>
          <span class="v-label">${s.count} producten · ${s.articles} artikelnummers · blz. ${s.page}</span>
          ${s.lines.length ? `<span class="v-label">${s.lines.length} productlijnen</span>` : ''}</div>
      </a>`).join('')}</div>`);
  }

  function pageSub(code, params) {
    const { esc, enc, setCrumbs, app } = H0();
    const s = subByCode[code];
    if (!s) return H0().notFound();
    const g = s.group;
    setCrumbs([['Trailerbouwdelen', '#/trailer'], [g.name, `#/trailer/g/${enc(g.code)}`], [s.name]]);
    const lijn = params.get('lijn') || '';
    const all = T.products.filter((p) => p.s === code);
    const list = lijn ? all.filter((p) => p.lijn === lijn) : all;
    const chips = s.lines.length ? `<div class="series-tabs" role="group" aria-label="Productlijn">
        <a class="chip${lijn ? '' : ' on'}" href="#/trailer/s/${enc(code)}">Alles (${all.length})</a>
        ${s.lines.map((l) => `<a class="chip${l === lijn ? ' on' : ''}" href="#/trailer/s/${enc(code)}?lijn=${enc(l)}">${esc(l)} (${all.filter((p) => p.lijn === l).length})</a>`).join('')}
      </div>` : '';
    // groeperen per productlijn wanneer er geen filter actief is
    let body;
    if (!lijn && s.lines.length) {
      const order = [''].concat(s.lines);
      body = order.map((l) => {
        const ps = all.filter((p) => p.lijn === l);
        return ps.length ? `${l ? `<div class="series-label">${esc(l)}</div>` : ''}<div class="grid parts">${ps.map(productCard).join('')}</div>` : '';
      }).join('');
    } else {
      body = `<div class="grid parts">${list.map(productCard).join('')}</div>`;
    }
    app.innerHTML = layout(code, `<div class="tree-code">${s.code} · catalogus blz. ${s.page}</div><h1 style="margin-top:2px">${esc(s.name)}</h1>
      <p class="lead">${all.length} producten · ${s.articles} artikelnummers</p>${chips}${body}`);
  }

  function pageProduct(id, params) {
    const { esc, enc, setCrumbs, app, img, copyBtn, webshopLink } = H0();
    const p = prodById[id];
    if (!p) return H0().notFound();
    const s = subByCode[p.s], g = s.group;
    setCrumbs([['Trailerbouwdelen', '#/trailer'], [g.name, `#/trailer/g/${enc(g.code)}`], [s.name, `#/trailer/s/${enc(s.code)}`], [p.title]]);
    const hl = params.get('a') || '';
    const tables = p.tables.map((t) => {
      let section = null;
      const body = t.rows.map((r) => {
        let head = '';
        if (r.s !== section) {
          section = r.s;
          if (r.s) head = `<tr class="sec"><td colspan="${t.cols.length + 2}">${esc(r.s)}</td></tr>`;
        }
        return `${head}<tr${r.a === hl ? ' class="hl" id="hl"' : ''}>${t.cols.map((c, i) => `<td>${esc(r.c[i] || '')}</td>`).join('')}
          <td class="artnr">${esc(r.a)}</td><td><div class="actions" style="justify-content:flex-end">${copyBtn(r.a)}${webshopLink(r.a, true)}</div></td></tr>`;
      }).join('');
      return `<div class="table-wrap"><table class="vt"><thead><tr>${t.cols.map((c) => `<th>${esc(c)}</th>`).join('')}<th>Artikelnummer</th><th></th></tr></thead><tbody>${body}</tbody></table></div>
        ${t.notes.length ? `<ul class="specs tb-notes">${t.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}`;
    }).join('');
    // buren in dezelfde subgroep
    const sibs = T.products.filter((q) => q.s === p.s);
    const i = sibs.indexOf(p);
    const nav = `<div class="pager">${i > 0 ? `<a class="btn ghost" href="#/trailer/p/${enc(sibs[i - 1].id)}">‹ ${esc(sibs[i - 1].title)}</a>` : '<span></span>'}
      ${i < sibs.length - 1 ? `<a class="btn ghost" href="#/trailer/p/${enc(sibs[i + 1].id)}">${esc(sibs[i + 1].title)} ›</a>` : ''}</div>`;
    app.innerHTML = layout(p.s, `<article class="card detail tb-detail">
        <div><div class="detail-img">${p.img[0] ? img(p.img[0], p.title) : '<span class="noimg">geen afbeelding</span>'}</div>
          ${p.img.length > 1 ? `<div class="detail-extra">${p.img.slice(1).map((x) => `<a href="${esc(x)}" target="_blank" rel="noopener">${img(x, p.title + ' (tekening)')}</a>`).join('')}</div>` : ''}
        </div>
        <div>
          <div class="tree-code">${esc(s.code)} ${esc(s.name)} · catalogus blz. ${p.page}</div>
          <h1 style="margin-top:4px">${esc(p.title)}</h1>
          ${p.lijn ? `<p style="margin:0 0 10px"><span class="badge">${esc(p.lijn)}</span></p>` : ''}
        </div>
      </article>
      <div class="card tb-tables">${tables}</div>${nav}`);
    if (hl) setTimeout(() => { const el = document.getElementById('hl'); if (el) el.scrollIntoView({ block: 'center' }); }, 50);
  }

  /* ---------- zoeken ---------- */
  function search(q) {
    if (!T) return [];
    const { norm, compact, enc } = H0();
    const cq = compact(q);
    const words = norm(q).trim().split(/\s+/).filter(Boolean);
    if (!cq) return [];
    const res = [], seen = new Set();
    // artikelnummer
    Object.keys(byArt).forEach((a) => {
      const ca = compact(a);
      if (cq.length >= 4 && ca.includes(cq)) {
        byArt[a].forEach(({ p, r, t }) => {
          const k = p.id + a;
          if (seen.has(k)) return; seen.add(k);
          const desc = r.c.filter(Boolean).join(' · ');
          res.push({ score: ca === cq ? 95 : 84, kind: 'Trailerbouw', title: p.title, sub: `${a}${desc ? ' · ' + desc : ''}`, href: `#/trailer/p/${enc(p.id)}?a=${enc(a)}`, img: p.img[0], art: a });
        });
      }
    });
    // subgroepen
    Object.values(subByCode).forEach((s) => {
      if (words.every((w) => norm(s.name + ' ' + s.group.name).includes(w))) {
        res.push({ score: 70, kind: 'Productgroep trailerbouw', title: s.name, sub: `${s.group.name} · ${s.count} producten`, href: `#/trailer/s/${enc(s.code)}`, img: s.img });
      }
    });
    // tekst
    T.products.forEach((p) => {
      if (words.every((w) => p._text.includes(w))) {
        const inTitle = words.every((w) => norm(p.title + ' ' + p.lijn).includes(w));
        const arts = p.tables.flatMap((t) => t.rows.map((r) => r.a));
        res.push({ score: inTitle ? 45 : 28, kind: `Trailerbouw · ${subByCode[p.s].name}`, title: p.title, sub: `${arts.slice(0, 4).join(', ')}${arts.length > 4 ? ` +${arts.length - 4}` : ''}${p.lijn ? ' · ' + p.lijn : ''}`, href: `#/trailer/p/${enc(p.id)}`, img: p.img[0] });
      }
    });
    return res;
  }

  function route(seg, params) {
    if (!T) return H0().notFound();
    switch (seg[0] || '') {
      case '': pageHome(); break;
      case 'h': case 'g': pageGroup(seg[1]); break;
      case 's': pageSub(seg[1], params); break;
      case 'p': pageProduct(seg[1], params); break;
      default: H0().notFound();
    }
  }

  window.TB = { init: (d) => { H0(); init(d); }, route, search, stats };
})();
