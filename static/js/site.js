/* ==========================================================================
   Anvaya Dental Care — public behaviour
   Vanilla ES2020, no dependencies. Every effect checks prefers-reduced-motion
   and the theme.animations setting before it runs.
   ========================================================================== */

(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animate = document.body.dataset.anim !== '0' && !reduced;
  const inr = (n) => '\u20b9' + Math.round(n || 0).toLocaleString('en-IN');

  /* ── scroll reveal ─────────────────────────────────────────────────────── */
  function reveal() {
    const items = $$('.rv');
    if (!animate || !('IntersectionObserver' in window)) {
      items.forEach((el) => el.classList.add('is-in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.06 });
    items.forEach((el) => io.observe(el));
  }

  /* ── header ────────────────────────────────────────────────────────────── */
  function header() {
    const head = $('#head');
    const bar = $('#scrollbar');
    if (!head) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      const y = window.scrollY;
      head.classList.toggle('is-stuck', y > 12);
      if (bar) {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.width = (max > 0 ? (y / max) * 100 : 0) + '%';
      }
    };
    window.addEventListener('scroll', () => {
      if (!frame) frame = requestAnimationFrame(paint);
    }, { passive: true });
    paint();
  }

  /* ── active nav ────────────────────────────────────────────────────────── */
  function activeNav() {
    const links = $$('.mainnav__a');
    const path = window.location.pathname;
    links.forEach((a) => {
      const href = a.getAttribute('href') || '';
      const clean = href.split('#')[0];
      if (clean && clean !== '/' && path.startsWith(clean)) a.classList.add('is-on');
      else if (href === path) a.classList.add('is-on');
    });

    const anchors = links.filter((a) => (a.getAttribute('href') || '').includes('#'));
    if (!anchors.length || !('IntersectionObserver' in window)) return;
    const targets = anchors
      .map((a) => {
        const id = (a.getAttribute('href') || '').split('#')[1];
        const el = id ? document.getElementById(id) : null;
        return el ? { a, el } : null;
      })
      .filter(Boolean);
    if (!targets.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        const match = targets.find((t) => t.el === entry.target);
        if (match) match.a.classList.toggle('is-on', entry.isIntersecting);
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    targets.forEach((t) => io.observe(t.el));
  }

  /* ── drawer ────────────────────────────────────────────────────────────── */
  function drawer() {
    const burger = $('.burger');
    const panel = $('#drawer');
    if (!burger || !panel) return;

    const setOpen = (open) => {
      burger.setAttribute('aria-expanded', String(open));
      panel.hidden = !open;
      document.documentElement.style.overflow = open ? 'hidden' : '';
      if (open) {
        const first = $('.drawer__a', panel);
        if (first) first.focus({ preventScroll: true });
      }
    };

    burger.addEventListener('click', () => setOpen(panel.hidden));
    panel.addEventListener('click', (e) => {
      if (e.target.closest('a')) setOpen(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !panel.hidden) {
        setOpen(false);
        burger.focus();
      }
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 900 && !panel.hidden) setOpen(false);
    });
  }

  /* ── bottom sheet ──────────────────────────────────────────────────────
     The phone layout swaps the burger drawer for a sheet that slides up from
     the tab bar. It behaves like a modal: scrim, Escape, trapped focus and a
     locked page behind it. */
  function sheets() {
    const openers = $$('[data-sheet-open]');
    if (!openers.length) return;
    let lastOpener = null;

    const focusables = (panel) =>
      $$('a[href], button:not([disabled]), input, select, textarea', panel)
        .filter((el) => el.offsetParent !== null);

    const close = (panel) => {
      panel.classList.remove('is-open');
      document.documentElement.style.overflow = '';
      openers.forEach((b) => {
        if (b.getAttribute('aria-controls') === panel.id) b.setAttribute('aria-expanded', 'false');
      });
      const done = () => { panel.hidden = true; };
      if (reduced) done();
      else window.setTimeout(done, 300);
      if (lastOpener) { lastOpener.focus({ preventScroll: true }); lastOpener = null; }
    };

    const open = (panel, opener) => {
      lastOpener = opener || null;
      panel.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      if (opener) opener.setAttribute('aria-expanded', 'true');
      // one frame between display and the class, or the slide-up never runs
      requestAnimationFrame(() => {
        panel.classList.add('is-open');
        const first = focusables($('.sheet__box', panel) || panel)[0];
        if (first) first.focus({ preventScroll: true });
      });
    };

    openers.forEach((opener) => {
      const panel = document.getElementById(opener.dataset.sheetOpen);
      if (!panel) return;
      opener.addEventListener('click', () => {
        if (panel.hidden) open(panel, opener); else close(panel);
      });
    });

    $$('.sheet').forEach((panel) => {
      panel.addEventListener('click', (e) => {
        if (e.target.closest('[data-sheet-close]') || e.target.closest('a')) close(panel);
      });
      panel.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { close(panel); return; }
        if (e.key !== 'Tab') return;
        const items = focusables($('.sheet__box', panel) || panel);
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      });
    });
  }

  /* ── app bar that gets out of the way ──────────────────────────────────
     Only on a phone, and only once you are past the hero: scrolling down hands
     the screen back to the content, scrolling up brings the bar straight back,
     which is what every shopping app does. */
  function appBar() {
    const head = $('#head');
    if (!head) return;
    const phone = window.matchMedia('(max-width: 760px)');
    let last = window.scrollY;
    let frame = 0;

    const paint = () => {
      frame = 0;
      const y = window.scrollY;
      if (!phone.matches) { head.classList.remove('is-away'); last = y; return; }
      const down = y > last + 6;
      const up = y < last - 6;
      if (down && y > 220) head.classList.add('is-away');
      else if (up) head.classList.remove('is-away');
      if (down || up) last = y;
    };

    window.addEventListener('scroll', () => {
      if (!frame) frame = requestAnimationFrame(paint);
    }, { passive: true });
  }

  /* ── counters ──────────────────────────────────────────────────────────── */
  function counters() {
    const nodes = $$('[data-count-to]');
    if (!nodes.length) return;
    if (!animate || !('IntersectionObserver' in window)) {
      nodes.forEach((n) => { n.textContent = Number(n.dataset.countTo || 0).toLocaleString('en-IN'); });
      return;
    }
    const run = (node) => {
      const target = parseFloat(node.dataset.countTo || '0');
      const start = performance.now();
      const dur = 1500;
      const tick = (now) => {
        const p = Math.min(1, (now - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        const value = target * eased;
        node.textContent = (target >= 100 ? Math.round(value) : Math.round(value * 10) / 10)
          .toLocaleString('en-IN');
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          run(entry.target);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });
    nodes.forEach((n) => io.observe(n));
  }

  /* ── parallax ──────────────────────────────────────────────────────────── */
  function parallax() {
    const nodes = $$('[data-parallax]');
    if (!nodes.length || !animate || window.innerWidth < 900) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      nodes.forEach((node) => {
        const rect = node.getBoundingClientRect();
        if (rect.bottom < -200 || rect.top > window.innerHeight + 200) return;
        const centre = rect.top + rect.height / 2 - window.innerHeight / 2;
        const shift = -centre * parseFloat(node.dataset.parallax || '0.05');
        const img = node.querySelector('img');
        if (img) img.style.transform = `translate3d(0, ${shift.toFixed(1)}px, 0) scale(1.06)`;
      });
    };
    window.addEventListener('scroll', () => {
      if (!frame) frame = requestAnimationFrame(paint);
    }, { passive: true });
    paint();
  }

  /* ── FAQ accordion ─────────────────────────────────────────────────────── */
  function faqs() {
    $$('[data-faqs]').forEach((group) => {
      const items = $$('.faq', group);
      items.forEach((item) => {
        const button = $('.faq__q', item);
        const panel = $('.faq__a', item);
        if (!button || !panel) return;

        const close = () => {
          item.classList.remove('is-open');
          button.setAttribute('aria-expanded', 'false');
          panel.style.height = '0px';
        };
        const open = () => {
          items.forEach((other) => { if (other !== item) closeItem(other); });
          item.classList.add('is-open');
          button.setAttribute('aria-expanded', 'true');
          panel.style.height = panel.firstElementChild.offsetHeight + 'px';
        };
        button.addEventListener('click', () => {
          if (item.classList.contains('is-open')) close(); else open();
        });
        panel.style.height = '0px';
      });

      function closeItem(item) {
        const button = $('.faq__q', item);
        const panel = $('.faq__a', item);
        item.classList.remove('is-open');
        if (button) button.setAttribute('aria-expanded', 'false');
        if (panel) panel.style.height = '0px';
      }

      window.addEventListener('resize', () => {
        items.forEach((item) => {
          if (!item.classList.contains('is-open')) return;
          const panel = $('.faq__a', item);
          if (panel) panel.style.height = panel.firstElementChild.offsetHeight + 'px';
        });
      });
    });
  }

  /* ── gallery lightbox ──────────────────────────────────────────────────── */
  function lightbox() {
    const buttons = $$('[data-gallery] .mosaic__i');
    if (!buttons.length) return;

    const box = document.createElement('div');
    box.className = 'lightbox';
    box.hidden = true;
    box.innerHTML = `
      <span class="lightbox__count"></span>
      <button class="lightbox__x" type="button" aria-label="Close">
        <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/></svg>
      </button>
      <button class="lightbox__nav lightbox__nav--prev" type="button" aria-label="Previous">
        <svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/></svg>
      </button>
      <button class="lightbox__nav lightbox__nav--next" type="button" aria-label="Next">
        <svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/></svg>
      </button>
      <div><img alt=""><p class="lightbox__cap"></p></div>`;
    document.body.appendChild(box);

    const img = $('img', box);
    const cap = $('.lightbox__cap', box);
    const count = $('.lightbox__count', box);
    let index = 0;
    let opener = null;

    const show = (i) => {
      index = (i + buttons.length) % buttons.length;
      const button = buttons[index];
      img.src = button.dataset.full || $('img', button).src;
      img.alt = button.dataset.cap || '';
      cap.textContent = button.dataset.cap || '';
      count.textContent = `${index + 1} / ${buttons.length}`;
    };
    const open = (i, source) => {
      opener = source;
      show(i);
      box.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      $('.lightbox__x', box).focus();
    };
    const close = () => {
      box.hidden = true;
      document.documentElement.style.overflow = '';
      if (opener) opener.focus();
    };

    buttons.forEach((button, i) => button.addEventListener('click', () => open(i, button)));
    $('.lightbox__x', box).addEventListener('click', close);
    $('.lightbox__nav--prev', box).addEventListener('click', () => show(index - 1));
    $('.lightbox__nav--next', box).addEventListener('click', () => show(index + 1));
    box.addEventListener('click', (e) => { if (e.target === box) close(); });
    document.addEventListener('keydown', (e) => {
      if (box.hidden) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowRight') show(index + 1);
      if (e.key === 'ArrowLeft') show(index - 1);
    });
  }

  /* ── chip groups ───────────────────────────────────────────────────────── */
  function chips() {
    $$('[data-chips]').forEach((group) => {
      const target = group.parentElement.querySelector('[data-chip-target]');
      $$('.chip', group).forEach((chip) => {
        chip.addEventListener('click', () => {
          const on = chip.classList.contains('is-on');
          $$('.chip', group).forEach((c) => c.classList.remove('is-on'));
          if (!on) chip.classList.add('is-on');
          if (target) target.value = on ? '' : (chip.dataset.chipValue || '');
        });
      });
    });
  }

  /* ── enquiry forms ─────────────────────────────────────────────────────── */
  function enquiryForms() {
    $$('[data-enquiry]').forEach((form) => {
      const msg = $('[data-enquiry-msg]', form);
      const done = form.parentElement.querySelector('[data-enquiry-done]');

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const button = $('button[type=submit]', form);
        if (button) { button.disabled = true; button.textContent = 'Sending\u2026'; }
        if (msg) { msg.textContent = ''; msg.className = 'fmsg'; }

        try {
          const response = await fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'fetch' },
          });
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error((data.errors || ['Something went wrong.']).join(' '));

          if (done) {
            const ref = $('[data-done-ref]', done);
            const title = $('[data-done-title]', done);
            const body = $('[data-done-body]', done);
            if (ref) ref.textContent = data.ref;
            if (title && data.title) title.textContent = data.title;
            if (body && data.body) body.textContent = data.body;
            form.hidden = true;
            done.hidden = false;
            done.scrollIntoView({ behavior: animate ? 'smooth' : 'auto', block: 'center' });
          } else {
            window.location.href = '/thank-you?ref=' + encodeURIComponent(data.ref);
          }
        } catch (error) {
          if (msg) { msg.textContent = error.message; msg.className = 'fmsg fmsg--bad'; }
          if (button) { button.disabled = false; button.textContent = 'Request an appointment'; }
        }
      });
    });
  }

  /* ── EMI calculator ────────────────────────────────────────────────────── */
  function calculators() {
    $$('[data-calc]').forEach((root) => {
      let plans = [];
      try { plans = JSON.parse(root.dataset.plans || '[]'); } catch (e) { plans = []; }
      if (!plans.length) {
        const note = $('[data-calc-note]', root);
        if (note) note.textContent = 'No instalment plans are active. Add one in the admin panel.';
        return;
      }

      const amountIn = $('[data-calc-amount]', root);
      const range = $('[data-calc-range]', root);
      const pillWrap = $('[data-calc-plans]', root);
      const out = {
        emi: $('[data-calc-emi]', root),
        tenure: $('[data-calc-tenure]', root),
        down: $('[data-calc-down]', root),
        extra: $('[data-calc-extra]', root),
        total: $('[data-calc-total]', root),
        note: $('[data-calc-note]', root),
      };
      const form = $('[data-emi-form]', root);
      const doneBox = $('[data-emi-done]', root);
      const applyBtn = $('[data-calc-apply]', root);

      let amount = parseInt(root.dataset.default || '60000', 10);
      let planId = plans[0].id;

      const quote = (plan, value) => {
        const downAmt = Math.round((value * (plan.down_pct || 0)) / 100);
        const financed = value - downAmt;
        const fee = Math.round((financed * (plan.fee_pct || 0)) / 100);
        let emi;
        if (!plan.rate) {
          emi = financed / plan.tenure;
        } else {
          const r = plan.rate / 1200;
          const growth = Math.pow(1 + r, plan.tenure);
          emi = (financed * r * growth) / (growth - 1);
        }
        const totalEmis = emi * plan.tenure;
        return {
          down: downAmt,
          financed,
          fee,
          emi,
          extra: totalEmis - financed + fee,
          total: downAmt + totalEmis + fee,
        };
      };

      const eligible = (plan) => (!plan.min || amount >= plan.min) && (!plan.max || amount <= plan.max);

      /* built once; paint() only updates their state, so a pill keeps its
         focus and its identity while the amount is being typed */
      const pills = plans.map((plan) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'tenure';
        button.setAttribute('aria-pressed', 'false');
        button.innerHTML = `${plan.tenure} months<small>${plan.rate ? plan.rate + '% p.a.' : 'no cost'}</small>`;
        button.addEventListener('click', () => { planId = plan.id; paint(); });
        pillWrap.appendChild(button);
        return { plan, button };
      });

      const paintPills = () => {
        pills.forEach(({ plan, button }) => {
          const ok = eligible(plan);
          button.classList.toggle('is-on', plan.id === planId);
          button.setAttribute('aria-pressed', String(plan.id === planId));
          button.disabled = !ok;
          button.title = ok
            ? plan.notes || ''
            : `Needs ${inr(plan.min)}${plan.max ? ' to ' + inr(plan.max) : ' or more'}`;
        });
      };

      const paint = () => {
        let plan = plans.find((p) => p.id === planId);
        if (!plan || !eligible(plan)) {
          plan = plans.find(eligible) || plans[0];
          planId = plan.id;
        }
        const q = quote(plan, amount);

        if (amountIn && document.activeElement !== amountIn) amountIn.value = inr(amount);
        if (range) range.value = String(Math.min(Number(range.max), amount));
        if (out.emi) out.emi.textContent = inr(q.emi);
        if (out.tenure) out.tenure.textContent = plan.tenure;
        if (out.down) out.down.textContent = q.down ? inr(q.down) : 'Nothing';
        if (out.extra) out.extra.textContent = q.extra > 1 ? inr(q.extra) : 'Nil';
        if (out.total) out.total.textContent = inr(q.total);

        const extraCell = root.querySelector('[data-calc-cell="extra"]');
        if (extraCell) extraCell.classList.toggle('is-free', q.extra <= 1);

        if (out.note) {
          if (!eligible(plan)) {
            out.note.textContent = 'That amount is outside every active plan. Ring reception and we will look at it.';
          } else if (!plan.rate && !plan.fee_pct) {
            out.note.textContent = `${plan.name}: you pay the treatment price and nothing more.`;
          } else {
            out.note.textContent = `${plan.name}: ${plan.rate}% a year on ${inr(q.financed)}` +
              (q.fee ? `, plus a ${inr(q.fee)} processing fee.` : '.');
          }
        }

        paintPills();
        if (form) {
          const a = $('[data-emi-amount]', form);
          const p = $('[data-emi-plan]', form);
          if (a) a.value = String(amount);
          if (p) p.value = String(planId);
        }
      };

      if (range) {
        range.addEventListener('input', () => { amount = parseInt(range.value, 10); paint(); });
      }
      if (amountIn) {
        amountIn.addEventListener('input', () => {
          const digits = amountIn.value.replace(/[^\d]/g, '');
          amount = Math.max(0, parseInt(digits || '0', 10));
          paint();
        });
        amountIn.addEventListener('blur', () => {
          amount = Math.max(5000, amount);
          paint();
        });
      }
      if (applyBtn && form) {
        applyBtn.addEventListener('click', () => {
          form.hidden = false;
          applyBtn.hidden = true;
          const first = $('input', form);
          if (first) first.focus();
          form.scrollIntoView({ behavior: animate ? 'smooth' : 'auto', block: 'center' });
        });
      }
      if (form) {
        const msg = $('[data-emi-msg]', form);
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const button = $('button[type=submit]', form);
          if (button) { button.disabled = true; button.textContent = 'Sending\u2026'; }
          if (msg) { msg.textContent = ''; msg.className = 'fmsg'; }
          try {
            const response = await fetch(form.action, {
              method: 'POST',
              body: new FormData(form),
              headers: { 'X-Requested-With': 'fetch' },
            });
            const data = await response.json();
            if (!response.ok || !data.ok) throw new Error((data.errors || ['Something went wrong.']).join(' '));
            form.hidden = true;
            if (doneBox) {
              const ref = $('[data-emi-ref]', doneBox);
              if (ref) ref.textContent = data.ref;
              doneBox.hidden = false;
            }
          } catch (error) {
            if (msg) { msg.textContent = error.message; msg.className = 'fmsg fmsg--bad'; }
            if (button) { button.disabled = false; button.textContent = 'Send application'; }
          }
        });
      }

      paint();
    });
  }

  /* ── live google rating in the hero ────────────────────────────────────── */
  function liveRating() {
    const box = $('[data-live-rating]');
    if (!box) return;
    fetch('/api/rating')
      .then((r) => r.json())
      .then((data) => {
        if (!data || !data.rating) { box.remove(); return; }
        const value = $('[data-rating-value]', box);
        const text = $('[data-rating-text]', box);
        if (value) value.textContent = Number(data.rating).toFixed(1);
        if (text) {
          text.textContent = data.source === 'google'
            ? `from ${data.total} Google reviews`
            : `from ${data.total} patient reviews on file`;
        }
        const stars = $$('[data-rating-stars] svg', box);
        const filled = Math.round(data.rating);
        stars.forEach((svg, i) => {
          const path = svg.querySelector('path');
          if (path) path.setAttribute('fill', i < filled ? 'currentColor' : 'none');
        });
      })
      .catch(() => box.remove());
  }

  /* ── boot ──────────────────────────────────────────────────────────────── */
  const boot = () => {
    reveal();
    header();
    activeNav();
    drawer();
    sheets();
    appBar();
    counters();
    parallax();
    faqs();
    lightbox();
    chips();
    enquiryForms();
    calculators();
    liveRating();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
