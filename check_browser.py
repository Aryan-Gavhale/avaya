"""Browser pass over the public site and admin panel. Needs the dev server running.

Drives Chromium at 1440x900 and 390x844, exercises every interactive piece,
records console errors and failed requests, checks for horizontal overflow,
broken images, clipped text, contrast and small tap targets, and writes
screenshots to _shots/.

    pip install playwright && playwright install chromium

    python check_browser.py            everything
    python check_browser.py desktop    one of desktop | mobile | motion | admin
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8120"
EMAIL = "owner@anvayadental.in"
PASSWORD = "anvaya2026"
SHOTS = Path("_shots")

problems: list[str] = []
passed = 0


def fail(where: str, what: str) -> None:
    problems.append(f"{where} — {what}")
    print(f"  FAIL {where}: {what}")


def note(what: str) -> None:
    global passed
    passed += 1
    print(f"  ok   {what}")


EXPECT_404 = {"/nope"}


def watch(page, label: str) -> None:
    def bad_status(r) -> None:
        path = r.url[len(BASE):].split("?")[0]
        if r.status >= 400 and BASE in r.url and path not in EXPECT_404:
            fail(label, f"HTTP {r.status} on {r.url[-90:]}")

    def console(m) -> None:
        if m.type != "error":
            return
        if "404" in m.text and any(p in page.url for p in EXPECT_404):
            return
        fail(label, f"console error: {m.text[:180]}")

    page.on("console", console)
    page.on("pageerror", lambda e: fail(label, f"page error: {str(e)[:180]}"))
    page.on("requestfailed", lambda r: fail(label, f"request failed: {r.url[-90:]}"))
    page.on("response", bad_status)


# ── page-level checks ───────────────────────────────────────────────────────
def overflow(page, label: str) -> None:
    wide = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    if wide > 1:
        culprits = page.evaluate("""() => {
            const w = window.innerWidth, out = [];
            for (const el of document.querySelectorAll('body *')) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && (r.right > w + 1))
                    out.push(el.tagName.toLowerCase()
                             + '.' + (el.className || '').toString().split(' ')[0]
                             + ' right=' + Math.round(r.right));
            }
            return [...new Set(out)].slice(0, 6);
        }""")
        fail(label, f"{wide}px wider than the viewport: {culprits}")


def broken_images(page, label: str) -> None:
    bad = page.evaluate("""() => [...document.images]
        .filter(i => i.complete && i.naturalWidth === 0
                     && i.getClientRects().length          // ignore offscreen scaffolding
                     && i.getAttribute('src'))
        .map(i => (i.className || i.tagName) + ' in '
                  + (i.closest('[data-sec]')?.dataset.sec || i.parentElement.className || '?')
                  + ' src=' + JSON.stringify(i.getAttribute('src').slice(-60)))""")
    if bad:
        fail(label, f"{len(bad)} image(s) failed to load: {bad[:5]}")

    empty = page.evaluate("""() => [...document.images]
        .filter(i => i.getClientRects().length && !i.getAttribute('src'))
        .map(i => (i.className || i.tagName) + ' in '
                  + (i.closest('[data-sec]')?.dataset.sec || '?'))""")
    if empty:
        fail(label, f"{len(empty)} rendered image(s) with no src: {empty[:5]}")


def missing_alt(page, label: str) -> None:
    bad = page.evaluate("""() => [...document.images]
        .filter(i => !i.hasAttribute('alt')).map(i => (i.src || '').slice(-60))""")
    if bad:
        fail(label, f"{len(bad)} image(s) with no alt attribute: {bad[:5]}")


def clipped_text(page, label: str) -> None:
    bad = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('h1,h2,h3,h4,p,li,td,th,button')) {
            if (el.children.length) continue;
            const s = getComputedStyle(el);
            if (s.overflow === 'hidden' && s.textOverflow !== 'ellipsis'
                && s.whiteSpace !== 'nowrap' && el.clientHeight > 0
                && el.scrollHeight > el.clientHeight + 4)
                out.push(el.tagName.toLowerCase() + ' "' + el.textContent.trim().slice(0, 45) + '"');
        }
        return [...new Set(out)].slice(0, 5);
    }""")
    if bad:
        fail(label, f"text taller than its clipped box: {bad}")


def small_targets(page, label: str) -> None:
    bad = page.evaluate("""() => {
        /* an absolutely positioned ::after pulled outside the box is the usual
           way to grow a small link's hit area, so count it in */
        const hit = (el) => {
            const r = el.getBoundingClientRect();
            let w = r.width, h = r.height;
            const p = getComputedStyle(el, '::after');
            if (p.content && p.content !== 'none' && p.position === 'absolute') {
                for (const [side, axis] of [['top', 'h'], ['bottom', 'h'],
                                            ['left', 'w'], ['right', 'w']]) {
                    const v = parseFloat(p[side]);
                    if (v < 0) { if (axis === 'h') h -= v; else w -= v; }
                }
            }
            return { w, h };
        };
        const out = [];
        for (const el of document.querySelectorAll('a,button,summary,input[type=checkbox],[role=button]')) {
            const r = el.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) continue;
            if (r.right < 0 || r.bottom < 0 || r.left > window.innerWidth) continue;  // offscreen
            if (getComputedStyle(el).visibility === 'hidden') continue;
            if (el.closest('p,li,figcaption,.rich,.foot__legal,.lede') && el.tagName !== 'A') continue;
            /* a checkbox inside its own label is hit through the label */
            const label = el.closest('label');
            if (label && label.getBoundingClientRect().height >= 34) continue;
            const box = hit(el);
            if (box.h < 34 || box.w < 26)
                out.push('"' + (el.textContent || el.getAttribute('aria-label') || el.tagName)
                         .trim().slice(0, 30) + '" ' + Math.round(box.w) + 'x' + Math.round(box.h));
        }
        return [...new Set(out)].slice(0, 8);
    }""")
    if bad:
        fail(label, f"tap targets under 34px: {bad}")


