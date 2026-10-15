/* ==========================================================================
   Admin panel behaviour. No framework, no build step.
   Everything degrades to a plain form post if JS is unavailable.
   ========================================================================== */
(() => {
  'use strict';

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const csrf = () => (document.querySelector('input[name=csrf_token]') || {}).value || '';

  /* ── sidebar on small screens ───────────────────────────────────────────── */
  const side = $('#side'), scrim = $('#scrim'), burger = $('#burger2');
  const sideSync = () => {
    const open = !!side?.classList.contains('is-open');
    if (scrim) scrim.hidden = !open;
    burger?.setAttribute('aria-expanded', String(open));
    burger?.setAttribute('aria-label', open ? 'Close the menu' : 'Menu');
  };
  const closeSide = () => { side?.classList.remove('is-open'); sideSync(); };
  burger?.addEventListener('click', () => { side?.classList.toggle('is-open'); sideSync(); });
  scrim?.addEventListener('click', closeSide);
  sideSync();

  // The open sidebar sits under the top bar, so it needs the bar's real height.
  const topbar = $('.top');
  const measureTop = () => {
    if (topbar) document.documentElement.style.setProperty('--top-h', topbar.offsetHeight + 'px');
  };
  measureTop();
  if (topbar && window.ResizeObserver) new ResizeObserver(measureTop).observe(topbar);
  window.addEventListener('resize', measureTop);

  /* ── phone: the "More" sheet ────────────────────────────────────────────── */
  (() => {
    const panel = $('#more-sheet');
    const openers = $$('[data-asheet-open]');
    if (!panel || !openers.length) return;
    const box = $('.asheet__box', panel);
    let opener = null;

    const focusables = () => $$('a[href], button:not([disabled])', box)
      .filter((el) => el.offsetParent !== null);

    const close = () => {
      panel.classList.remove('is-open');
      document.documentElement.style.overflow = '';
      openers.forEach((b) => b.setAttribute('aria-expanded', 'false'));
      setTimeout(() => { panel.hidden = true; }, 300);
      opener?.focus({ preventScroll: true });
      opener = null;
    };

    const open = (button) => {
      opener = button;
      panel.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      button.setAttribute('aria-expanded', 'true');
      // one frame between display and the class, or the slide-up never runs
      requestAnimationFrame(() => {
        panel.classList.add('is-open');
        focusables()[0]?.focus({ preventScroll: true });
      });
    };

    openers.forEach((b) => b.addEventListener('click', () => {
      if (panel.hidden) open(b); else close();
    }));
    panel.addEventListener('click', (event) => {
      if (event.target.closest('[data-asheet-close]') || event.target.closest('a')) close();
    });
    panel.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { close(); return; }
      if (event.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    window.adminSheetClose = close;
  })();

  /* ── phone: the app bar's back chevron ──────────────────────────────────── */
  $$('[data-back]').forEach((button) => {
    button.addEventListener('click', () => {
      const sameSite = document.referrer && document.referrer.startsWith(window.location.origin);
      if (sameSite && window.history.length > 1) window.history.back();
      else window.location.href = '/admin';
    });
  });

  /* ── print (kept out of the markup so the CSP needs no inline handlers) ─── */
  $$('[data-print]').forEach((el) => el.addEventListener('click', () => window.print()));

  /* ── flashes ────────────────────────────────────────────────────────────── */
  $$('.flash').forEach((el) => {
    const kill = () => { el.style.opacity = '0'; el.style.transform = 'translateX(14px)'; setTimeout(() => el.remove(), 240); };
    el.style.transition = 'opacity .22s, transform .22s';
    $('.flash__x', el)?.addEventListener('click', kill);
    setTimeout(kill, 6000);
  });

  function toast(message, isError) {
    let host = $('#flashes');
    if (!host) { host = document.createElement('div'); host.id = 'flashes'; host.className = 'flashes'; document.body.appendChild(host); }
    const el = document.createElement('div');
    el.className = 'flash' + (isError ? ' flash--error' : '');
    el.innerHTML = '<span></span><button class="flash__x" type="button" aria-label="Dismiss">&times;</button>';
    el.firstChild.textContent = message;
    host.appendChild(el);
    el.style.transition = 'opacity .22s, transform .22s';
    const kill = () => { el.style.opacity = '0'; setTimeout(() => el.remove(), 240); };
    $('.flash__x', el).addEventListener('click', kill);
    setTimeout(kill, 5000);
  }
  window.adminToast = toast;

  /* ── confirm before destructive posts ───────────────────────────────────── */
  document.addEventListener('submit', (event) => {
    const form = event.target;
    const question = form.dataset.confirm;
    if (question && !window.confirm(question)) event.preventDefault();
  });
  // Rows can be swapped in later by live search, so row-level behaviour is
  // bound through these functions and each element is only ever bound once.
  const bound = new WeakSet();
  const once = (el) => (bound.has(el) ? false : (bound.add(el), true));
  const rebinders = [];

  const bindConfirm = (root = document) => $$('button[data-confirm], a[data-confirm]', root).forEach((el) => {
    if (!once(el)) return;
    el.addEventListener('click', (event) => {
      if (el.closest('form') && el.type === 'submit') return;   // handled above
      if (!window.confirm(el.dataset.confirm)) event.preventDefault();
    });
  });
  bindConfirm();
  rebinders.push(bindConfirm);

  /* ── unsaved-changes guard ──────────────────────────────────────────────── */
  $$('form[data-guard]').forEach((form) => {
    let dirty = false;
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', () => { dirty = false; });
    window.addEventListener('beforeunload', (event) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });
  });

  /* ── colour inputs paired with a hex field ──────────────────────────────── */
  $$('input[data-colour-for]').forEach((swatch) => {
    const text = document.getElementById(swatch.dataset.colourFor);
    if (!text) return;
    swatch.addEventListener('input', () => { text.value = swatch.value.toUpperCase(); });
    text.addEventListener('input', () => {
      if (/^#[0-9a-f]{6}$/i.test(text.value)) swatch.value = text.value;
    });
  });

  /* ── slug helper: fill from a title until touched by hand ───────────────── */
  const slugify = (value) => value.toString().toLowerCase().trim()
    .replace(/[^a-z0-9\s-]/g, '').replace(/[\s-]+/g, '-').replace(/^-|-$/g, '');
  $$('input[name=slug]').forEach((slug) => {
    const form = slug.closest('form');
    const source = form && (form.querySelector('input[name=name]') || form.querySelector('input[name=title]'));
    if (!source) return;
    if (slug.value) slug.dataset.touched = '1';
    slug.addEventListener('input', () => { slug.dataset.touched = '1'; });
    source.addEventListener('input', () => {
      if (!slug.dataset.touched) slug.value = slugify(source.value);
    });
  });

  /* ── opening-hours rows ─────────────────────────────────────────────────── */
  $$('[data-hrow]').forEach((row) => {
    const closed = $('[data-hclosed]', row);
    const times = $$('input[type=time]', row);
    const sync = () => {
      row.classList.toggle('is-closed', closed.checked);
      times.forEach((t) => { t.disabled = closed.checked; });
    };
    closed.addEventListener('change', sync);
    sync();
  });

  /* ── media picker ───────────────────────────────────────────────────────── */
  const modal = $('#picker'), modalBody = $('#picker-body');
  let pickTarget = null, lastFocus = null;

  function openPicker(host) {
    pickTarget = host;
    lastFocus = document.activeElement;
    modal.hidden = false;
    modalBody.innerHTML = '<p class="hint">Loading the library…</p>';
    fetch('/admin/media/picker', { headers: { 'X-Requested-With': 'fetch' } })
      .then((r) => r.text())
      .then((html) => {
        modalBody.innerHTML = html;
        $('#picker-search', modalBody)?.focus();
        wirePicker();
      })
      .catch(() => { modalBody.innerHTML = '<p class="note note--warn">Could not load the media library.</p>'; });
  }

  function closePicker() {
    modal.hidden = true;
    pickTarget = null;
    lastFocus?.focus();
  }

  function wirePicker() {
    const search = $('#picker-search', modalBody);
    let timer = null;
    search?.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        fetch('/admin/media/picker?q=' + encodeURIComponent(search.value), { headers: { 'X-Requested-With': 'fetch' } })
          .then((r) => r.text())
          .then((html) => {
            const keep = search.value;
            modalBody.innerHTML = html;
            const again = $('#picker-search', modalBody);
            if (again) { again.value = keep; again.focus(); }
            wirePicker();
          });
      }, 260);
    });

    $$('.pitem', modalBody).forEach((item) => {
      item.addEventListener('click', () => {
        if (!pickTarget) return;
        const input = $('[data-pick-input]', pickTarget);
        const preview = $('[data-pick-preview]', pickTarget);
        const meta = $('[data-pick-meta]', pickTarget);
        input.value = item.dataset.id;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        preview.innerHTML = '<img src="' + item.dataset.thumb + '" alt="">';
        if (meta) meta.textContent = '#' + item.dataset.id + ' · ' + (item.dataset.alt || 'no alt text');
        closePicker();
      });
    });
  }

  $$('[data-pick]').forEach((host) => {
    $('[data-pick-open]', host)?.addEventListener('click', () => openPicker(host));
    $('[data-pick-clear]', host)?.addEventListener('click', () => {
      const input = $('[data-pick-input]', host);
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      $('[data-pick-preview]', host).textContent = 'No image';
      const meta = $('[data-pick-meta]', host);
      if (meta) meta.textContent = 'Nothing selected';
    });
  });
  $$('[data-picker-close]').forEach((b) => b.addEventListener('click', closePicker));
  modal?.addEventListener('click', (event) => { if (event.target === modal) closePicker(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (modal && !modal.hidden) closePicker();
      else closeSide();
    }
  });

  /* ── drag reorder for any table with data-reorder ───────────────────────── */
  const bindReorder = (root = document) => $$('[data-reorder]', root).forEach((table) => {
    if (!once(table)) return;
    const url = table.dataset.reorder;
    const body = $('tbody', table) || table;
    let dragged = null;

    const rows = () => $$('[data-id]', body);
    const persist = () => {
      const order = rows().map((r) => r.dataset.id);
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
        body: JSON.stringify({ order, ids: order }),
      })
        .then((r) => r.json())
        .then((data) => { if (data.ok) toast('Order saved.'); else toast('Could not save the order.', true); })
        .catch(() => toast('Could not save the order.', true));
    };

    /* Dragging does not exist on a touch screen, so every reorderable row also
       gets a pair of move buttons. CSS shows them only on the phone layout. */
    const arrow = (up) =>
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
      + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
      + (up ? '<path d="M12 19V5M6 11l6-6 6 6"/>' : '<path d="M12 5v14M6 13l6 6 6-6"/>')
      + '</svg>';

    const syncMoves = () => {
      const list = rows();
      list.forEach((row, at) => {
        const up = $('[data-move=up]', row);
        const down = $('[data-move=down]', row);
        if (up) up.disabled = at === 0;
        if (down) down.disabled = at === list.length - 1;
      });
    };

    const move = (row, delta) => {
      const list = rows();
      const to = list.indexOf(row) + delta;
      if (to < 0 || to >= list.length) return;
      if (delta < 0) row.parentNode.insertBefore(row, list[to]);
      else row.parentNode.insertBefore(list[to], row);
      persist();
      syncMoves();
    };

    rows().forEach((row) => {
      const handle = $('.drag', row);
      if (!handle) return;

      [['up', 'Move up'], ['down', 'Move down']].forEach(([dir, label]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'movebtn';
        button.dataset.move = dir;
        button.setAttribute('aria-label', label);
        button.innerHTML = arrow(dir === 'up');
        button.addEventListener('click', () => move(row, dir === 'up' ? -1 : 1));
        handle.appendChild(button);
      });

      handle.setAttribute('draggable', 'true');
      handle.addEventListener('dragstart', (event) => {
        dragged = row;
        row.classList.add('is-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', row.dataset.id);
      });
      handle.addEventListener('dragend', () => {
        row.classList.remove('is-dragging');
        rows().forEach((r) => r.classList.remove('is-over'));
        dragged = null;
        persist();
      });
      row.addEventListener('dragover', (event) => {
        if (!dragged || dragged === row) return;
        event.preventDefault();
        row.classList.add('is-over');
        const box = row.getBoundingClientRect();
        const after = (event.clientY - box.top) > box.height / 2;
        row.parentNode.insertBefore(dragged, after ? row.nextSibling : row);
      });
      row.addEventListener('dragleave', () => row.classList.remove('is-over'));

      // keyboard equivalent, because drag-and-drop alone is not accessible
      handle.setAttribute('tabindex', '0');
      handle.addEventListener('keydown', (event) => {
        const list = rows();
        const at = list.indexOf(row);
        if (event.key === 'ArrowUp' && at > 0) {
          event.preventDefault();
          row.parentNode.insertBefore(row, list[at - 1]);
          handle.focus(); persist(); syncMoves();
        } else if (event.key === 'ArrowDown' && at < list.length - 1) {
          event.preventDefault();
          row.parentNode.insertBefore(list[at + 1], row);
          handle.focus(); persist(); syncMoves();
        }
      });
    });

    syncMoves();
  });
  bindReorder();
  rebinders.push(bindReorder);

  /* ── select-all + bulk bar on list tables ───────────────────────────────── */
  const bindBulk = (root = document) => $$('[data-bulk]', root).forEach((form) => {
    if (!once(form)) return;
    const all = $('[data-bulk-all]', form);
    const boxes = $$('[data-bulk-item]', form);
    const bar = $('[data-bulk-bar]', form);
    const count = $('[data-bulk-count]', form);
    const sync = () => {
      const on = boxes.filter((b) => b.checked).length;
      if (bar) bar.hidden = on === 0;
      if (count) count.textContent = on + (on === 1 ? ' selected' : ' selected');
      if (all) all.checked = on === boxes.length && on > 0;
    };
    all?.addEventListener('change', () => { boxes.forEach((b) => { b.checked = all.checked; }); sync(); });
    boxes.forEach((b) => b.addEventListener('change', sync));
    sync();
  });
  bindBulk();
  rebinders.push(bindBulk);

  /* ── auto-submitting filter forms ───────────────────────────────────────── */
  $$('form[data-autofilter] select, form[data-autofilter] input[type=date]').forEach((el) => {
    el.addEventListener('change', () => el.form.submit());
  });

  /* ── <details> popovers: one open at a time, close on outside click/Esc ──── */
  const pops = $$('details[data-pop]');
  pops.forEach((pop) => {
    pop.addEventListener('toggle', () => {
      if (!pop.open) return;
      pops.forEach((other) => { if (other !== pop && !other.contains(pop)) other.open = false; });
      const panel = $('.pop__p', pop);
      if (panel) $('select, input:not([disabled]), button', panel)?.focus({ preventScroll: true });
    });
  });
  document.addEventListener('click', (event) => {
    pops.forEach((pop) => { if (pop.open && !pop.contains(event.target)) pop.open = false; });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = pops.find((pop) => pop.open);
    if (open) { open.open = false; $('summary', open)?.focus(); }
  });

  /* ── "/" jumps to the list search, as it does in most web apps ──────────── */
  const slash = $('[data-slash]');
  if (slash) {
    document.addEventListener('keydown', (event) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
      const tag = (document.activeElement?.tagName || '').toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag) || document.activeElement?.isContentEditable) return;
      event.preventDefault();
      slash.focus();
      slash.select();
    });
  }

  /* ── sidebar rail: the toolbar button or "[" folds the sidebar into its icons ── */
  const sideTog = $('#sidetog');
  const sideEl = $('#side');
  if (sideTog && sideEl) {
    const root = document.documentElement;
    const wide = () => window.matchMedia('(min-width: 1001px)').matches;
    const mini = () => root.classList.contains('side-mini');

    const tip = document.createElement('div');
    tip.className = 'sidetip';
    tip.setAttribute('aria-hidden', 'true');
    document.body.append(tip);
    let tipOff = 0;
    const hideTip = () => {
      clearTimeout(tipOff);
      tipOff = setTimeout(() => tip.classList.remove('is-on', 'is-gliding'), 90);
    };
    const showTip = (el) => {
      if (!mini() || !wide() || !el.dataset.tip) return;
      clearTimeout(tipOff);
      const box = el.getBoundingClientRect();
      const count = el.querySelector('b')?.textContent.trim();
      tip.textContent = count ? `${el.dataset.tip} · ${count} new` : el.dataset.tip;
      const gliding = tip.classList.contains('is-on');
      tip.classList.toggle('is-gliding', gliding);
      tip.style.left = `${sideEl.getBoundingClientRect().right + 10}px`;
      tip.style.top = `${box.top + box.height / 2}px`;
      if (!gliding) { void tip.offsetWidth; tip.classList.add('is-on'); }
    };
    sideEl.addEventListener('mouseover', (event) => {
      const el = event.target.closest('[data-tip]');
      if (el) showTip(el);
    });
    sideEl.addEventListener('mouseout', (event) => {
      const el = event.target.closest('[data-tip]');
      if (el && !el.contains(event.relatedTarget)) hideTip();
    });
    sideEl.addEventListener('focusin', (event) => {
      const el = event.target.closest('[data-tip]');
      if (el) showTip(el);
    });
    sideEl.addEventListener('focusout', hideTip);
    sideEl.addEventListener('scroll', () => tip.classList.remove('is-on', 'is-gliding'), { passive: true });

    const sync = () => {
      const label = mini() ? 'Expand the sidebar' : 'Collapse the sidebar';
      sideTog.setAttribute('aria-expanded', String(!mini()));
      sideTog.setAttribute('aria-label', label);
      sideTog.title = `${label}  [`;
    };
    let morph = 0;
    const flip = () => {
      if (!wide()) return;
      tip.classList.remove('is-on', 'is-gliding');
      sideEl.classList.remove('is-morph');
      void sideEl.offsetWidth;
      sideEl.classList.add('is-morph');
      root.classList.toggle('side-mini');
      try { localStorage.setItem('admin.side.mini', mini() ? '1' : '0'); } catch (e) { /* full */ }
      if (mini()) {
        $$('details[data-fold]:not([open])', sideEl).forEach((d) => { d.open = true; d.dataset.railOpen = ''; });
      } else {
        $$('details[data-rail-open]', sideEl).forEach((d) => {
          delete d.dataset.railOpen;
          if (!d.querySelector('.is-on')) d.open = false;
        });
      }
      sync();
      clearTimeout(morph);
      morph = setTimeout(() => sideEl.classList.remove('is-morph'), 900);
    };
    sideTog.addEventListener('click', flip);
    document.addEventListener('keydown', (event) => {
      if (event.key !== '[' || event.ctrlKey || event.metaKey || event.altKey) return;
      const tag = (document.activeElement?.tagName || '').toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag) || document.activeElement?.isContentEditable) return;
      event.preventDefault();
      flip();
    });
    sync();
  }

  /* ── column chooser ─────────────────────────────────────────────────────────
     A table opts in with data-cols="<key>" and a data-col name on each header.
     Headers marked data-lock cannot be hidden — the row's name and its actions.
     The choice is per browser, so each person keeps the view they need. */
  const colsReady = {};
  const setupCols = (table) => {
    const name = table.dataset.cols;
    if (colsReady[name]) { colsReady[name](); return; }
    const key = 'admin.cols.' + name;
    const heads = $$('thead th', table);
    const chooser = $(`details[data-colpick="${name}"]`);
    const list = chooser && $('[data-colpick-list]', chooser);
    let hidden = [];
    try { hidden = JSON.parse(localStorage.getItem(key) || '[]'); } catch (e) { hidden = []; }

    // Looks the table up each time: live search replaces it with a new one.
    const apply = () => {
      const live = $(`table[data-cols="${name}"]`);
      if (!live) return;
      $$('thead th', live).forEach((th, at) => {
        const off = !th.hasAttribute('data-lock') && hidden.includes(th.dataset.col);
        th.classList.toggle('col-off', off);
        $$('tbody tr', live).forEach((tr) => tr.children[at]?.classList.toggle('col-off', off));
      });
    };
    colsReady[name] = apply;
    const save = () => {
      try { localStorage.setItem(key, JSON.stringify(hidden)); } catch (e) { /* storage full or blocked */ }
      apply();
    };

    if (list) {
      heads.forEach((th) => {
        const name = th.dataset.col;
        const text = th.textContent.trim();
        if (!name || !text) return;            // the checkbox and action columns have no label
        const locked = th.hasAttribute('data-lock');
        const row = document.createElement('label');
        if (locked) row.className = 'is-locked';
        row.innerHTML = '<input type="checkbox"><span></span>';
        const box = row.firstChild;
        row.lastChild.textContent = text + (locked ? ' (always shown)' : '');
        box.checked = locked || !hidden.includes(name);
        box.disabled = locked;
        box.addEventListener('change', () => {
          hidden = box.checked ? hidden.filter((n) => n !== name) : hidden.concat(name);
          save();
        });
        list.appendChild(row);
      });
      $('[data-colpick-reset]', chooser)?.addEventListener('click', () => {
        hidden = [];
        $$('input', list).forEach((box) => { box.checked = true; });
        save();
      });
      chooser.hidden = false;
    }
    apply();
  };
  const bindCols = (root = document) => $$('table[data-cols]', root).forEach(setupCols);
  bindCols();
  rebinders.push(bindCols);

  /* ── inline toggles (publish switches in list rows) ─────────────────────── */
  const bindToggles = (root = document) => $$('[data-toggle-url]', root).forEach((box) => {
    if (!once(box)) return;
    box.addEventListener('change', () => {
      fetch(box.dataset.toggleUrl, { method: 'POST', headers: { 'X-CSRF-Token': csrf() } })
        .then((r) => r.json())
        .then((data) => {
          if (!data.ok) throw new Error();
          const row = box.closest('tr, .sitem');
          row?.classList.toggle('is-draft', !data.on);
          toast(data.on ? 'Published.' : 'Hidden from the site.');
        })
        .catch(() => { box.checked = !box.checked; toast('Could not change that.', true); });
    });
  });
  bindToggles();
  rebinders.push(bindToggles);

  /* ── live search ────────────────────────────────────────────────────────────
     A list's search box re-runs the search as you type. The server renders the
     same page as for a normal submit, and only the parts marked data-live are
     swapped in, so filters, paging and counts all stay exactly as the server
     decides. Without JS the box still searches on Enter. */
  $$('form input[type=search][name=q]').forEach((input) => {
    const form = input.form;
    if (!form || (form.getAttribute('method') || 'get').toLowerCase() !== 'get') return;
    if (!$('[data-live]')) return;
    let timer = 0;
    let ctrl = null;
    let last = input.value.trim();

    const target = () => {
      const params = new URLSearchParams();
      new FormData(form).forEach((value, key) => {
        if (key !== 'page' && String(value).trim() !== '') params.append(key, String(value).trim());
      });
      const path = form.getAttribute('action') || location.pathname;
      return path + (params.toString() ? '?' + params : '');
    };

    const swap = (doc) => {
      $$('[data-live]').forEach((region) => {
        const fresh = doc.querySelector(`[data-live="${region.dataset.live}"]`);
        if (!fresh) { region.replaceChildren(); return; }
        const node = document.importNode(fresh, true);
        node.classList.add('is-fresh');
        region.replaceWith(node);
        rebinders.forEach((bind) => bind(node));
        setTimeout(() => node.classList.remove('is-fresh'), 500);
      });
    };

    const run = () => {
      const q = input.value.trim();
      if (q === last) return;
      last = q;
      const url = target();
      ctrl?.abort();
      ctrl = new AbortController();
      $$('[data-live]').forEach((r) => r.classList.add('is-loading'));
      fetch(url, { signal: ctrl.signal, credentials: 'same-origin', headers: { 'X-Live-Search': '1' } })
        .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
        .then((html) => {
          swap(new DOMParser().parseFromString(html, 'text/html'));
          history.replaceState(null, '', url);
        })
        .catch((err) => {
          if (err.name === 'AbortError') return;
          $$('[data-live]').forEach((r) => r.classList.remove('is-loading'));
          toast('Search could not be refreshed. Press Enter to try again.', true);
          last = null;
        });
    };

    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 180); });
    input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      clearTimeout(timer);
      if (last === null) last = undefined;
      run();
    });
  });

  /* ── section type chooser filter ────────────────────────────────────────── */
  const typeFilter = $('#type-filter');
  typeFilter?.addEventListener('input', () => {
    const needle = typeFilter.value.toLowerCase();
    $$('.typecard').forEach((card) => {
      card.hidden = needle && !card.textContent.toLowerCase().includes(needle);
    });
  });

  /* ── media library upload ───────────────────────────────────────────────── */
  const drop = $('#drop');
  if (drop) {
    const input = $('#drop-input');
    const stop = (event) => { event.preventDefault(); event.stopPropagation(); };
    ['dragenter', 'dragover'].forEach((name) => drop.addEventListener(name, (e) => { stop(e); drop.classList.add('is-over'); }));
    ['dragleave', 'drop'].forEach((name) => drop.addEventListener(name, (e) => { stop(e); drop.classList.remove('is-over'); }));
    drop.addEventListener('drop', (event) => { if (event.dataTransfer.files.length) send(event.dataTransfer.files); });
    input?.addEventListener('change', () => { if (input.files.length) send(input.files); });

    function send(files) {
      const status = $('#drop-status');
      let done = 0, failed = 0;
      const total = files.length;
      const tick = () => {
        if (status) status.textContent = `Uploading ${done + failed} of ${total}…`;
        if (done + failed === total) {
          if (failed) toast(`${failed} file${failed === 1 ? '' : 's'} could not be uploaded.`, true);
          window.location.reload();
        }
      };
      Array.from(files).forEach((file) => {
        const body = new FormData();
        body.append('files', file);
        body.append('csrf_token', csrf());
        fetch('/admin/media/upload', { method: 'POST', body, headers: { 'X-Requested-With': 'fetch' } })
          .then((r) => r.json())
          .then((data) => { data.ok ? done++ : failed++; tick(); })
          .catch(() => { failed++; tick(); });
      });
      tick();
    }
  }

  /* ── EMI quote preview inside the admin application form ────────────────── */
  // Same arithmetic as core/emi.py quote(): the fee is charged on the financed part.
  const rupees = (n) => '₹' + Math.round(n).toLocaleString('en-IN');
  const emiQuote = (amount, ds) => {
    const tenure = Math.max(1, parseInt(ds.tenure, 10) || 1);
    const rate = parseFloat(ds.rate || '0');
    const down = amount * parseFloat(ds.down || '0') / 100;
    const financed = amount - down;
    const fee = financed * parseFloat(ds.fee || '0') / 100;
    let monthly = financed / tenure;
    if (rate > 0) { const r = rate / 1200; const f = Math.pow(1 + r, tenure); monthly = financed * r * f / (f - 1); }
    monthly = Math.round(monthly * 100) / 100;
    return { tenure, down, fee, financed, monthly, total: down + fee + monthly * tenure };
  };
  const planEligible = (amount, ds) => {
    const min = parseFloat(ds.min || '0'); const max = parseFloat(ds.max || '0');
    return !(min && amount < min) && !(max && amount > max);
  };

  $$('[data-emi-quote]').forEach((emiForm) => {
    const out = $('[data-emi-out]', emiForm);
    const sum = (key, text) => { const el = $(`[data-emi-sum="${key}"]`, emiForm); if (el) el.textContent = text; };
    const recalc = () => {
      const amount = parseFloat($('[name=treatment_amount]', emiForm)?.value || '0');

      // Plan cards: every card shows its own monthly figure, and plans that do
      // not cover this amount are switched off rather than silently accepted.
      $$('[data-plan-card]', emiForm).forEach((card) => {
        const input = $('input', card);
        const ok = !amount || planEligible(amount, input.dataset);
        card.classList.toggle('is-off', !ok);
        input.disabled = !ok;
        if (!ok && input.checked) input.checked = false;
        const q = $('[data-plan-q]', card);
        if (!ok) q.innerHTML = '<small>Not for this amount</small>';
        else if (amount) q.innerHTML = `${rupees(emiQuote(amount, input.dataset).monthly)}<small> / month</small>`;
        else q.innerHTML = '<small>Enter the cost first</small>';
      });

      const picked = $('[name=plan_id]:checked', emiForm) || $('select[name=plan_id]', emiForm)?.selectedOptions[0];
      if (!amount || !picked || !picked.dataset.tenure) {
        if (out) out.textContent = '';
        return;
      }
      const q = emiQuote(amount, picked.dataset);
      if (out) {
        out.textContent = `${rupees(q.monthly)} × ${q.tenure} months`
          + (q.down ? ` · ${rupees(q.down)} down` : '') + (q.fee ? ` · ${rupees(q.fee)} fee` : '');
      }
      sum('amount', rupees(amount));
      sum('plan', picked.dataset.name || `${q.tenure} months`);
      sum('down', q.down ? rupees(q.down) : 'Nothing');
      sum('fee', q.fee ? rupees(q.fee) : 'None');
      sum('monthly', `${rupees(q.monthly)} × ${q.tenure}`);
      sum('total', rupees(q.total));
    };
    emiForm.addEventListener('input', recalc);
    emiForm.addEventListener('change', recalc);
    recalc();
  });

  /* ── step-by-step forms ─────────────────────────────────────────────────────
     data-wiz on a form, data-wiz-pane per step. Continue only moves on once the
     current step is valid, so the form cannot be filed half-filled. Without JS
     every step shows at once and the server does the same checks. */
  $$('form[data-wiz]').forEach((form) => {
    const panes = $$('[data-wiz-pane]', form);
    const steps = $$('[data-wiz-step]', form);
    const back = $('[data-wiz-back]', form);
    const next = $('[data-wiz-next]', form);
    const submit = $('[data-wiz-submit]', form);
    const why = $('[data-wiz-why]', form);
    let at = 0;

    const inDialog = !!form.closest('dialog');
    const valueOf = (key) => {
      if (key === 'treatment') {
        const sel = $('[name=service_id]', form);
        return sel?.value ? sel.selectedOptions[0].textContent.trim()
          : ($('[name=treatment_label]', form)?.value.trim() || 'Not on the list');
      }
      const radio = $(`[name="${key}"]:checked`, form);
      if (radio) return radio.dataset.label || radio.closest('label')?.textContent.trim() || radio.value;
      const el = $(`[name="${key}"]`, form);
      if (!el || el.closest('[hidden]')) return '';
      if (el.tagName === 'SELECT') return el.value ? el.selectedOptions[0].textContent.trim() : '';
      if (el.type === 'date') {
        const d = el.valueAsDate;
        return d ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
      }
      if ('money' in el.dataset) return el.value ? rupees(parseFloat(el.value)) : '';
      return el.value.trim();
    };
    const fill = () => {
      $$('[data-rv]', form).forEach((dd) => { dd.textContent = valueOf(dd.dataset.rv) || '—'; });
    };

    const invalid = (pane) => {
      // A required radio group still counts when every option is switched off,
      // otherwise a step with no usable plan would let the user straight through.
      const fields = $$('input, select, textarea', pane)
        .filter((el) => el.type !== 'hidden' && el.closest('[hidden]') === null);
      for (const el of fields) {
        if (el.type === 'radio') {
          if (el.required && !$$(`[name="${el.name}"]`, pane).some((r) => r.checked)) {
            const usable = $$(`[name="${el.name}"]`, pane).find((r) => !r.disabled);
            return { el: usable || el, msg: usable ? 'Choose one of the options to continue.'
              : 'None of the plans covers this amount. Go back and check the cost.' };
          }
        } else if (!el.disabled && !el.checkValidity()) {
          const label = $(`label[for="${el.id}"]`, pane)?.firstChild?.textContent.trim() || 'This field';
          return { el, msg: el.validity.valueMissing ? `${label} is needed.` : `Check the ${label.toLowerCase()}.` };
        }
      }
      return null;
    };

    const show = (i, focus = true) => {
      at = Math.max(0, Math.min(panes.length - 1, i));
      panes.forEach((p, n) => p.classList.toggle('is-on', n === at));
      steps.forEach((s, n) => {
        s.classList.toggle('is-on', n === at);
        s.classList.toggle('is-done', n < at);
        s.style.cursor = n < at ? 'pointer' : '';
      });
      back.hidden = at === 0;
      next.hidden = at === panes.length - 1;
      submit.hidden = at !== panes.length - 1;
      why.textContent = '';
      $$('.is-bad', panes[at]).forEach((el) => el.addEventListener('input', () => el.classList.remove('is-bad'), { once: true }));
      if (at === panes.length - 1) fill();
      if (focus) {
        if (!inDialog) form.scrollIntoView({ block: 'start', behavior: 'smooth' });
        $('input:not([type=hidden]):not([disabled]), select, textarea', panes[at])?.focus({ preventScroll: true });
      }
    };

    const forward = () => {
      const bad = invalid(panes[at]);
      if (bad) {
        why.textContent = bad.msg;
        bad.el.classList.add('is-bad');
        bad.el.focus();
        bad.el.addEventListener('input', () => { bad.el.classList.remove('is-bad'); why.textContent = ''; }, { once: true });
        return;
      }
      show(at + 1);
    };

    next.addEventListener('click', forward);
    back.addEventListener('click', () => show(at - 1));
    steps.forEach((s, n) => s.addEventListener('click', () => { if (n < at) show(n); }));

    // Enter in a field moves on a step instead of filing an unfinished form.
    form.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.target.tagName === 'TEXTAREA') return;
      if (at < panes.length - 1) { event.preventDefault(); forward(); }
    });
    form.addEventListener('submit', (event) => {
      for (let n = 0; n < panes.length; n++) {
        if (invalid(panes[n])) { event.preventDefault(); show(n); forward(); return; }
      }
    });

    // Lets a dialog send the flow back to its first step each time it opens.
    form.addEventListener('wiz:goto', (event) => show(event.detail || 0, true));

    // After a server-side refusal, open on the first step that has a problem.
    const first = panes.findIndex((p) => $('.is-bad, .ferr', p));
    show(first < 0 ? 0 : first, first >= 0);
  });

  /* ── <dialog> openers ───────────────────────────────────────────────────────
     data-dlg-open="<id>" opens a dialog, data-dlg-close closes the one it sits
     in, and a click on the backdrop closes it too. */
  $$('[data-dlg-open]').forEach((btn) => btn.addEventListener('click', () => {
    const dlg = document.getElementById(btn.dataset.dlgOpen);
    if (!dlg || dlg.open) return;
    btn.closest('details[open]')?.removeAttribute('open');
    dlg.showModal();
    $('form[data-wiz]', dlg)?.dispatchEvent(new CustomEvent('wiz:goto', { detail: 0 }));
  }));
  $$('dialog.dlg').forEach((dlg) => {
    dlg.addEventListener('click', (event) => { if (event.target === dlg) dlg.close(); });
    $$('[data-dlg-close]', dlg).forEach((b) => b.addEventListener('click', () => dlg.close()));
  });

  /* ── animate dashboard bars once laid out ───────────────────────────────── */
  requestAnimationFrame(() => $$('.bar__f').forEach((f) => { f.style.width = f.style.width; }));
})();
