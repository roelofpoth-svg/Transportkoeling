/*
 * Wijlhuizen Transportkoeling selector insluiten op een website.
 *
 * Plaats op de pagina:
 *   <div id="wijlhuizen-transportkoeling"></div>
 *   <script src="https://<jouw-domein>/embed.js" async></script>
 *
 * Optioneel: data-start="#/merk/thermoking" op de div om direct bij een merk, type of categorie te beginnen.
 * De iframe groeit automatisch mee met de inhoud, zodat er geen dubbele scrollbalk ontstaat.
 */
(function () {
  var script = document.currentScript || document.querySelector('script[src*="embed.js"]');
  var base = script.src.replace(/embed\.js(\?.*)?$/, '');
  var hosts = document.querySelectorAll('#wijlhuizen-transportkoeling, [data-wijlhuizen-transportkoeling]');
  if (!hosts.length) {
    var d = document.createElement('div');
    script.parentNode.insertBefore(d, script);
    hosts = [d];
  }
  Array.prototype.forEach.call(hosts, function (host) {
    if (host.querySelector('iframe')) return;
    var start = host.getAttribute('data-start') || '';
    var frame = document.createElement('iframe');
    frame.src = base + 'index.html' + (start ? (start.charAt(0) === '#' ? start : '#/' + start) : '');
    frame.title = 'Wijlhuizen Transportkoeling selectietool';
    frame.loading = 'lazy';
    frame.setAttribute('allow', 'clipboard-write');
    frame.style.cssText = 'width:100%;border:0;display:block;min-height:600px;height:900px;overflow:hidden';
    host.appendChild(frame);
    window.addEventListener('message', function (e) {
      if (e.source !== frame.contentWindow || !e.data) return;
      if (e.data.type === 'tk-selector:height') frame.style.height = Math.max(600, e.data.height) + 'px';
      if (e.data.type === 'tk-selector:navigate') {
        var top = frame.getBoundingClientRect().top;
        if (top < 0) window.scrollBy({ top: top - 10, behavior: 'smooth' });
      }
    });
  });
})();