def contrast(page, label: str) -> None:
    """Rough WCAG AA check on text against its nearest painted background."""
    bad = page.evaluate("""() => {
        /* parse rgb()/rgba() and the color(srgb r g b / a) form that
           color-mix() computes to, returning 0-255 channels plus alpha */
        const parse = (c) => {
            if (!c) return null;
            const n = c.match(/-?[\\d.]+(e-?\\d+)?/g);
            if (!n) return null;
            const v = n.map(Number);
            if (c.startsWith('color(')) {
                const [r, g, b] = v.slice(0, 3).map(x => x * 255);
                return [r, g, b, v.length > 3 ? v[3] : 1];
            }
            return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1];
        };
        const over = (fg, bg) => {           // composite fg (with alpha) onto bg
            const a = fg[3];
            return [fg[0] * a + bg[0] * (1 - a),
                    fg[1] * a + bg[1] * (1 - a),
                    fg[2] * a + bg[2] * (1 - a), 1];
        };
        const lum = (c) => {
            const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92
                                                            : Math.pow((v + 0.055) / 1.055, 2.4); };
            return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
        };
        const bgOf = (el) => {
            const layers = [];
            for (let n = el; n; n = n.parentElement) {
                const s = getComputedStyle(n);
                if (s.backgroundImage !== 'none') return null;   // cannot sample a gradient
                const c = parse(s.backgroundColor);
                if (c && c[3] > 0.001) {
                    layers.push(c);
                    if (c[3] > 0.999) break;
                }
            }
            let base = [255, 255, 255, 1];
            for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
            return base;
        };
        const out = [];
        for (const el of document.querySelectorAll('p,li,span,td,h1,h2,h3,h4,a,button,strong,small')) {
            if (el.children.length || !el.textContent.trim()) continue;
            const s = getComputedStyle(el);
            if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity < 0.9) continue;
            if (!el.getClientRects().length) continue;
            const bg = bgOf(el);
            const fg = parse(s.color);
            if (!bg || !fg) continue;
            const a = lum(over(fg, bg)), b = lum(bg);
            const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
            const size = parseFloat(s.fontSize);
            const large = size >= 24 || (size >= 18.66 && +s.fontWeight >= 700);
            if (ratio < (large ? 3 : 4.5))
                out.push(ratio.toFixed(2) + ':1 ' + Math.round(size) + 'px '
                         + el.tagName.toLowerCase() + '.' + (el.className || '').toString().split(' ')[0]
                         + ' "' + el.textContent.trim().slice(0, 30) + '"');
        }
        return [...new Set(out)].slice(0, 10);
    }""")
    if bad:
        fail(label, f"text under the WCAG AA contrast ratio: {bad}")


def shoot(page, name: str, full: bool = False) -> None:
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)


def scroll_shots(page, name: str, steps: int = 24) -> None:
    height = page.evaluate("() => window.innerHeight")
    for i in range(steps):
        page.evaluate(f"() => window.scrollTo(0, {i} * {height} * 0.88)")
        page.wait_for_timeout(650)
        shoot(page, f"{name}-{i:02d}")
        if page.evaluate("() => window.scrollY + window.innerHeight "
                         ">= document.documentElement.scrollHeight - 4"):
            break
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    shoot(page, f"{name}-full", full=True)


# ── public site ─────────────────────────────────────────────────────────────
EXPECTED_SECTIONS = {"hero", "trust", "services", "about", "process", "gallery",
                     "doctors", "reviews", "emi", "branches", "faq", "enquiry"}


