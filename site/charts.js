(function () {
  'use strict';

  // Real figures from hds_stats.py (261 tasks). One source of truth; update
  // here when the numbers move. No external chart library — inline SVG only,
  // which is the whole point: nothing is fetched, nothing leaves the page.
  var BY_LANG = [
    { lang: 'Python', ok: 135, total: 145 },
    { lang: 'Ruby', ok: 10, total: 11 },
    { lang: 'JavaScript', ok: 35, total: 41 },
    { lang: 'TypeScript', ok: 20, total: 24 },
    { lang: 'PHP', ok: 10, total: 10 },
    { lang: 'C', ok: 10, total: 10 }
  ];
  var OUTCOMES = [
    { key: 'first', n: 208, color: 'var(--aurora-4)' },
    { key: 'corrected', n: 32, color: 'var(--aurora-1)' },
    { key: 'gaveup', n: 21, color: 'var(--ink-faint)' }
  ];

  var SVG = 'http://www.w3.org/2000/svg';

  function el(name, attrs) {
    var n = document.createElementNS(SVG, name);
    for (var k in attrs) { if (attrs.hasOwnProperty(k)) n.setAttribute(k, attrs[k]); }
    return n;
  }

  function t(key, fallback) {
    var lang = document.documentElement.lang || 'en';
    var dict = (window.I18N && window.I18N[lang]) || {};
    return dict[key] !== undefined ? dict[key] : fallback;
  }

  // Horizontal bars: pass@1 per language, labelled with the raw ok/total.
  function renderByLang(host) {
    host.textContent = '';
    var rows = BY_LANG.length, rowH = 34, padL = 96, padR = 54, w = 520,
        h = rows * rowH + 8, barMax = w - padL - padR;
    var svg = el('svg', {
      viewBox: '0 0 ' + w + ' ' + h, class: 'chart__svg',
      role: 'img', 'aria-label': t('chartLangTitle', 'Pass@1 by language')
    });
    BY_LANG.forEach(function (d, i) {
      var pct = d.ok / d.total, y = i * rowH + 6, bw = Math.max(2, barMax * pct);
      svg.appendChild(el('text', { x: padL - 10, y: y + 15, class: 'chart__lbl',
        'text-anchor': 'end' })).textContent = d.lang;
      svg.appendChild(el('rect', { x: padL, y: y, width: barMax, height: 18,
        rx: 9, class: 'chart__track' }));
      var bar = el('rect', { x: padL, y: y, width: bw, height: 18, rx: 9,
        fill: 'var(--aurora-2)', class: 'chart__bar' });
      svg.appendChild(bar);
      svg.appendChild(el('text', { x: padL + bw + 8, y: y + 15,
        class: 'chart__val' })).textContent =
        Math.round(pct * 100) + '%  (' + d.ok + '/' + d.total + ')';
    });
    host.appendChild(svg);
  }

  // A single stacked bar: how the 261 tasks resolved.
  function renderOutcomes(host) {
    host.textContent = '';
    var total = OUTCOMES.reduce(function (s, d) { return s + d.n; }, 0);
    var w = 520, h = 90, barY = 8, barH = 30, x = 0;
    var svg = el('svg', { viewBox: '0 0 ' + w + ' ' + h, class: 'chart__svg',
      role: 'img', 'aria-label': t('chartOutTitle', 'Generation outcomes') });
    var legendY = barY + barH + 30;
    OUTCOMES.forEach(function (d) {
      var seg = (d.n / total) * w;
      svg.appendChild(el('rect', { x: x, y: barY, width: Math.max(1, seg - 2),
        height: barH, rx: 6, fill: d.color, class: 'chart__seg' }));
      svg.appendChild(el('text', { x: x + 4, y: barY + barH / 2 + 4,
        class: 'chart__seg-n' })).textContent = d.n;
      x += seg;
    });
    var lx = 0;
    OUTCOMES.forEach(function (d) {
      var g = el('g', {});
      g.appendChild(el('rect', { x: lx, y: legendY - 10, width: 12, height: 12,
        rx: 3, fill: d.color }));
      var lbl = el('text', { x: lx + 18, y: legendY, class: 'chart__legend' });
      lbl.textContent = t('out_' + d.key, d.key) + ' · ' +
        Math.round((d.n / total) * 100) + '%';
      g.appendChild(lbl);
      svg.appendChild(g);
      lx += 190;
    });
    host.appendChild(svg);
  }

  function draw() {
    var a = document.getElementById('chart-lang');
    var b = document.getElementById('chart-outcomes');
    if (a) renderByLang(a);
    if (b) renderOutcomes(b);
  }

  // Redraw on language change so labels/legends re-localise.
  document.addEventListener('DOMContentLoaded', function () {
    draw();
    document.querySelectorAll('.lang').forEach(function (btn) {
      btn.addEventListener('click', function () { setTimeout(draw, 0); });
    });
  });
})();
