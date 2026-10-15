/* Generieke catalogusweergave: elke catalogus is een boom (willekeurige diepte) met producten in de bladeren.
 * Data: data/catalogi.json (lijst) en data/catalogi/<id>.json (per catalogus, wordt pas geladen wanneer nodig). */
(function () {
  'use strict';
  let H, INDEX = [], VER = '';
  const CATS = {}; // id -> {data, nodes, prods, byArt}
  const loading = {};
  const H0 = () => H || (H = window.TKH);

  function init(index, ver) { INDEX = index; VER = ver || ''; }
  const meta = (cid) => INDEX.find((c) => c.id === cid);

  function load(cid) {
    if (CATS[cid]) return Promise.resolve(CATS[cid]);
    if (!loading[cid]) {
      loading[cid] = fetch(`data/catalogi/${cid}.json${VER ? '?v=' + VER : ''}`).then((r) => r.json()).then((d) => {
        const c = { data: d, nodes: {}, prods: {}, byArt: {}, byNode: {} };
        const walk = (n, parent, depth) => { n.parent = parent; n.depth = depth; c.nodes[n.id] = n; n.children.forEach((ch) => walk(ch, n, depth + 1)); };
        d.tree.forEach((n) => walk(n, null, 0));
        const { norm } = H0();
        d.products.forEach((p) => {
          c.prods[p.id] = p;
          (c.byNode[p.n] = c.byNode[p.n] || []).push(p);
          p.tables.forEach((t) => t.rows.forEach((r) => { (c.byArt[r.a] = c.byArt[r.a] || []).push({ p, r }); }));
          const path = []; for (let n = c.nodes[p.n]; n; n = n.parent) path.unshift(n.name);
          p._path = path;
          p._text = norm([p.title, p.lijn, ...path, ...p.tables.flatMap((t) => [...t.notes, ...t.rows.flatMap((r) => [...r.c, r.s])])].join(' '));
        });
        CATS[cid] = c;
        return c;
      });
    }
    return loading[cid];
  }
  const ensureAll = () => Promise.all(INDEX.map((c) => load(c.id)));

  /* ---------- hulp ---------- */
  const nodeUrl = (cid, n) => `#/c/${cid}/n/${n.id}`;
  const prodUrl = (cid, p, a) => `#/c/${cid}/p/${encodeURIComponent(p.id)}${a ? '?a=' + encodeURIComponent(a) : ''}`;
  const pathOf = (n) => { const out = []; for (let x = n; x; x = x.parent) out.unshift(x); return out; };
  const allProducts = (c, n) => n.children.length ? n.children.flatMap((ch) => allProducts(c, ch)) : (c.byNode[n.id] || []);

  function crumbsFor(cid, n, extra) {
    const m = meta(cid);
    const list = [[m.name, `#/c/${cid}`], ...pathOf(n).map((x) => [x.name, nodeUrl(cid, x)])];
    if (extra) list.push([extra]); else list[list.length - 1] = [list[list.length - 1][0]];
    H0().setCrumbs(list);
  }

  function treeHtml(cid, c, cur) {
    const { esc } = H0();
    const open = new Set(cur ? pathOf(cur).map((n) => n.id) : []);
    const item = (n) => n.children.length
      ? `<details${open.has(n.id) ? ' open' : ''}><summary>${esc(n.name)} <span class="tree-n">${n.count}</span></summary><ul>${n.children.map((ch) => `<li>${item(ch)}</li>`).join('')}</ul></details>`
      : `<a href="${nodeUrl(cid, n)}"${cur === n ? ' aria-current="page"' : ''}>${esc(n.name)} <span class="tree-n">${n.count}</span></a>`;
    return `<nav class="tree gtree" aria-label="Productgroepen"><ul>${c.data.tree.map((n) => `<li>${item(n)}</li>`).join('')}</ul></nav>`;
  }

  function layout(cid, c, cur, content) {
    const wide = window.matchMedia('(min-width: 901px)').matches;
    return `<div class="tb-layout">
      <aside class="tb-side"><details class="tb-side-toggle"${wide ? ' open' : ''}><summary>Productgroepen</summary>${treeHtml(cid, c, cur)}</details></aside>
      <div class="tb-main">${content}</div></div>`;
  }

  function productCard(cid, p) {
    const { esc, img } = H0();
    const rows = p.tables.flatMap((t) => t.rows.map((r) => ({ r, t })));
    const main = rows.filter(({ r }) => !/^(toebehoren|onderdelen)/i.test(r.s));
    const notes = p.tables.flatMap((t) => t.notes).slice(0, 3);
    const pic = p.img[0] || (rows.find(({ r }) => r.i) || { r: {} }).r.i;
    const desc = ({ r, t }) => {
      const parts = r.c.filter((v, i) => v && t.cols[i] !== 'Afb.' && t.cols[i] !== 'Pos.' && t.cols[i] !== 'Positie');
      return parts.slice(0, 3).join(' · ');
    };
    return `<a class="card tb-card" href="${prodUrl(cid, p)}">
      <div class="part-img">${pic ? img(pic, p.title) : '<span class="noimg">geen afbeelding</span>'}</div>
      <div class="part-body">
        <h3 class="part-title">${esc(p.title)}</h3>
        ${p.lijn ? `<span class="badge">${esc(p.lijn)}</span>` : ''}
        ${notes.length ? `<ul class="specs">${notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
        <ul class="tb-preview">${main.slice(0, 3).map((x) => `<li><span class="artnr">${esc(x.r.a)}</span> <span class="v-label">${esc(desc(x))}</span></li>`).join('')}</ul>
        ${rows.length > 3 ? `<span class="v-label">+ ${rows.length - 3} meer</span>` : ''}
      </div></a>`;
  }

  /* ---------- pagina's ---------- */
  function pageCatalog(cid, c) {
    const { esc, img, app, setCrumbs } = H0();
    const m = meta(cid);
    setCrumbs([[m.name]]);
    app.innerHTML = `<h1>${esc(m.name)}</h1><p class="lead">${esc(m.desc)} Kies een groep of zoek bovenaan op artikelnummer, OE-nummer of omschrijving.</p>
      <div class="grid groups" style="margin-top:16px">${c.data.tree.map((n) => `<section class="card group">
        <a class="group-head" href="${nodeUrl(cid, n)}">${n.img ? img(n.img, n.name) : ''}<span><b>${esc(n.name)}</b><span class="v-label">${n.count} producten</span></span></a>
        ${n.children.length ? `<ul>${n.children.slice(0, 14).map((ch) => `<li><a href="${nodeUrl(cid, ch)}">${esc(ch.name)}</a> <span class="tree-n">${ch.count}</span></li>`).join('')}
          ${n.children.length > 14 ? `<li><a href="${nodeUrl(cid, n)}"><b>Alle ${n.children.length} groepen ›</b></a></li>` : ''}</ul>` : ''}
      </section>`).join('')}</div>`;
  }

  function pageNode(cid, c, n, params) {
    const { esc, img, app } = H0();
    crumbsFor(cid, n);
    if (n.children.length) {
      app.innerHTML = layout(cid, c, n, `<h1>${esc(n.name)}</h1><p class="lead">${n.count} producten · ${n.articles} artikelregels</p>
        <div class="grid subs">${n.children.map((ch) => `<a class="card sub" href="${nodeUrl(cid, ch)}">
          <div class="part-img">${ch.img ? img(ch.img, ch.name) : ''}</div>
          <div class="part-body"><h3 class="part-title">${esc(ch.name)}</h3>
            <span class="v-label">${ch.count} producten${typeof ch.page === 'number' ? ` · blz. ${ch.page}` : ''}</span>
            ${ch.children.length ? `<span class="v-label">${ch.children.map((x) => esc(x.name)).slice(0, 4).join(', ')}${ch.children.length > 4 ? '…' : ''}</span>` : ''}</div>
        </a>`).join('')}</div>`);
      return;
    }
    const all = c.byNode[n.id] || [];
    const lines = n.lines || [];
    const lijn = params.get('lijn') || '';
    const useChips = lines.length > 1 && lines.length <= 30;
    const chips = useChips ? `<div class="series-tabs" role="group" aria-label="Productlijn">
        <a class="chip${lijn ? '' : ' on'}" href="${nodeUrl(cid, n)}">Alles (${all.length})</a>
        ${lines.map((l) => `<a class="chip${l === lijn ? ' on' : ''}" href="${nodeUrl(cid, n)}?lijn=${encodeURIComponent(l)}">${esc(l)} (${all.filter((p) => p.lijn === l).length})</a>`).join('')}</div>` : '';
    let body;
    if (!lijn && all.length <= 2) body = all.map((p) => `<div class="inline-prod">${productFull(cid, p, '', true)}</div>`).join('');
    else if (lijn) body = `<div class="grid parts">${all.filter((p) => p.lijn === lijn).map((p) => productCard(cid, p)).join('')}</div>`;
    else if (lines.length) {
      body = [''].concat(lines).map((l) => {
        const ps = all.filter((p) => p.lijn === l);
        return ps.length ? `${l ? `<div class="series-label">${esc(l)}</div>` : ''}<div class="grid parts">${ps.map((p) => productCard(cid, p)).join('')}</div>` : '';
      }).join('');
    } else body = `<div class="grid parts">${all.map((p) => productCard(cid, p)).join('')}</div>`;
    const pages = all.map((p) => p.page).filter((x) => typeof x === 'number');
    app.innerHTML = layout(cid, c, n, `<div class="tree-code">${esc(pathOf(n).slice(0, -1).map((x) => x.name).join(' › '))}${pages.length ? ` · catalogus blz. ${Math.min(...pages)}` : ''}</div>
      <h1 style="margin-top:2px">${esc(n.name)}</h1><p class="lead">${all.length} producten · ${n.articles} artikelregels</p>${chips}${body}`);
  }

  function tablesHtml(p, hl) {
    const { esc, img, copyBtn, webshopLink } = H0();
    return p.tables.map((t) => {
      const hasImg = t.rows.some((r) => r.i);
      let section = null;
      const body = t.rows.map((r) => {
        let head = '';
        if (r.s !== section) {
          section = r.s;
          if (r.s) head = `<tr class="sec"><td colspan="${t.cols.length + 2 + (hasImg ? 1 : 0)}">${esc(r.s)}</td></tr>`;
        }
        return `${head}<tr${r.a === hl ? ' class="hl" id="hl"' : ''}>${hasImg ? `<td class="row-img">${r.i ? img(r.i, r.c.join(' ')) : ''}</td>` : ''}${t.cols.map((col, i) => `<td>${esc(r.c[i] || '').replace(/ \| /g, '<br>')}</td>`).join('')}
          <td class="artnr">${esc(r.a)}</td><td><div class="actions" style="justify-content:flex-end">${copyBtn(r.a)}${webshopLink(r.a, true)}</div></td></tr>`;
      }).join('');
      return `<div class="table-wrap"><table class="vt"><thead><tr>${hasImg ? '<th></th>' : ''}${t.cols.map((col) => `<th>${esc(col)}</th>`).join('')}<th>Artikelnummer</th><th></th></tr></thead><tbody>${body}</tbody></table></div>
        ${t.notes.length ? `<ul class="specs tb-notes">${t.notes.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}`;
    }).join('');
  }

  // product volledig (foto's + tabel), gebruikt op de productpagina en in kleine groepen
  function productFull(cid, p, hl, asSection) {
    const { esc, img } = H0();
    const imgs = p.img;
    return `<article class="card detail tb-detail">
        <div><div class="detail-img">${imgs[0] ? img(imgs[0], p.title) : '<span class="noimg">geen afbeelding</span>'}</div>
          ${imgs.length > 1 ? `<div class="detail-extra">${imgs.slice(1, 13).map((x) => `<a href="${esc(x)}" target="_blank" rel="noopener">${img(x, p.title)}</a>`).join('')}</div>` : ''}</div>
        <div>
          <div class="tree-code">${esc(meta(cid).name)} › ${esc(p._path.join(' › '))}${typeof p.page === 'number' ? ` · catalogus blz. ${p.page}` : ''}</div>
          ${asSection ? `<h2 style="margin:4px 0 8px"><a href="${prodUrl(cid, p)}" style="color:inherit;text-decoration:none">${esc(p.title)}</a></h2>` : `<h1 style="margin-top:4px">${esc(p.title)}</h1>`}
          ${p.lijn ? `<p style="margin:0 0 10px"><span class="badge">${esc(p.lijn)}</span></p>` : ''}
        </div>
      </article>
      <div class="card tb-tables">${tablesHtml(p, hl)}</div>`;
  }

  function pageProduct(cid, c, p, params) {
    const { esc, app } = H0();
    const n = c.nodes[p.n];
    crumbsFor(cid, n, p.title);
    const hl = params.get('a') || '';
    const sibs = c.byNode[p.n] || [];
    const i = sibs.indexOf(p);
    const nav = `<div class="pager">${i > 0 ? `<a class="btn ghost" href="${prodUrl(cid, sibs[i - 1])}">‹ ${esc(sibs[i - 1].title)}</a>` : '<span></span>'}
      ${i < sibs.length - 1 ? `<a class="btn ghost" href="${prodUrl(cid, sibs[i + 1])}">${esc(sibs[i + 1].title)} ›</a>` : ''}</div>`;
    app.innerHTML = layout(cid, c, n, productFull(cid, p, hl) + nav);
    if (hl) setTimeout(() => { const el = document.getElementById('hl'); if (el) el.scrollIntoView({ block: 'center' }); }, 50);
  }

  /* ---------- zoeken ---------- */
  function searchLoaded(q) {
    const { norm, compact } = H0();
    const cq = compact(q);
    const words = norm(q).trim().split(/\s+/).filter(Boolean);
    if (!cq) return [];
    const res = [];
    INDEX.forEach((m) => {
      const c = CATS[m.id];
      if (!c) return;
      const seen = new Set();
      if (cq.length >= 4) {
        Object.keys(c.byArt).forEach((a) => {
          const ca = compact(a);
          if (!ca.includes(cq)) return;
          c.byArt[a].forEach(({ p, r }) => {
            const k = p.id + a; if (seen.has(k)) return; seen.add(k);
            res.push({ score: ca === cq ? 95 : 84, kind: m.name, title: p.title, sub: `${a} · ${r.c.filter(Boolean).join(' · ').replace(/ \| /g, ' ')}`, href: prodUrl(m.id, p, a), img: r.i || p.img[0], art: a });
          });
        });
      }
      Object.values(c.nodes).forEach((n) => {
        if (words.every((w) => norm(pathOf(n).map((x) => x.name).join(' ')).includes(w)) && words.some((w) => norm(n.name).includes(w))) {
          res.push({ score: 72, kind: `${m.name} · groep`, title: pathOf(n).map((x) => x.name).join(' › '), sub: `${n.count} producten`, href: nodeUrl(m.id, n), img: n.img });
        }
      });
      c.data.products.forEach((p) => {
        if (seen.has(p.id + '*')) return;
        if (words.every((w) => p._text.includes(w))) {
          const inTitle = words.every((w) => norm(p.title + ' ' + p.lijn).includes(w));
          // OE-nummers of andere codes in de tabel: toon de regel die matcht
          let hitRow = null;
          if (!inTitle && cq.length >= 4) {
            for (const t of p.tables) { for (const r of t.rows) { if (compact(r.c.join(' ')).includes(cq)) { hitRow = r; break; } } if (hitRow) break; }
          }
          const arts = p.tables.flatMap((t) => t.rows.map((r) => r.a));
          res.push({ score: hitRow ? 80 : inTitle ? 45 : 28, kind: `${m.name} · ${p._path[p._path.length - 1]}`, title: p.title,
            sub: hitRow ? `${hitRow.a} · ${hitRow.c.filter(Boolean).join(' · ').replace(/ \| /g, ' ')}` : `${arts.slice(0, 4).join(', ')}${arts.length > 4 ? ` +${arts.length - 4}` : ''}${p.lijn ? ' · ' + p.lijn : ''}`,
            href: prodUrl(m.id, p, hitRow ? hitRow.a : ''), img: (hitRow && hitRow.i) || p.img[0], art: hitRow ? hitRow.a : '' });
        }
      });
    });
    return res;
  }

  /* ---------- router ---------- */
  function route(seg, params) {
    const { app } = H0();
    const cid = seg[0];
    if (!meta(cid)) return H0().notFound();
    if (!CATS[cid]) app.innerHTML = '<p class="loading">Catalogus laden…</p>';
    return load(cid).then((c) => {
      if (seg[1] === 'n') {
        const n = c.nodes[seg.slice(2).join('/')];
        return n ? pageNode(cid, c, n, params) : H0().notFound();
      }
      if (seg[1] === 'p') {
        const p = c.prods[seg[2]];
        return p ? pageProduct(cid, c, p, params) : H0().notFound();
      }
      return pageCatalog(cid, c);
    });
  }

  // oude trailerbouw-links (#/trailer/s/1.1.1, #/trailer/p/51.02.0350) blijven werken
  function legacyTrailer(seg, params) {
    return load('trailerbouw').then((c) => {
      if (seg[0] === 'p' && seg[1]) { location.replace(`#/c/trailerbouw/p/${encodeURIComponent(seg[1])}${params.toString() ? '?' + params : ''}`); return; }
      if ((seg[0] === 's' || seg[0] === 'g' || seg[0] === 'h') && seg[1]) {
        const n = Object.values(c.nodes).find((x) => x.name.startsWith(seg[1] + ' '));
        if (n) { location.replace(nodeUrl('trailerbouw', n) + (params.toString() ? '?' + params : '')); return; }
      }
      location.replace('#/c/trailerbouw');
    });
  }

  window.CAT = { init, route, legacyTrailer, load, ensureAll, searchLoaded, index: () => INDEX, isLoaded: () => INDEX.every((c) => CATS[c.id]) };
})();