def public_pass(browser, label: str, width: int, height: int, mobile: bool) -> None:
    print(f"\n== public {label} {width}x{height} ==")
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              device_scale_factor=2 if mobile else 1,
                              is_mobile=mobile, has_touch=mobile)
    page = ctx.new_page()
    watch(page, f"{label} /")

    page.goto(BASE, wait_until="load")
    page.wait_for_timeout(1400)

    # measured before any full-page capture, which resizes the viewport and can
    # drop the touch emulation the touch-only styles depend on
    overflow(page, f"{label} /")
    broken_images(page, f"{label} /")
    missing_alt(page, f"{label} /")
    clipped_text(page, f"{label} /")
    contrast(page, f"{label} /")
    if mobile:
        small_targets(page, f"{label} /")

    scroll_shots(page, f"{label}-home")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(600)

    kinds = page.eval_on_selector_all("[data-sec]", "els => els.map(e => e.dataset.sec)")
    missing = EXPECTED_SECTIONS - set(kinds)
    if missing:
        fail(f"{label} /", f"expected section types not on the home page: {sorted(missing)}")
    else:
        note(f"{len(kinds)} sections rendered: {', '.join(kinds)}")

    thin = page.evaluate("""() => [...document.querySelectorAll('[data-sec]')]
        .filter(s => s.textContent.trim().length < 25).map(s => s.dataset.sec)""")
    if thin:
        fail(f"{label} /", f"sections with almost no content: {thin}")

    # header state on scroll
    page.evaluate("() => window.scrollTo(0, 700)")
    page.wait_for_timeout(700)
    if page.evaluate("() => document.querySelector('#head')?.classList.contains('is-stuck')"):
        note("header takes its scrolled state")
    else:
        fail(f"{label} /", "header did not gain .is-stuck after scrolling")
    bar = page.evaluate("() => document.querySelector('#scrollbar')?.style.width")
    if bar and bar != "0%":
        note(f"scroll progress bar tracks the page ({bar})")
    shoot(page, f"{label}-header-stuck")

    # counters
    counts = page.evaluate("""() => [...document.querySelectorAll('[data-count-to]')]
        .map(el => [el.dataset.countTo, el.textContent.trim()])""")
    if counts:
        stuck_at_zero = [c for c in counts if c[1] in ("", "0")]
        if stuck_at_zero:
            fail(f"{label} /", f"counters never reached their value: {counts}")
        else:
            note(f"{len(counts)} counter(s) animated to their value")

    # FAQ accordion
    faq = page.locator(".faq__q").first
    if faq.count():
        faq.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        faq.click()
        page.wait_for_timeout(700)
        expanded = faq.get_attribute("aria-expanded")
        tall = page.evaluate("""() => {
            const p = document.querySelector('.faq__a');
            return p ? p.getBoundingClientRect().height : 0; }""")
        shoot(page, f"{label}-faq-open")
        if expanded == "true" and tall > 10:
            note("FAQ answer opens")
        else:
            fail(f"{label} FAQ", f"aria-expanded={expanded}, answer height={tall}")
        faq.click()
        page.wait_for_timeout(700)
        if faq.get_attribute("aria-expanded") == "false":
            note("FAQ closes on a second click")
        else:
            fail(f"{label} FAQ", "a second click did not collapse the answer")
        # keyboard
        faq.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        if faq.get_attribute("aria-expanded") == "true":
            note("FAQ opens from the keyboard")
            page.keyboard.press("Enter")
        else:
            fail(f"{label} FAQ", "Enter did not open the answer")
    else:
        fail(f"{label} /", "no FAQ questions found")

    # EMI calculator
    amount = page.locator("[data-calc-amount]").first
    if amount.count():
        amount.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        emi_before = page.locator("[data-calc-emi]").first.inner_text()
        amount.click()
        amount.fill("")
        amount.type("120000", delay=25)
        page.wait_for_timeout(800)
        emi_after = page.locator("[data-calc-emi]").first.inner_text()
        tenures = page.locator(".tenure").count()
        shoot(page, f"{label}-emi")
        if "₹" in emi_after and emi_after != emi_before:
            note(f"EMI figure follows the amount ({emi_before} to {emi_after})")
        else:
            fail(f"{label} EMI", f"monthly figure stayed at {emi_after!r}")
        if tenures >= 2:
            note(f"{tenures} tenure options offered")
            second = page.locator(".tenure:not([disabled])").nth(1)
            if second.count():
                second.click()
                page.wait_for_timeout(700)
                if page.locator("[data-calc-emi]").first.inner_text() != emi_after:
                    note("changing the tenure changes the monthly figure")
                else:
                    fail(f"{label} EMI", "picking another tenure changed nothing")
        else:
            fail(f"{label} EMI", f"only {tenures} tenure option(s)")

        note_text = page.locator("[data-calc-note]").first.inner_text()
        if len(note_text) > 10:
            note(f"calculator explains the plan: {note_text[:60]!r}")

        # apply for EMI for real
        apply = page.locator("[data-calc-apply]").first
        if apply.count():
            if page.locator("[data-emi-form]").first.is_visible():
                fail(f"{label} EMI", "the apply form is open before it is asked for")
            if page.locator("[data-emi-done]").first.is_visible():
                fail(f"{label} EMI", "the EMI confirmation shows before anything is sent")
            else:
                note("EMI apply form and confirmation start hidden")
            apply.click()
            page.wait_for_timeout(800)
            form = page.locator("[data-emi-form]").first
            if form.count() and form.is_visible():
                page.fill("[data-emi-form] input[name=applicant_name]", "Playwright EMI")
                page.fill("[data-emi-form] input[name=phone]", "9876500088")
                page.wait_for_timeout(400)
                shoot(page, f"{label}-emi-apply")
                page.click("[data-emi-form] button[type=submit]")
                page.wait_for_timeout(1800)
                shoot(page, f"{label}-emi-sent")
                if page.locator("[data-emi-done]").first.is_visible():
                    ref = page.locator("[data-emi-ref]").first.inner_text()
                    note(f"EMI application submits from the page (ref {ref})")
                else:
                    msg = page.locator("[data-emi-msg]").first
                    fail(f"{label} EMI", "no confirmation after applying: "
                                         f"{msg.inner_text() if msg.count() else 'nothing shown'}")
            else:
                fail(f"{label} EMI", "the apply form did not open")
    else:
        fail(f"{label} /", "no EMI amount input found")

    # gallery lightbox
    tile = page.locator("[data-gallery] .mosaic__i").first
    if tile.count():
        tile.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        tile.click()
        page.wait_for_timeout(800)
        box = page.locator(".lightbox")
        shoot(page, f"{label}-lightbox")
        if box.count() and box.is_visible():
            note("gallery lightbox opens")
            counter = page.locator(".lightbox__count").inner_text()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(500)
            if page.locator(".lightbox__count").inner_text() != counter:
                note(f"arrow keys move through the gallery ({counter} to "
                     f"{page.locator('.lightbox__count').inner_text()})")
            else:
                fail(f"{label} gallery", "the right arrow did not advance the photograph")
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
            if not page.locator(".lightbox").is_visible():
                note("lightbox closes on Escape")
            else:
                fail(f"{label} gallery", "Escape did not close the lightbox")
        else:
            fail(f"{label} gallery", "clicking a photograph opened nothing")
    else:
        fail(f"{label} /", "no gallery tiles found")

    # the phone app shell: bottom tabs and the More sheet
    if mobile:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(400)

        tabs = page.locator(".tabbar__a")
        if tabs.count() >= 4 and tabs.first.is_visible():
            note(f"phone tab bar shows {tabs.count()} destinations")
        else:
            fail(f"{label} nav", f"the tab bar is not usable ({tabs.count()} items)")

        docked = page.evaluate("""() => {
            const bar = document.querySelector('.tabbar');
            if (!bar) return null;
            const r = bar.getBoundingClientRect();
            return { gap: Math.round(window.innerHeight - r.bottom),
                     h: Math.round(r.height) };
        }""")
        if docked and abs(docked["gap"]) <= 1 and 52 <= docked["h"] <= 76:
            note(f"the tab bar sits on the bottom edge ({docked['h']}px tall)")
        else:
            fail(f"{label} nav", f"the tab bar is not docked to the bottom: {docked}")

        # the old burger and sticky call bar must not double up with the tabs
        doubled = page.evaluate("""() => ['.burger', '.stickybar', '.drawer']
            .filter(s => { const el = document.querySelector(s);
                           return el && getComputedStyle(el).display !== 'none'; })""")
        if doubled:
            fail(f"{label} nav", f"desktop navigation still showing on a phone: {doubled}")
        else:
            note("the burger, drawer and call bar step aside for the tab bar")

        on = page.evaluate("""() => (document.querySelector('.tabbar__a.is-on') || {})
            .textContent?.trim()""")
        if on == "Home":
            note("the tab bar marks the screen you are on")
        else:
            fail(f"{label} nav", f"no tab marked current on the home page ({on!r})")

        # nothing important should hide behind the bar. The jump has to be instant
        # and repeated: landing at the foot starts the lazy images down there, and
        # each one that arrives makes the document taller than where we stopped
        for _ in range(5):
            page.evaluate("() => window.scrollTo({ top: 1e7, behavior: 'instant' })")
            page.wait_for_timeout(500)
            settled = page.evaluate("""() => { const d = document.documentElement;
                return window.scrollY >= d.scrollHeight - d.clientHeight - 1; }""")
            if settled:
                break
        under = page.evaluate("""() => {
            const bar = document.querySelector('.tabbar').getBoundingClientRect();
            return [...document.querySelectorAll('.foot a, .foot__note')]
                .filter(el => { const r = el.getBoundingClientRect();
                                return r.height && r.bottom > bar.top + 2; })
                .map(el => `"${el.textContent.trim().slice(0, 20)}" ends ${
                    Math.round(el.getBoundingClientRect().bottom - bar.top)}px into the bar`);
        }""")
        page.evaluate("() => window.scrollTo(0, 0)")
        if under:
            fail(f"{label} nav", f"footer element(s) sit under the tab bar: {under}")
        else:
            note("the page ends above the tab bar rather than behind it")

        more = page.locator("[data-sheet-open]").first
        more.click()
        page.wait_for_timeout(700)
        shoot(page, f"{label}-menu")
        sheet = page.locator("#more-sheet")
        if sheet.is_visible() and page.evaluate(
                "() => document.querySelector('#more-sheet').classList.contains('is-open')"):
            note("the More sheet slides up")
            risen = page.evaluate("""() => {
                const box = document.querySelector('.sheet__box').getBoundingClientRect();
                return Math.round(window.innerHeight - box.top);
            }""")
            if risen > 260:
                note(f"the sheet covers {risen}px of the screen")
            else:
                fail(f"{label} nav", f"the sheet only rose {risen}px")
            focused = page.evaluate(
                "() => (document.activeElement.className || '').toString()")
            if "sheet__" in focused or "appbtn" in focused:
                note("focus moves into the sheet")
            else:
                fail(f"{label} nav", f"focus stayed outside the sheet ({focused!r})")
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
            if not sheet.is_visible():
                note("the sheet closes on Escape")
            else:
                fail(f"{label} nav", "Escape did not close the sheet")
            more.click()
            page.wait_for_timeout(600)
            page.locator(".sheet__scrim").click(position={"x": 195, "y": 40})
            page.wait_for_timeout(600)
            if not sheet.is_visible():
                note("tapping above the sheet closes it too")
            else:
                fail(f"{label} nav", "the scrim did not close the sheet")
        else:
            fail(f"{label} nav", "the More sheet did not open")

        # the app bar gets out of the way going down and comes back going up
        page.evaluate("() => window.scrollTo(0, 900)")
        page.wait_for_timeout(700)
        away = page.evaluate("() => document.querySelector('#head').classList.contains('is-away')")
        page.evaluate("() => window.scrollTo(0, 500)")
        page.wait_for_timeout(700)
        back = not page.evaluate("() => document.querySelector('#head').classList.contains('is-away')")
        if away and back:
            note("the app bar hides on the way down and returns on the way up")
        else:
            fail(f"{label} nav", f"app bar hide-on-scroll misbehaved (away={away}, back={back})")
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        # card rails, rather than one long stack
        rails = page.evaluate("""() => [...document.querySelectorAll('.cards, .docs, .revs')]
            .filter(el => el.scrollWidth > el.clientWidth + 20).length""")
        if rails:
            note(f"{rails} card rail(s) scroll sideways instead of stacking")
        else:
            fail(f"{label} /", "no horizontal card rails on the phone layout")

    # enquiry form, submitted for real
    page.goto(BASE + "/contact", wait_until="load")
    page.wait_for_timeout(900)
    form = page.locator("[data-enquiry]").first
    if form.count():
        if page.locator("[data-enquiry-done]").first.is_visible():
            fail(f"{label} /contact", "the thank-you box shows before anything is sent")
        else:
            note("thank-you box stays hidden until the form is sent")
        page.fill("[data-enquiry] input[name=name]", "Playwright Visitor")
        page.fill("[data-enquiry] input[name=phone]", "9876500099")
        page.fill("[data-enquiry] input[name=email]", "visual@example.com")
        if page.locator("[data-enquiry] textarea[name=message]").count():
            page.fill("[data-enquiry] textarea[name=message]", "Sent by the visual check.")
        chip = page.locator("[data-chips] .chip").first
        if chip.count():
            chip.click()
            page.wait_for_timeout(300)
            if "is-on" in (chip.get_attribute("class") or ""):
                note("service chips select")
        page.wait_for_timeout(1800)          # clear the submit-timing gate
        shoot(page, f"{label}-enquiry")
        page.click("[data-enquiry] button[type=submit]")
        page.wait_for_timeout(2000)
        shoot(page, f"{label}-enquiry-sent")
        done = page.locator("[data-enquiry-done]").first
        if done.count() and done.is_visible():
            note(f"enquiry confirms in place (ref "
                 f"{page.locator('[data-done-ref]').first.inner_text()})")
        elif "/thank-you" in page.url:
            note("enquiry redirects to the thank-you page")
        else:
            msg = page.locator("[data-enquiry-msg]").first
            fail(f"{label} enquiry", "no confirmation: "
                                     f"{msg.inner_text() if msg.count() else page.url}")
    else:
        fail(f"{label} /contact", "no enquiry form found")

    # inner pages
    for path, name in (("/treatments", "treatments"), ("/about", "about"),
                       ("/emi-and-payment", "emi-page"), ("/contact", "contact"),
                       ("/treatments/dental-implants", "treatment"),
                       ("/nope", "404")):
        page.goto(BASE + path, wait_until="load")
        page.wait_for_timeout(900)
        shoot(page, f"{label}-{name}", full=True)
        if path != "/nope":
            overflow(page, f"{label} {path}")
            broken_images(page, f"{label} {path}")
            clipped_text(page, f"{label} {path}")
            if not page.locator("h1").count():
                fail(f"{label} {path}", "no h1 on the page")
    note("inner pages and the 404 page render")

    # keyboard
    page.goto(BASE, wait_until="load")
    page.wait_for_timeout(900)
    page.keyboard.press("Tab")
    first = page.evaluate(
        "() => (document.activeElement.textContent || '').trim().slice(0, 40)")
    if "skip" in first.lower():
        note(f"first tab stop is the skip link ({first!r})")
    else:
        fail(f"{label} keyboard", f"first tab stop is {first!r}, expected a skip link")
    if page.evaluate("""() => { const s = getComputedStyle(document.activeElement);
                              return s.outlineStyle !== 'none' || s.boxShadow !== 'none'; }"""):
        note("focus ring is visible")
    else:
        fail(f"{label} keyboard", "no visible focus ring")

    landmarks = page.evaluate("""() => ({
        main: !!document.querySelector('main'),
        nav: !!document.querySelector('nav'),
        h1: document.querySelectorAll('h1').length,
        lang: document.documentElement.lang })""")
    if landmarks["main"] and landmarks["nav"] and landmarks["h1"] == 1 and landmarks["lang"]:
        note(f"landmarks fine: one h1, main, nav, lang={landmarks['lang']}")
    else:
        fail(f"{label} /", f"landmark problem: {landmarks}")

    ctx.close()


