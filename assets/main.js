(function () {
  // Pastga aylantirganda bo‘limlarni ohista ko‘rsatish
  var motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var revealItems = document.querySelectorAll('.rv');
  if (motionOk && 'IntersectionObserver' in window && revealItems.length) {
    document.documentElement.classList.add('rv-on');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    revealItems.forEach(function (el) { io.observe(el); });
  }

  // Sahifa aylantirilganda header soyasi
  var headerEl = document.querySelector('.site-header');
  if (headerEl) {
    var onScroll = function () { headerEl.classList.toggle('is-scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // Mobil menyu
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('sayt-menyu');
  if (toggle && nav) {
    var setOpen = function (open) {
      toggle.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('is-open', open);
    };
    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
        toggle.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !toggle.contains(e.target)) setOpen(false);
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) setOpen(false);
    });
    var wide = window.matchMedia('(min-width: 881px)');
    var onWide = function (e) { if (e.matches) setOpen(false); };
    if (wide.addEventListener) wide.addEventListener('change', onWide);
  }

  // Maqolalarni mavzu bo‘yicha filtrlash
  var group = document.querySelector('[data-filter]');
  if (!group) return;
  var buttons = Array.prototype.slice.call(group.querySelectorAll('button[data-value]'));
  var items = Array.prototype.slice.call(document.querySelectorAll('.post[data-category]'));
  var status = document.querySelector('[data-filter-status]');
  var empty = document.querySelector('[data-filter-empty]');

  function apply(value, updateUrl) {
    var shown = 0;
    buttons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.value === value));
    });
    items.forEach(function (item) {
      var match = value === 'all' || item.dataset.category === value;
      item.hidden = !match;
      if (match) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
    if (status) status.textContent = shown + ' ta maqola ko‘rsatilmoqda';
    if (updateUrl && window.history.replaceState) {
      var url = new URL(window.location.href);
      if (value === 'all') url.searchParams.delete('mavzu');
      else url.searchParams.set('mavzu', value);
      window.history.replaceState(null, '', url);
    }
  }

  group.hidden = false;
  buttons.forEach(function (b) {
    b.addEventListener('click', function () { apply(b.dataset.value, true); });
  });
  var initial = new URLSearchParams(window.location.search).get('mavzu');
  if (initial && buttons.some(function (b) { return b.dataset.value === initial; })) {
    apply(initial, false);
  }
})();