def motion_pass(browser) -> None:
    print("\n== reduced motion 1440x900 ==")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              reduced_motion="reduce")
    page = ctx.new_page()
    watch(page, "reduced motion")
    page.goto(BASE, wait_until="load")
    page.wait_for_timeout(1400)
    shoot(page, "motion-home")

    hidden = page.evaluate("""() => [...document.querySelectorAll('.rv')]
        .filter(el => !el.classList.contains('is-in')).length""")
    invisible = page.evaluate("""() => [...document.querySelectorAll('.rv')]
        .filter(el => parseFloat(getComputedStyle(el).opacity) < 0.99).length""")
    if hidden or invisible:
        fail("reduced motion",
             f"{hidden} reveal element(s) never marked in, {invisible} still transparent")
    else:
        note("all reveal content is shown immediately with reduced motion on")

    counts = page.evaluate("""() => [...document.querySelectorAll('[data-count-to]')]
        .map(el => el.textContent.trim())""")
    if counts and all(c not in ("", "0") for c in counts):
        note(f"counters jump straight to their value: {counts[:4]}")
    elif counts:
        fail("reduced motion", f"counters left blank or at zero: {counts}")

    moving = page.evaluate("""() => [...document.querySelectorAll('.sect *')]
        .filter(el => { const s = getComputedStyle(el);
                        return (parseFloat(s.animationDuration) || 0) > 0.05
                               && s.animationIterationCount === 'infinite'; }).length""")
    if moving:
        fail("reduced motion", f"{moving} element(s) still animate forever")
    else:
        note("nothing animates indefinitely")

    parallaxed = page.evaluate("""() => [...document.querySelectorAll('[data-parallax]')]
        .filter(el => el.style.transform && el.style.transform !== 'none').length""")
    if parallaxed:
        fail("reduced motion", f"{parallaxed} parallax element(s) still transformed")
    else:
        note("parallax is off")

    ctx.close()


# ── admin ───────────────────────────────────────────────────────────────────
ADMIN_SCREENS = [
    ("/admin/", "dashboard"), ("/admin/pages", "pages"),
    ("/admin/pages/1", "page-builder"), ("/admin/sections/1", "section-editor"),
    ("/admin/services", "services"), ("/admin/services/1", "service-form"),
    ("/admin/service_categories", "categories"),
    ("/admin/doctors", "doctors"), ("/admin/branches", "branches"),
    ("/admin/faqs", "faqs"), ("/admin/nav_items", "navigation"),
    ("/admin/testimonials", "testimonials"), ("/admin/galleries", "galleries"),
    ("/admin/galleries/1/items", "gallery-items"),
    ("/admin/media", "media"), ("/admin/reviews", "reviews"),
    ("/admin/enquiries", "enquiries"), ("/admin/enquiries/1", "enquiry-detail"),
    ("/admin/emi_plans", "emi-plans"), ("/admin/emi/applications", "emi-apps"),
    ("/admin/emi/applications/1", "emi-app-detail"),
    ("/admin/emi/ledger", "ledger"), ("/admin/settings", "settings"),
    ("/admin/settings/theme", "settings-theme"),
    ("/admin/settings/hours", "settings-hours"),
    ("/admin/users", "users"), ("/admin/account", "account"),
    ("/admin/activity", "activity"), ("/admin/backup", "backup"),
]


def admin_phone_pass(page, label: str) -> None:
    """The admin panel as an app: tabs, a sheet, cards instead of tables.

    Everything the front desk does from a phone has to work here, so this walks
    the same route a receptionist would: open a list, filter it, open a record,
    reorder something, save a form.
    """
    page.goto(BASE + "/admin/", wait_until="load")
    page.wait_for_timeout(700)

    hidden = page.evaluate("""() => ['#side', '#burger2']
        .filter(s => { const el = document.querySelector(s);
                       return el && getComputedStyle(el).display !== 'none'; })""")
    if hidden:
        fail(f"admin {label}", f"the desktop sidebar is still on screen: {hidden}")
    else:
        note("the dark sidebar and its burger give way to the tab bar")

    tabs = page.locator(".atabs__a")
    docked = page.evaluate("""() => {
        const bar = document.querySelector('.atabs');
        if (!bar) return null;
        const r = bar.getBoundingClientRect();
        return { gap: Math.round(window.innerHeight - r.bottom), h: Math.round(r.height) };
    }""")
    if tabs.count() >= 4 and docked and abs(docked["gap"]) <= 1:
        note(f"admin tab bar docked with {tabs.count()} destinations ({docked['h']}px)")
    else:
        fail(f"admin {label}", f"admin tab bar not usable: {tabs.count()} items, {docked}")

    badge = page.locator(".atabs__n")
    if badge.count() and badge.first.is_visible():
        note(f"the enquiries tab carries a count of {badge.first.inner_text()}")

    more = page.locator("[data-asheet-open]").first
    more.click()
    page.wait_for_timeout(700)
    shoot(page, f"admin-{label}-sheet")
    sheet = page.locator("#more-sheet")
    if sheet.is_visible():
        links = page.locator("#more-sheet .asheet__a").count()
        note(f"the More sheet lists {links} sections plus account and sign-out")
        if not page.locator("#more-sheet form[action*='logout'] button").count():
            fail(f"admin {label}", "no way to sign out from the phone sheet")
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        if sheet.is_visible():
            fail(f"admin {label}", "Escape did not close the admin sheet")
        else:
            note("the admin sheet closes on Escape")
    else:
        fail(f"admin {label}", "the admin More sheet did not open")

    # tables must have become cards, and nothing may scroll sideways
    for path, expect_cards in (("/admin/enquiries", True), ("/admin/services", True),
                               ("/admin/emi/applications", True)):
        page.goto(BASE + path, wait_until="load")
        page.wait_for_timeout(800)
        shoot(page, f"admin-{label}-cards-{path.strip('/').replace('/', '-')}", full=True)
        state = page.evaluate("""() => {
            const t = document.querySelector('table.t');
            if (!t) return null;
            const row = t.querySelector('tbody tr');
            return {
                table: getComputedStyle(t).display,
                row: row ? getComputedStyle(row).display : null,
                labelled: !!t.querySelector('td[data-label]'),
                sideways: t.parentElement.scrollWidth > t.parentElement.clientWidth + 4,
            };
        }""")
        if not state:
            fail(f"admin {label}", f"no list table on {path}")
        elif expect_cards and (state["table"] != "block" or state["row"] != "block"):
            fail(f"admin {label}", f"{path} still renders as a table: {state}")
        elif state["sideways"]:
            fail(f"admin {label}", f"{path} scrolls sideways on a phone")
        else:
            note(f"{path} reads as cards, no sideways scrolling")
        overflow(page, f"admin {label} {path}")

    # the primary action floats where a thumb can reach it
    fab = page.locator("[data-fab]").first
    if fab.count():
        box = page.evaluate("""() => {
            const el = document.querySelector('[data-fab]');
            const r = el.getBoundingClientRect();
            const tabs = document.querySelector('.atabs').getBoundingClientRect();
            return { fixed: getComputedStyle(el).position, clear: Math.round(tabs.top - r.bottom),
                     right: Math.round(window.innerWidth - r.right) };
        }""")
        if box["fixed"] == "fixed" and box["clear"] >= 0 and box["right"] < 30:
            note(f"the new-record button floats {box['clear']}px above the tabs")
        else:
            fail(f"admin {label}", f"the floating action button is misplaced: {box}")
    else:
        fail(f"admin {label}", "no floating action button on a list screen")

    # reordering without a mouse
    page.goto(BASE + "/admin/faqs", wait_until="load")
    page.wait_for_timeout(800)
    first = page.evaluate("() => document.querySelector('tbody tr .rowlink')?.textContent.trim()")
    down = page.locator("[data-move=down]").first
    if down.count() and down.is_visible():
        down.click()
        page.wait_for_timeout(1200)
        moved = page.evaluate("() => document.querySelector('tbody tr .rowlink')?.textContent.trim()")
        shoot(page, f"admin-{label}-reorder")
        if moved and moved != first:
            note("the move buttons reorder a list from a touch screen")
            page.locator("[data-move=up]").nth(1).click()   # put it back
            page.wait_for_timeout(1000)
        else:
            fail(f"admin {label}", "tapping move-down changed nothing")
    else:
        fail(f"admin {label}", "no move buttons on a sortable list")

    # a form: docked save bar, fields wide enough to type into
    page.goto(BASE + "/admin/services/1", wait_until="load")
    page.wait_for_timeout(800)
    form = page.evaluate("""() => {
        const bar = document.querySelector('.savebar');
        const tabs = document.querySelector('.atabs').getBoundingClientRect();
        const input = document.querySelector('.fi .in');
        if (!bar || !input) return null;
        const r = bar.getBoundingClientRect();
        const i = input.getBoundingClientRect();
        return { fixed: getComputedStyle(bar).position,
                 clear: Math.round(tabs.top - r.bottom),
                 wide: Math.round(i.width), tall: Math.round(i.height),
                 size: parseFloat(getComputedStyle(input).fontSize) };
    }""")
    shoot(page, f"admin-{label}-form", full=True)
    if not form:
        fail(f"admin {label}", "no save bar or fields on the treatment form")
    else:
        if form["fixed"] == "fixed" and abs(form["clear"]) <= 1:
            note("the save bar docks straight above the tab bar")
        else:
            fail(f"admin {label}", f"the save bar is not docked: {form}")
        if form["wide"] > 280 and form["tall"] >= 44 and form["size"] >= 16:
            note(f"fields are {form['wide']}x{form['tall']} at {form['size']:.0f}px, "
                 "so iOS will not zoom on focus")
        else:
            fail(f"admin {label}", f"fields are too small to type into: {form}")

    # and it still saves
    page.fill("input[name=name]", "Dental implants")
    page.click(".savebar button[type=submit]")
    page.wait_for_timeout(1200)
    if page.locator(".flash").count():
        note("saving from the docked bar works and reports back")
    else:
        fail(f"admin {label}", "saving from the phone save bar produced no confirmation")

    toast = page.evaluate("""() => {
        const f = document.querySelector('.flash');
        const tabs = document.querySelector('.atabs');
        if (!f || !tabs) return null;
        return Math.round(tabs.getBoundingClientRect().top - f.getBoundingClientRect().bottom);
    }""")
    if toast is not None and toast >= 0:
        note(f"toasts rise {toast}px clear of the tab bar")
    elif toast is not None:
        fail(f"admin {label}", f"the toast overlaps the tab bar by {-toast}px")

    small_targets(page, f"admin {label} form")

    for path in ("/admin/enquiries/1", "/admin/emi/applications/1", "/admin/pages/1",
                 "/admin/media", "/admin/settings"):
        page.goto(BASE + path, wait_until="load")
        page.wait_for_timeout(700)
        overflow(page, f"admin {label} {path}")
        clipped_text(page, f"admin {label} {path}")
        shoot(page, f"admin-{label}-{path.strip('/').replace('/', '-')}", full=True)
    note("the phone admin walks through every screen without overflowing")


def admin_pass(browser, label: str, width: int, height: int) -> None:
    print(f"\n== admin {label} {width}x{height} ==")
    mobile = width < 700
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              is_mobile=mobile, has_touch=mobile)
    page = ctx.new_page()
    watch(page, f"admin {label}")

    page.goto(BASE + "/admin/login", wait_until="load")
    page.wait_for_timeout(600)
    shoot(page, f"admin-{label}-login")
    page.fill("input[name=email]", EMAIL)
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_timeout(1400)
    if "/admin/login" in page.url:
        fail(f"admin {label}", "sign-in did not go through")
        ctx.close()
        return
    note("admin sign-in works")

    for path, name in ADMIN_SCREENS:
        page.goto(BASE + path, wait_until="load")
        page.wait_for_timeout(650)
        shoot(page, f"admin-{label}-{name}", full=True)
        overflow(page, f"admin {label} {path}")
        broken_images(page, f"admin {label} {path}")
        clipped_text(page, f"admin {label} {path}")
    note(f"{len(ADMIN_SCREENS)} admin screens render")

    if mobile:
        admin_phone_pass(page, label)
        ctx.close()
        return

    # ── desktop-only interaction checks ─────────────────────────────────────
    # media picker
    page.goto(BASE + "/admin/sections/1", wait_until="load")
    page.wait_for_timeout(900)
    pick = page.locator("[data-pick] [data-pick-open]").first
    if pick.count():
        pick.click()
        page.wait_for_timeout(1600)
        shoot(page, f"admin-{label}-picker")
        picker = page.locator("#picker")
        if picker.is_visible():
            note("media picker opens from a section field")
            tiles = page.locator("#picker-body .pitem").count()
            if tiles:
                note(f"picker lists {tiles} image(s)")
            else:
                fail(f"admin {label}", "the picker opened but listed no images")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            if not picker.is_visible():
                note("media picker closes on Escape")
            else:
                fail(f"admin {label}", "Escape did not close the picker")
        else:
            fail(f"admin {label}", "the media picker did not open")
    else:
        fail(f"admin {label}", "no media picker button on the section editor")

    # dirty-form guard, on its own page: dismissing a beforeunload prompt leaves
    # the tab wedged for later navigations, so the page is thrown away after
    guard = ctx.new_page()
    guard.goto(BASE + "/admin/services/1", wait_until="load")
    guard.wait_for_timeout(800)
    guard.fill("input[name=name]", "Changed but not saved")
    guard.wait_for_timeout(400)
    seen: list[str] = []
    guard.on("dialog", lambda d: (seen.append(d.message), d.dismiss()))
    guard.locator(".side a").first.click()
    guard.wait_for_timeout(1200)
    if seen:
        note("leaving a dirty form asks first")
    else:
        fail(f"admin {label}", "no warning when navigating away from unsaved edits")
    guard.close(run_before_unload=False)

    # inline publish toggle
    page.goto(BASE + "/admin/services", wait_until="load")
    page.wait_for_timeout(800)
    sw = page.locator("input[data-toggle-url]").first
    knob = page.locator("label.sw").first          # the input itself is hidden
    if sw.count() and knob.count():
        was = sw.is_checked()
        knob.click()
        page.wait_for_timeout(1200)
        shoot(page, f"admin-{label}-toggle")
        if sw.is_checked() != was:
            note("inline publish toggle flips without a reload")
            page.reload(wait_until="load")
            page.wait_for_timeout(700)
            if page.locator("input[data-toggle-url]").first.is_checked() != was:
                note("the toggle survived a reload, so it was saved")
            else:
                fail(f"admin {label}", "the toggle looked flipped but was not saved")
            knob.click()
            page.wait_for_timeout(1000)
        else:
            fail(f"admin {label}", "the publish toggle did not change")
    else:
        fail(f"admin {label}", "no publish toggle on the services table")

    # slug helper
    page.goto(BASE + "/admin/services/new", wait_until="load")
    page.wait_for_timeout(700)
    page.fill("input[name=name]", "Painless Root Canal")
    page.wait_for_timeout(700)
    slug = page.input_value("input[name=slug]")
    if slug == "painless-root-canal":
        note("slug fills itself from the name")
    else:
        fail(f"admin {label}", f"slug helper produced {slug!r}")

    # search and filter
    page.goto(BASE + "/admin/enquiries", wait_until="load")
    page.wait_for_timeout(800)
    rows_all = page.locator("tbody tr").count()
    tab = page.locator(".tab", has_text="New").first
    if tab.count():
        tab.click()
        page.wait_for_timeout(1200)
        rows_new = page.locator("tbody tr").count()
        shoot(page, f"admin-{label}-filter-tab")
        if rows_new <= rows_all and "status=new" in page.url:
            note(f"the status tab narrows the table ({rows_all} to {rows_new})")
        else:
            fail(f"admin {label}", f"status tab landed on {page.url} with {rows_new} rows")
    else:
        fail(f"admin {label}", "no status tabs on enquiries")

    # filters live in a popover: closed by default, applied with one button
    page.goto(BASE + "/admin/enquiries", wait_until="load")
    page.wait_for_timeout(700)
    pop = page.locator("details[data-pop]:not([data-colpick]) > summary").first
    if pop.count() and not page.locator("select[name=range]").first.is_visible():
        note("filters are folded into one button, not spread across the top")
        pop.click()
        page.wait_for_timeout(500)
        shoot(page, f"admin-{label}-filters-open")
        page.locator(".top__crumb").click()
        page.wait_for_timeout(400)
        if page.locator("select[name=range]").first.is_visible():
            fail(f"admin {label}", "the filter popover did not close on an outside click")
        else:
            note("the filter popover closes on an outside click")
        pop.click()
        page.wait_for_timeout(400)
        page.select_option("select[name=range]", "today")
        page.click(".pop__foot button[type=submit]")
        page.wait_for_timeout(1200)
        shoot(page, f"admin-{label}-filter")
        chips = page.locator(".chips .chip").count()
        if "range=today" in page.url and chips:
            note(f"the date filter applies and shows as a removable chip "
                 f"({page.locator('tbody tr').count()} row(s) today)")
            page.locator(".chips .chip a").first.click()
            page.wait_for_timeout(1000)
            if "range=" not in page.url:
                note("removing the chip clears that filter")
            else:
                fail(f"admin {label}", f"the chip did not clear its filter, url is {page.url}")
        else:
            fail(f"admin {label}", f"the date filter did not apply ({page.url}, {chips} chip(s))")
    else:
        fail(f"admin {label}", "no folded filter popover on enquiries")

    page.keyboard.press("/")
    page.wait_for_timeout(200)
    if page.evaluate("() => document.activeElement?.matches('[data-slash]')"):
        note("/ jumps to the search box")
    else:
        fail(f"admin {label}", "/ did not focus the search box")
    page.keyboard.press("Escape")

    # column chooser: hide a column, survive a reload, put it back
    page.goto(BASE + "/admin/enquiries", wait_until="load")
    page.wait_for_timeout(700)
    cols = page.locator("details[data-colpick] > summary").first
    if cols.count() and cols.is_visible():
        cols.click()
        page.wait_for_timeout(400)
        locked = page.locator("[data-colpick-list] input:disabled").count()
        box = page.locator("[data-colpick-list] label", has_text="Treatment").locator("input")
        box.uncheck()
        page.wait_for_timeout(300)
        shoot(page, f"admin-{label}-columns")
        page.reload(wait_until="load")
        page.wait_for_timeout(700)
        gone = page.evaluate("""() => {
            const th = document.querySelector('th[data-col=treatment]');
            const td = document.querySelector('tbody tr td:nth-child(3)');
            return th && getComputedStyle(th).display === 'none' && (!td || getComputedStyle(td).display === 'none');
        }""")
        if gone and locked:
            note(f"a hidden column stays hidden after a reload ({locked} column(s) locked on)")
        else:
            fail(f"admin {label}", f"column chooser: hidden={gone}, locked={locked}")
        cols.click()
        page.wait_for_timeout(300)
        page.click("[data-colpick-reset]")
        page.wait_for_timeout(300)
        if page.locator("th[data-col=treatment]").is_visible():
            note("reset brings every column back")
        else:
            fail(f"admin {label}", "column reset did not restore the column")
        page.keyboard.press("Escape")
    else:
        fail(f"admin {label}", "no column chooser on enquiries")

    # the new-application wizard: Continue is gated, steps go in order
    page.goto(BASE + "/admin/emi/applications/new", wait_until="load")
    page.wait_for_timeout(700)
    on = lambda: page.evaluate("() => [...document.querySelectorAll('[data-wiz-pane]')].findIndex(p => p.classList.contains('is-on'))")
    page.click("[data-wiz-next]")
    page.wait_for_timeout(300)
    why = page.inner_text("[data-wiz-why]")
    if on() == 0 and why:
        note(f"the wizard will not move on with gaps ({why!r})")
    else:
        fail(f"admin {label}", f"Continue on an empty first step moved to step {on()}")
    page.fill("#applicant_name", "Playwright Wizard")
    page.fill("#phone", "98765 43210")
    page.click("[data-wiz-next]")
    page.wait_for_timeout(400)
    page.fill("#treatment_amount", "90000")
    page.click("[data-wiz-next]")
    page.wait_for_timeout(500)
    shoot(page, f"admin-{label}-wizard-plans")
    monthly = page.locator(".plancard:not(.is-off) [data-plan-q]").first.inner_text()
    page.locator(".plancard:not(.is-off)").first.click()
    page.click("[data-wiz-next]")
    page.wait_for_timeout(500)
    shoot(page, f"admin-{label}-wizard-review", full=True)
    review = page.inner_text(".review")
    if on() == 3 and "Playwright Wizard" in review and "₹" in monthly:
        note(f"plan cards price themselves ({monthly.strip()}) and the review reads back every answer")
        page.click("[data-wiz-submit]")
        page.wait_for_timeout(1400)
        if "/emi/applications/" in page.url and "/new" not in page.url:
            note("the wizard files the application and lands on it")
        else:
            fail(f"admin {label}", f"filing from the wizard landed on {page.url}")
    else:
        fail(f"admin {label}", f"wizard review: step {on()}, monthly {monthly!r}")

    # the record page: one next action, tabs, a guided payment dialog
    page.goto(BASE + "/admin/emi/applications/1#record", wait_until="load")
    page.wait_for_timeout(900)
    shoot(page, f"admin-{label}-emi-pay-dialog")
    if page.locator("#pay-dlg[open]").count():
        note("#record from the ledger opens the payment dialog")
        page.click("#pay-dlg [data-wiz-next]")
        page.wait_for_timeout(300)
        page.click("#pay-dlg [data-wiz-next]")
        page.wait_for_timeout(400)
        shoot(page, f"admin-{label}-emi-pay-confirm")
        amt = page.inner_text("#pay-dlg [data-rv=amount]")
        if "₹" in amt and page.locator("#pay-dlg [data-wiz-submit]").is_visible():
            note(f"the payment dialog walks to a confirm step ({amt})")
        else:
            fail(f"admin {label}", f"payment dialog confirm step shows {amt!r}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    else:
        fail(f"admin {label}", "the payment dialog did not open from #record")
    page.goto(BASE + "/admin/emi/applications/1", wait_until="load")
    page.wait_for_timeout(700)
    page.click("[data-dtab=payments]")
    page.wait_for_timeout(300)
    if "#payments" in page.url and page.locator("#pane-payments").is_visible() \
            and not page.locator("#pane-overview").is_visible():
        note("record tabs switch in place and keep their place in the URL")
    else:
        fail(f"admin {label}", "record tabs did not switch panes")
    shoot(page, f"admin-{label}-emi-detail", full=True)

    # bulk selection
    page.goto(BASE + "/admin/enquiries", wait_until="load")
    page.wait_for_timeout(800)
    head_box = page.locator("thead input[type=checkbox]").first
    if head_box.count():
        head_box.click()
        page.wait_for_timeout(600)
        picked = page.locator("tbody input[type=checkbox]:checked").count()
        shoot(page, f"admin-{label}-bulk")
        if picked:
            note(f"select-all ticks {picked} row(s) and reveals the bulk bar")
        else:
            fail(f"admin {label}", "select-all ticked nothing")
    else:
        fail(f"admin {label}", "no select-all checkbox")

    # theme colour writes through to the public page
    page.goto(BASE + "/admin/settings/theme", wait_until="load")
    page.wait_for_timeout(800)
    field = page.locator("input[name='theme.primary']").first
    if field.count():
        original = page.input_value("input[name='theme.primary']")
        page.fill("input[name='theme.primary']", "#7A1F3D")
        page.click("form[action*='/settings/'] button[type=submit]")
        page.wait_for_timeout(1200)
        page.goto(BASE, wait_until="load")
        page.wait_for_timeout(800)
        applied = page.evaluate("""() => getComputedStyle(document.documentElement)
            .getPropertyValue('--primary').trim()""")
        shoot(page, f"admin-{label}-theme-applied")
        if applied.lower().startswith("#7a1f3d"):
            note("a theme colour saved in admin reaches the public page")
        else:
            fail(f"admin {label}", f"--primary on the site is {applied!r} after saving #7A1F3D")
        page.goto(BASE + "/admin/settings/theme", wait_until="load")
        page.wait_for_timeout(700)
        page.fill("input[name='theme.primary']", original)
        page.click("form[action*='/settings/'] button[type=submit]")
        page.wait_for_timeout(900)
        note("theme colour put back")
    else:
        fail(f"admin {label}", "no primary colour field in theme settings")

    # receipt print view
    page.goto(BASE + "/admin/emi/applications/1", wait_until="load")
    page.wait_for_timeout(800)
    receipt = page.locator("a[href*='/emi/receipt/']").first
    if receipt.count():
        page.goto(BASE + (receipt.get_attribute("href") or ""), wait_until="load")
        page.wait_for_timeout(700)
        shoot(page, f"admin-{label}-receipt", full=True)
        page.emulate_media(media="print")
        page.wait_for_timeout(400)
        shoot(page, f"admin-{label}-receipt-print", full=True)
        chrome = page.evaluate("""() => {
            const s = document.querySelector('.side');
            return s ? getComputedStyle(s).display : 'none'; }""")
        page.emulate_media(media="screen")
        if chrome == "none":
            note("receipt hides the admin chrome when printed")
        else:
            fail(f"admin {label}", f"sidebar still shows in print (display:{chrome})")
    else:
        fail(f"admin {label}", "no receipt link on the seeded application")

    # log out
    page.goto(BASE + "/admin/", wait_until="load")
    page.wait_for_timeout(600)
    out = page.locator("form[action*='logout'] button, a[href*='logout']").first
    if out.count():
        out.click()
        page.wait_for_timeout(1000)
        page.goto(BASE + "/admin/enquiries", wait_until="load")
        page.wait_for_timeout(700)
        if "/admin/login" in page.url:
            note("logging out closes the session")
        else:
            fail(f"admin {label}", f"still signed in after logout, landed on {page.url}")
    else:
        fail(f"admin {label}", "no sign-out control")

    ctx.close()


def purge() -> None:
    """Drop the rows earlier runs submitted.

    Each pass sends an enquiry and an EMI application, and the public forms refuse
    a connection that has sent twenty in an hour — so without this, a few runs in a
    row start failing on the throttle rather than on anything real.
    """
    import sqlite3

    conn = sqlite3.connect("db/clinic.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        DELETE FROM emi_applications WHERE applicant_name LIKE 'Playwright %';
        DELETE FROM enquiries        WHERE name LIKE 'Playwright %';
        DELETE FROM login_attempts   WHERE email LIKE '%anvayadental.in';
    """)
    conn.commit()
    conn.close()


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if SHOTS.exists():
        shutil.rmtree(SHOTS)
    SHOTS.mkdir()
    purge()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        if which in ("all", "desktop"):
            public_pass(browser, "desktop", 1440, 900, False)
        if which in ("all", "mobile"):
            public_pass(browser, "mobile", 390, 844, True)
        if which in ("all", "motion"):
            motion_pass(browser)
        if which in ("all", "admin"):
            admin_pass(browser, "desktop", 1440, 900)
            admin_pass(browser, "mobile", 390, 844)
        browser.close()

    print(f"\n=== {len(problems)} problem(s), {passed} check(s) passed ===")
    for line in problems:
        print(" - " + line)
    print(f"\nscreenshots: {SHOTS.resolve()}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
