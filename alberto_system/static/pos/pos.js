/* ==========================================================================
   Alberto Grocers - POS TERMINAL
   Vanilla JS, no framework. Config + bootstrap data arrive as JSON in
   #pos-boot. Everything else is rendered client-side.
   ========================================================================== */
(function () {
    'use strict';

    // ---------------------------------------------------------------- CONFIG
    var bootEl = document.getElementById('pos-boot');
    var CFG = JSON.parse(bootEl.textContent);
    var PRODUCTS = CFG.products || [];
    var CUSTOMERS = CFG.customers || [];
    var TAX_RATE = parseFloat(CFG.tax_rate != null ? CFG.tax_rate : '15');
    var PAGE_SIZE = parseInt(CFG.page_size || '24', 10);

    var URLS = CFG.urls || {};

    // ------------------------------------------------------------------ STATE
    var cart = [];          // {id, name, sku, price, original_price, qty, max_stock, comment, category__name}
    var selected = -1;      // index into cart
    var customer = null;    // {id, name, customer_id}
    // Tile density: compact / comfortable / large. Remembered per browser.
    var view = 'comfortable';
    try {
        var savedDensity = localStorage.getItem('posDensity');
        if (['compact', 'comfortable', 'large'].indexOf(savedDensity) >= 0) view = savedDensity;
    } catch (e) {}
    var page = 1;
    var filterCat = '__all__';
    var query = '';
    var heldCount = parseInt(CFG.held_count || '0', 10);
    var drawerOpen = !!CFG.drawer_open;
    var locked = false;
    var paying = false;
    // Product id of a line that was just added, so renderCart() can play the
    // fade-in-up highlight exactly once. Null = nothing to flash.
    var flashLineId = null;
    // Armed quantity multiplier (F4). 1 = normal, one at a time. Anything
    // higher applies to the NEXT item added and is then spent, so a stray
    // armed 4 can never silently quadruple a later product.
    var armedQty = 1;

    var CURRENCY = '₱';

    // ------------------------------------------------------------------- UTIL
    function $(id) { return document.getElementById(id); }
    function el(tag, cls, txt) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (txt != null) n.textContent = txt;
        return n;
    }
    function money(n) {
        var v = parseFloat(n || 0);
        return CURRENCY + v.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function moneyShort(n) {
        var v = parseFloat(n || 0);
        return CURRENCY + v.toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }
    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function getCookie(name) {
        var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? decodeURIComponent(m[2]) : '';
    }

    /**
     * VAT is INCLUSIVE in Philippine retail: shelf prices already contain it,
     * so the terminal extracts tax out of the total. Mirrors split_vat() on
     * the server, which is the authority for what actually gets stored.
     *
     * Voided lines are EXCLUDED. A line the cashier has struck through must
     * never still be charged for - a POS that shows a voided line in the
     * total is a real till discrepancy, not a cosmetic bug. There is no
     * server-side void field, so the exclusion happens here and the voided
     * line is simply not sent at checkout.
     */
    function totals() {
        var gross = 0, discount = 0;
        for (var i = 0; i < cart.length; i++) {
            var it = cart[i];
            if (it.voided) continue;
            gross += it.price * it.qty;
            if (it.original_price > it.price) discount += (it.original_price - it.price) * it.qty;
        }
        gross = round2(gross);
        var net = round2(gross / (1 + TAX_RATE / 100));
        return { gross: gross, subtotal: net, tax: round2(gross - net), discount: round2(discount) };
    }

    /** Lines that are actually being sold - what the totals describe. */
    function payableLines() {
        return cart.filter(function (l) { return !l.voided; });
    }
    function round2(n) { return Math.round((n + Number.EPSILON) * 100) / 100; }

    // ---------------------------------------------------------------- TOASTS
    function toast(msg, kind) {
        kind = kind || '';
        var host = $('posToasts');
        var t = el('div', 'pos-toast ' + kind);
        var icon = kind === 'ok' ? 'fa-circle-check'
            : kind === 'err' ? 'fa-circle-exclamation'
            : kind === 'warn' ? 'fa-triangle-exclamation' : 'fa-circle-info';
        t.innerHTML = '<i class="fa-solid ' + icon + '"></i><span>' + esc(msg) + '</span>';
        host.appendChild(t);
        setTimeout(function () {
            t.classList.add('out');
            setTimeout(function () { t.remove(); }, 200);
        }, 2600);
    }

    // ----------------------------------------------------------------- MODALS
    var modalStack = [];
    function openModal(id) {
        var m = $(id);
        m.classList.add('open');
        modalStack.push(id);
        var focusable = m.querySelector('input:not([type=hidden]), textarea, .btn-success, .btn-primary');
        if (focusable) setTimeout(function () { focusable.focus(); }, 60);
    }
    function closeModal(id) {
        $(id).classList.remove('open');
        modalStack = modalStack.filter(function (x) { return x !== id; });
    }
    function closeTopModal() {
        if (!modalStack.length) return false;
        closeModal(modalStack[modalStack.length - 1]);
        return true;
    }
    function anyModalOpen() { return modalStack.length > 0; }

    // ------------------------------------------------------------- NAV DRAWER
    // Navigation lives in the app sidebar (base.html), opened with the burger
    // in the topbar. The terminal only needs to know if that drawer is open so
    // Escape can hand focus back to the system.
    function navDrawerOpen() {
        var d = document.getElementById('appSidebar');
        return !!(d && d.classList.contains('show'));
    }

    // ------------------------------------------------------------------ FETCH
    function api(url, opts) {
        opts = opts || {};
        return fetch(url, {
            method: opts.method || 'GET',
            headers: Object.assign(
                { 'X-Requested-With': 'XMLHttpRequest' },
                opts.body ? { 'Content-Type': 'application/json' } : {},
                opts.method && opts.method !== 'GET' ? { 'X-CSRFToken': CFG.csrf_token } : {}
            ),
            body: opts.body ? JSON.stringify(opts.body) : undefined
        }).then(function (r) {
            return r.json().catch(function () { return { status: 'error', message: 'Server returned an unreadable response.' }; });
        });
    }

    // ==========================================================================
    // CATALOG
    // ==========================================================================

    function visibleProducts() {
        var q = query.trim().toLowerCase();
        var out = PRODUCTS.filter(function (p) {
            if (filterCat !== '__all__' && p.category__name !== filterCat) return false;
            if (!q) return true;
            return (p.name || '').toLowerCase().indexOf(q) >= 0
                || (p.sku || '').toLowerCase().indexOf(q) >= 0;
        });
        return out;
    }

    function renderCategories() {
        var host = $('catFilters');
        var cats = [];
        var seen = {};
        for (var i = 0; i < PRODUCTS.length; i++) {
            var c = PRODUCTS[i].category__name;
            if (c && !seen[c]) { seen[c] = 1; cats.push(c); }
        }
        cats.sort();

        var chips = [{ key: '__all__', label: 'All' }].concat(cats.map(function (c) { return { key: c, label: c }; }));
        host.innerHTML = '';
        chips.forEach(function (chip) {
            var b = el('button', 'cat-chip' + (filterCat === chip.key ? ' active' : ''), chip.label);
            b.setAttribute('data-cat', chip.key);
            host.appendChild(b);
        });
    }

    /**
     * The catalogue's empty state has TWO cases and they need different words,
     * because they need different actions from the cashier:
     *   - nothing in the catalogue at all -> send them to add products
     *   - a search or filter that matched nothing -> tell them to clear it
     * Collapsing these into one "no results" message is what made the old
     * screen confusing.
     */
    function renderCatalogEmpty(list) {
        var grid = $('productGrid');
        var e = el('div', 'catalog-empty');

        if (!PRODUCTS.length) {
            // Nothing has ever been added.
            e.innerHTML = '<div class="cat-empty-icon"><i class="fa-solid fa-box-open"></i></div>'
                + '<p class="cat-empty-title">No products yet</p>'
                + '<p class="cat-empty-text">The catalogue is empty, so there is nothing to sell. '
                + 'Add your first product to start ringing up sales.</p>'
                + '<a class="ag-btn-primary" href="' + esc(URLS.productList || '#') + '">'
                + '<i class="fa-solid fa-plus"></i> Add a product</a>';
        } else if (query) {
            // A search that found nothing.
            e.innerHTML = '<div class="cat-empty-icon"><i class="fa-solid fa-magnifying-glass"></i></div>'
                + '<p class="cat-empty-title">No results for &ldquo;' + esc(query) + '&rdquo;</p>'
                + '<p class="cat-empty-text">Nothing in the catalogue matches that. '
                + 'Check the spelling, or scan the barcode instead.</p>'
                + '<button type="button" class="ag-btn-secondary" data-empty-act="clear-search">'
                + '<i class="fa-solid fa-xmark"></i> Clear search</button>';
        } else {
            // A category with nothing in it.
            e.innerHTML = '<div class="cat-empty-icon"><i class="fa-solid fa-tags"></i></div>'
                + '<p class="cat-empty-title">Nothing in ' + esc(filterCat) + '</p>'
                + '<p class="cat-empty-text">This category has no products in stock right now.</p>'
                + '<button type="button" class="ag-btn-secondary" data-empty-act="clear-filter">'
                + '<i class="fa-solid fa-layer-group"></i> Show all products</button>';
        }
        grid.appendChild(e);
    }

    /** Page buttons, from the reference: numbers with the current one in
     * the yellow gradient. A window around the current page so the strip
     * never grows past the width of the pane. */
    function renderPageNumbers(totalPages) {
        var host = $('pgNumbers');
        if (!host) return;
        host.innerHTML = '';
        // Show at most 7 numbers, always including first and last.
        var WINDOW = 7;
        var start = Math.max(1, Math.min(page - 3, totalPages - WINDOW + 1));
        if (start < 1) start = 1;
        var end = Math.min(totalPages, start + WINDOW - 1);

        if (totalPages <= 1) return;

        for (var n = start; n <= end; n++) {
            var b = el('button', 'pg-btn' + (n === page ? ' active' : ''), String(n));
            b.type = 'button';
            b.setAttribute('data-page', n);
            if (n === page) b.setAttribute('aria-current', 'page');
            b.setAttribute('aria-label', 'Page ' + n + ' of ' + totalPages);
            host.appendChild(b);
        }
    }

    function renderCatalog() {
        var list = visibleProducts();
        var totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
        if (page > totalPages) page = totalPages;
        if (page < 1) page = 1;
        var slice = list.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

        var grid = $('productGrid');
        grid.className = 'catalog-grid mode-' + view;
        grid.innerHTML = '';

        if (!slice.length) {
            renderCatalogEmpty(list);
        }

        // The tile that sits behind the selected cart line keeps the yellow
        // outline, so the two panes always agree about what is selected.
        var selLine = selected >= 0 ? cart[selected] : null;
        var selPid = selLine ? selLine.id : null;

        slice.forEach(function (p) {
            // Out of stock is its own state, separate from low stock. The low
            // threshold is the product's own reorder_level, so this badge
            // agrees with the low-stock alert rather than guessing at 3.
            var out = p.quantity <= 0;
            var reorder = p.reorder_level == null ? 3 : p.reorder_level;
            var low = !out && p.quantity <= reorder;
            var t = el('button', 'p-tile'
                + (out ? ' out' : low ? ' low' : '')
                + (p.id === selPid ? ' is-selected' : ''));
            t.type = 'button';
            t.setAttribute('data-pid', p.id);
            if (out) {
                t.setAttribute('disabled', 'disabled');
                t.setAttribute('aria-label', p.name + ' - out of stock');
            } else {
                t.setAttribute('aria-label', 'Add ' + p.name + ' to the sale, ' + moneyShort(p.price));
            }

            // The red SALE tag only appears when the price really is reduced,
            // and it always carries a word - never a bare red block.
            var isDiscounted = p.original_price != null && p.original_price > p.price;
            if (isDiscounted) {
                t.appendChild(el('span', 'p-sale-tag', 'SALE'));
            }
            if (p.category__name) {
                t.appendChild(el('span', 'p-badge-cat', p.category__name));
            }

            var media = p.image_url
                ? '<img class="p-thumb" src="' + esc(p.image_url) + '" alt="" loading="lazy" decoding="async">'
                : '<div class="p-thumb-ph"><i class="fa-solid fa-image"></i></div>';
            t.innerHTML += media
                + '<div class="p-name">' + esc(p.name) + '</div>'
                + '<div class="p-foot"><span class="p-price">'
                + (isDiscounted ? '<s class="p-was">' + moneyShort(p.original_price) + '</s>' : '')
                + moneyShort(p.price) + '</span>'
                + stockBadgeHtml(p.quantity, out, low) + '</div>';
            grid.appendChild(t);
        });

        $('pageInfo').textContent = 'Page ' + page + ' / ' + totalPages
            + (list.length ? '  ·  ' + list.length + ' items' : '');
        $('pgFirst').disabled = $('pgPrev').disabled = (page <= 1);
        $('pgNext').disabled = $('pgLast').disabled = (page >= totalPages);
        renderPageNumbers(totalPages);
    }

    /**
     * Stock is shown as a coloured dot AND the number AND, when it matters,
     * an icon and a word. Colour alone would fail WCAG 1.4.1 and would be
     * unreadable for a colour-blind cashier on a low-contrast till screen.
     */
    function stockBadgeHtml(qty, out, low) {
        if (out) {
            return '<span class="p-stock p-stock--out">'
                + '<i class="fa-solid fa-circle-xmark"></i> Out of stock</span>';
        }
        if (low) {
            return '<span class="p-stock p-stock--low">'
                + '<i class="fa-solid fa-triangle-exclamation"></i> ' + qty + ' left</span>';
        }
        return '<span class="p-stock p-stock--in">'
            + '<span class="p-stock-dot"></span> ' + qty + ' left</span>';
    }

    function selectView(v) {
        view = v;
        Array.prototype.forEach.call(document.querySelectorAll('.view-btn'), function (b) {
            var on = b.getAttribute('data-view') === v;
            b.classList.toggle('active', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        try { localStorage.setItem('posDensity', v); } catch (e) {}
        renderCatalog();
    }

    // ==========================================================================
    // ARMED QUANTITY  (F4)
    // A cashier selling 4 bottles of the same thing should not have to tap the
    // tile four times. F4 arms a multiplier, the next item takes it, and the
    // terminal is back to normal. The badge on the toolbar button is what makes
    // this safe: a live multiplier is always visible, never hidden in a dialog
    // that has already closed.
    // ==========================================================================

    function paintArmedQty() {
        var btn = $('btnQty');
        var badge = $('qtyBadge');
        if (btn) btn.classList.toggle('is-active', armedQty > 1);
        if (badge) {
            badge.textContent = '×' + armedQty;
            badge.hidden = armedQty <= 1;
        }
    }

    /** Clear the arming and take the badge away. Safe to call at any time. */
    function spendArmedQty() {
        armedQty = 1;
        paintArmedQty();
    }

    function openQty() {
        $('qtyInput').value = armedQty > 1 ? String(armedQty) : '';
        openModal('modalQty');
    }

    function applyQty() {
        var raw = $('qtyInput').value.trim();
        if (raw === '') {
            // An empty box means "back to normal", not an error - it is the
            // obvious way to disarm and the most likely thing to be typed.
            spendArmedQty();
            closeModal('modalQty');
            toast('Quantity back to 1.', '');
            return;
        }
        // Digits only: a decimal or a sign here would silently become NaN and
        // fall through to 1, which is exactly the kind of surprise a till
        // cannot have.
        if (!/^[0-9]+$/.test(raw)) {
            toast('Enter a whole number.', 'err');
            $('qtyInput').focus();
            $('qtyInput').select();
            return;
        }
        var n = parseInt(raw, 10);
        if (!n || n < 1) { toast('Quantity must be 1 or more.', 'err'); return; }
        if (n > 999) { toast('Quantity cannot exceed 999.', 'err'); return; }
        armedQty = n;
        paintArmedQty();
        closeModal('modalQty');
        if (n > 1) {
            toast('Next item will be added ×' + n + '.', 'ok');
            // Hand focus back to the scanner box so the very next thing the
            // cashier does is scan or tap, not reach for the mouse.
            $('productSearch').focus();
        } else {
            toast('Quantity back to 1.', '');
        }
    }

    // ==========================================================================
    // CART
    // ==========================================================================

    /**
     * Add a product to the cart.
     *
     * `qty` is the multiplier for the NEXT item (F4). When the caller does not
     * pass one - which is every normal tap or scan - the armed value is taken
     * and immediately spent, so the terminal is back to 1 for the item after
     * it. An explicit qty (the OSK, a repeat) does not touch the arming.
     *
     * The arm is spent even if stock stops us part-way through, otherwise a
     * failed add would leave a live multiplier sitting on the terminal.
     */
    function addToCart(id, qty) {
        var product = PRODUCTS.find(function (p) { return p.id === id; });
        if (!product) return false;
        if (product.quantity <= 0) {
            toast(product.name + ' is out of stock.', 'err');
            return false;
        }
        var useArm = (qty == null);
        if (useArm) {
            qty = armedQty;
            spendArmedQty();
        }
        qty = qty || 1;
        var line = cart.find(function (i) { return i.id === id; });
        if (line) {
            if (line.qty + qty > line.max_stock) {
                toast('Only ' + line.max_stock + ' of ' + line.name + ' in stock.', 'warn');
                qty = Math.max(0, line.max_stock - line.qty);
                if (!qty) return false;
            }
            line.qty += qty;
            // Re-adding a voided line brings it back to life.
            if (line.voided) { line.voided = false; flashLineId = id; }
        } else {
            if (qty > product.quantity) qty = product.quantity;
            cart.push({
                id: product.id,
                name: product.name,
                sku: product.sku,
                price: parseFloat(product.price),
                original_price: parseFloat(product.price),
                qty: qty,
                max_stock: product.quantity,
                comment: '',
                voided: false,
                category__name: product.category__name
            });
            flashLineId = id;
        }
        selected = cart.findIndex(function (i) { return i.id === id; });
        renderCart();
        renderCatalog();
        return true;
    }

    /**
     * Void a single line, or bring a voided one back. Destructive either way,
     * so it confirms before it acts.
     */
    function toggleVoidLine(index) {
        var line = cart[index];
        if (!line) return;
        if (line.voided) {
            line.voided = false;
            toast(line.name + ' restored.', 'ok');
        } else {
            if (!confirm('Void "' + line.name + '"? It stays on screen struck through and is not charged. You can restore it.')) return;
            line.voided = true;
            toast(line.name + ' voided.', 'warn');
        }
        renderCart();
    }

    function setQty(index, qty) {
        var line = cart[index];
        if (!line) return;
        qty = parseInt(qty, 10);
        if (isNaN(qty)) return;
        if (qty > line.max_stock) {
            toast('Only ' + line.max_stock + ' of ' + line.name + ' in stock.', 'warn');
            qty = line.max_stock;
        }
        if (qty <= 0) { removeLine(index); return; }
        line.qty = qty;
        renderCart();
    }

    function bumpQty(index, delta) {
        if (!cart[index]) return;
        setQty(index, cart[index].qty + delta);
    }

    function removeLine(index) {
        if (index < 0 || index >= cart.length) return;
        cart.splice(index, 1);
        if (selected >= cart.length) selected = cart.length - 1;
        renderCart();
    }

    function deleteSelected() {
        if (selected < 0 || !cart[selected]) {
            toast('Select a line first.', 'warn');
            return;
        }
        var name = cart[selected].name;
        cart.splice(selected, 1);
        if (selected >= cart.length) selected = cart.length - 1;
        renderCart();
        toast('Removed ' + name, 'ok');
    }

    function clearCart(silent) {
        // A live multiplier must never survive into the next order, or the
        // first customer of the next sale gets somebody else's quantity.
        spendArmedQty();
        if (!cart.length) return false;
        if (!silent && !confirmVoid()) return false;
        cart = [];
        selected = -1;
        renderCart();
        if (!silent) toast('Order voided.', 'warn');
        return true;
    }

    /** Replaces the whole basket (used by hold / resume / repeat). */
    function loadCart(items, opts) {
        opts = opts || {};
        cart = [];
        (items || []).forEach(function (it) {
            var product = PRODUCTS.find(function (p) { return p.id === it.id; });
            var maxStock = product ? product.quantity : (it.max_stock || it.qty);
            cart.push({
                id: it.id,
                name: it.name || (product ? product.name : 'Item'),
                sku: it.sku || (product ? product.sku : ''),
                price: parseFloat(it.price),
                original_price: parseFloat(it.original_price != null ? it.original_price : it.price),
                qty: Math.max(1, parseInt(it.qty, 10) || 1),
                max_stock: maxStock,
                comment: it.comment || '',
                category__name: it.category__name || (product ? product.category__name : null)
            });
        });
        selected = cart.length ? 0 : -1;
        renderCart();
        if (!opts.quiet) toast(cart.length + ' item(s) loaded.', 'ok');
    }

    /**
     * Move the yellow tile outline onto whichever product the selected cart
     * line belongs to. Done as a class toggle rather than a full
     * renderCatalog() so selecting a line in a 24-tile grid stays instant.
     */
    function syncTileSelection() {
        var selLine = selected >= 0 ? cart[selected] : null;
        var selPid = selLine ? String(selLine.id) : null;
        var tiles = document.querySelectorAll('#productGrid .p-tile');
        for (var i = 0; i < tiles.length; i++) {
            var on = selPid !== null && tiles[i].getAttribute('data-pid') === selPid;
            tiles[i].classList.toggle('is-selected', on);
        }
    }

    function renderCart() {
        var host = $('cartList');
        var t = totals();
        var payable = payableLines();

        if (!cart.length) {
            host.innerHTML = '<div class="cart-empty"><i class="fa-solid fa-cart-shopping"></i>'
                + '<p>Tap a product or scan a barcode</p></div>';
        } else {
            var frag = document.createDocumentFragment();
            cart.forEach(function (line, i) {
                var isDisc = line.original_price > line.price;
                var over = line.qty > line.max_stock;
                var isVoid = !!line.voided;
                var row = el('div', 'cart-line'
                    + (i === selected ? ' selected' : '')
                    + (isDisc && !isVoid ? ' is-discounted' : '')
                    + (over && !isVoid ? ' is-over' : '')
                    + (isVoid ? ' is-voided' : '')
                    + (line.id === flashLineId ? ' is-new' : ''));
                row.setAttribute('data-idx', i);
                if (isVoid) row.setAttribute('aria-label', line.name + ' - voided');

                var nameHtml = '<div class="cl-name">' + esc(line.name) + '</div>';
                var totalHtml = '<div class="cl-line-total">' + money(line.price * line.qty) + '</div>';

                var meta = '<span class="cl-seq">#' + (i + 1) + '</span>'
                    + '<span class="cl-unit">' + money(line.price) + ' × ' + line.qty + '</span>';
                if (isDisc) meta += '<span class="cl-was">' + money(line.original_price) + '</span>';
                if (line.comment) meta += '<span class="cl-comment"><i class="fa-solid fa-comment-dots"></i>'
                    + esc(line.comment) + '</span>';

                if (isVoid) {
                    // Red is never the only signal: the strike, the icon and
                    // the word all carry it.
                    meta += '<span class="cl-void-tag"><i class="fa-solid fa-ban"></i> Voided</span>';
                    meta += '<span class="cl-void-btn" data-act="unvoid" title="Restore this line">'
                        + '<i class="fa-solid fa-rotate-left"></i> Restore</span>';
                } else {
                    meta += '<span class="cl-qty-btn" data-act="dec" title="Decrease" role="button" aria-label="Decrease quantity of ' + esc(line.name) + '"><i class="fa-solid fa-minus"></i></span>';
                    meta += '<span class="cl-qty">' + line.qty + '</span>';
                    meta += '<span class="cl-qty-btn" data-act="inc" title="Increase" role="button" aria-label="Increase quantity of ' + esc(line.name) + '"><i class="fa-solid fa-plus"></i></span>';
                    meta += '<span class="cl-void-btn" data-act="void" title="Void this line"><i class="fa-solid fa-ban"></i> Void</span>';
                }

                row.innerHTML = '<span class="cl-dot"></span>' + nameHtml + totalHtml
                    + '<div class="cl-meta">' + meta + '</div>';
                frag.appendChild(row);
            });
            host.innerHTML = '';
            host.appendChild(frag);
        }
        // The flash is a one-shot: clear it so the next repaint is calm.
        flashLineId = null;

        // Keep the catalogue's yellow outline in step with the cart selection.
        syncTileSelection();

        $('sumTotal').textContent = money(t.gross);
        // The count describes what is being sold, so a voided line stops
        // being counted rather than quietly inflating the basket.
        $('itemCount').textContent = payable.length;

        // F10 shows the amount owed as soon as the cart has something in it,
        // so the cashier can read the total without looking away from the bar.
        var payAmount = $('fkeyPayAmount');
        if (payAmount) payAmount.textContent = payable.length ? money(t.gross) : '';

        var empty = payable.length === 0;
        ['btnDelete', 'btnVoid', 'btnComment', 'btnDiscount', 'fkeyPay', 'fkeyCash'].forEach(function (id) {
            var n = $(id);
            if (n) n.disabled = empty;
        });
    }

    // ==========================================================================
    // LINE ACTIONS: discount / comment
    // ==========================================================================

    function openDiscount() {
        if (selected < 0 || !cart[selected]) { toast('Select a line to discount.', 'warn'); return; }
        var line = cart[selected];
        $('discName').textContent = line.name;
        $('discCurrent').textContent = money(line.price);
        $('discWas').textContent = 'Shelf price ' + money(line.original_price);
        $('discInput').value = line.price < line.original_price ? line.price : '';
        $('discInput').focus();
        $('discInput').select();
        openModal('modalDiscount');
    }

    function applyDiscount() {
        var line = cart[selected];
        if (!line) { closeModal('modalDiscount'); return; }
        var raw = $('discInput').value.trim();
        if (raw === '') { closeModal('modalDiscount'); return; }
        var val = parseFloat(raw);
        if (isNaN(val) || val < 0) { toast('Enter a valid price.', 'err'); return; }
        if (val > line.original_price) { toast('Price cannot exceed the shelf price.', 'err'); return; }

        if (val < line.original_price && $('discReason').value.trim() === '') {
            toast('A reason is required for a price reduction.', 'err');
            $('discReason').focus();
            return;
        }
        line.price = round2(val);
        if (val === line.original_price) { line.original_price = round2(val); }
        renderCart();
        closeModal('modalDiscount');
        toast('Price updated.', 'ok');
    }

    function openComment() {
        if (selected < 0 || !cart[selected]) { toast('Select a line to comment.', 'warn'); return; }
        var line = cart[selected];
        $('cmtName').textContent = line.name;
        $('cmtInput').value = line.comment || '';
        openModal('modalComment');
    }

    function applyComment() {
        var line = cart[selected];
        if (!line) { closeModal('modalComment'); return; }
        line.comment = $('cmtInput').value.trim().slice(0, 255);
        renderCart();
        closeModal('modalComment');
        toast(line.comment ? 'Comment saved.' : 'Comment cleared.', 'ok');
    }

    // ==========================================================================
    // CUSTOMER
    // ==========================================================================

    // The customer pill and the customer-lookup modal were removed from the UI.
    // setCustomer() is still called by resumeHeld()/repeatLast(), where the sale
    // being restored already carries a customer, so it keeps working - but every
    // element it used to paint is optional now.
    function setCustomer(c) {
        customer = c || null;
        var nameEl = $('custName');
        if (nameEl) nameEl.textContent = customer ? customer.name : 'Walk-in Customer';
        var clearBtn = $('btnCustClear');
        if (clearBtn) clearBtn.style.display = customer ? '' : 'none';
        var creditBtn = $('pmCredit');
        if (creditBtn) creditBtn.classList.toggle('disabled', !customer);
    }

    // ==========================================================================
    // PAYMENT
    // ==========================================================================

    var payMethod = 'CASH';

    function setPayMethod(m) {
        if (m === 'CREDIT' && !customer) {
            toast('Select a customer for a credit sale.', 'warn');
            return;
        }
        payMethod = m;
        Array.prototype.forEach.call(document.querySelectorAll('.pay-method'), function (b) {
            var on = b.getAttribute('data-method') === m;
            b.classList.toggle('active', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        var needsRef = (m === 'GCASH' || m === 'BANK');
        $('payRefGroup').style.display = needsRef ? '' : 'none';
        $('payTenderGroup').style.display = (m === 'CREDIT') ? 'none' : '';
        $('payChangeRow').style.display = (m === 'CREDIT') ? 'none' : 'flex';
        // Quick amounts and the numpad both key off CASH, so they go away
        // together rather than leaving a dead pad on a GCash sale.
        $('quickCash').style.display = (m === 'CASH') ? '' : 'none';
        $('payNumpad').style.display = (m === 'CASH') ? '' : 'none';
        updateChange();
    }

    /**
     * Numpad. Types into the tender field exactly as a physical keyboard
     * would, so there is only one code path for the value.
     */
    function numpadPress(key) {
        if (payMethod !== 'CASH') return;
        var field = $('payTender');
        if (!field) return;
        var v = field.value;
        if (key === 'clear') {
            v = '';
        } else if (key === 'back') {
            v = v.slice(0, -1);
        } else {
            // One decimal point only, and never a leading one.
            if (key === '.' && (v.indexOf('.') >= 0 || v === '')) return;
            // Drop a leading zero so "0" then "5" gives 5, not 05.
            if (v === '0' && key !== '.') v = '';
            v += key;
        }
        field.value = v;
        field.focus();
        updateChange();
    }

    function openPayment(forceMethod) {
        if (!cart.length) { toast('Cart is empty.', 'warn'); return; }
        paying = true;
        var t = totals();
        $('payDue').textContent = money(t.gross);
        $('payTender').value = '';
        $('payRef').value = '';
        $('btnConfirmPay').disabled = true;
        setPayMethod(forceMethod || (customer ? 'CREDIT' : 'CASH'));
        openModal('modalPayment');
    }

    function updateChange() {
        if (payMethod === 'CREDIT') return;
        var t = totals();
        var paid = parseFloat($('payTender').value);
        if (isNaN(paid)) paid = 0;
        var change = round2(paid - t.gross);
        var short = change < 0;
        $('payChange').textContent = (short ? '−' : '') + money(Math.abs(change));
        $('payChangeRow').classList.toggle('short', short);

        var needsRef = (payMethod === 'GCASH' || payMethod === 'BANK');
        var ok = !short && (!needsRef || $('payRef').value.trim() !== '');
        $('btnConfirmPay').disabled = !ok;
    }

    function submitPayment() {
        // A voided line is never sent - it is not being sold.
        var selling = payableLines();
        if (!selling.length) return;
        var t = totals();
        var paid = payMethod === 'CREDIT' ? 0 : (parseFloat($('payTender').value) || 0);

        var payload = {
            items: selling.map(function (l) {
                return {
                    id: l.id, qty: l.qty, price: l.price,
                    original_price: l.original_price,
                    comment: l.comment,
                    override_reason: l.comment || ''
                };
            }),
            amount_paid: paid,
            payment_method: payMethod,
            payment_description: $('payRef').value.trim(),
            customer_id: customer ? customer.id : ''
        };

        var btn = $('btnConfirmPay');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing…';

        api(URLS.checkout, { method: 'POST', body: payload }).then(function (data) {
            if (data.status === 'success') {
                closeModal('modalPayment');
                paying = false;
                showReceipt(data);
            } else {
                toast(data.message || 'Checkout failed.', 'err');
                btn.disabled = false;
                btn.textContent = 'Complete Sale';
            }
        }).catch(function () {
            toast('Connection error. Please try again.', 'err');
            btn.disabled = false;
            btn.textContent = 'Complete Sale';
        });
    }

    function showReceipt(data) {
        $('rcptId').textContent = data.receipt_id;
        $('rcptCust').textContent = data.customer_name || 'Walk-in Customer';
        $('rcptDate').textContent = data.date || '';
        $('rcptItems').innerHTML = (data.items || []).map(function (i) {
            return '<tr><td>' + esc(i.name) + '</td><td class="num">' + i.qty + '</td>'
                + '<td class="num">' + i.price + '</td><td class="num">' + i.total + '</td></tr>';
        }).join('');
        $('rcptTotal').textContent = CURRENCY + (data.total || '0.00');
        $('rcptTotalLine').textContent = CURRENCY + (data.total || '0.00');
        $('rcptPaid').textContent = CURRENCY + (data.amount_paid || '0.00');
        $('rcptChange').textContent = CURRENCY + (data.change || '0.00');
        $('rcptMethod').textContent = payMethod;
        openModal('modalReceipt');

        cart = [];
        selected = -1;
        spendArmedQty();
        renderCart();
    }

    function finishSale() {
        closeModal('modalReceipt');
        $('productSearch').value = '';
        query = '';
        renderCatalog();
        $('productSearch').focus();
    }

    // ==========================================================================
    // SAVE SALE (parked tickets) - F9
    // ==========================================================================

    function openHeld() {
        openModal('modalHeld');
        loadHeld();
    }

    function loadHeld() {
        api(URLS.holdList).then(function (data) {
            var host = $('heldList');
            host.innerHTML = '';
            var tickets = data.tickets || [];
            heldCount = tickets.length;
            updateHeldBadge();
            if (!tickets.length) {
                host.innerHTML = '<div class="state-msg"><i class="fa-solid fa-inbox"></i>'
                    + '<p>No parked orders</p></div>';
                return;
            }
            tickets.forEach(function (t) {
                var row = el('div', 'ticket');
                row.innerHTML = '<span class="tk-id">' + esc(t.ticket_id) + '</span>'
                    + '<div class="tk-main"><div class="tk-label">' + esc(t.label) + '</div>'
                    + '<div class="tk-meta">' + t.item_count + ' item(s) · ' + esc(t.cashier || '') + ' · ' + esc(t.timestamp) + '</div></div>'
                    + '<div class="tk-total">' + CURRENCY + esc(t.total) + '</div>';
                var btns = el('div', 'tk-btns');
                var resume = el('button', 'btn btn-primary', 'Resume');
                resume.addEventListener('click', function () { resumeHeld(t.ticket_id); });
                var drop = el('button', 'btn btn-danger', 'Discard');
                drop.addEventListener('click', function () { discardHeld(t.ticket_id); });
                btns.appendChild(resume);
                btns.appendChild(drop);
                row.appendChild(btns);
                host.appendChild(row);
            });
        });
    }

    function resumeHeld(ticketId) {
        api(URLS.holdResume.replace('__ID__', ticketId), { method: 'POST' }).then(function (data) {
            if (data.status !== 'success') { toast(data.message || 'Could not resume.', 'err'); return; }
            closeModal('modalHeld');
            clearCart(true);
            loadCart((data.payload || {}).items, { quiet: true });
            if (data.payload && data.payload.customer_id) {
                var c = CUSTOMERS.find(function (x) { return x.id === data.payload.customer_id; });
                setCustomer(c ? { id: c.id, name: c.name, customer_id: c.customer_id } : null);
            } else {
                setCustomer(null);
            }
            heldCount = Math.max(0, heldCount - 1);
            updateHeldBadge();
            toast('Resumed ' + (data.label || ticketId), 'ok');
        });
    }

    function discardHeld(ticketId) {
        if (!confirm('Discard this parked order? It cannot be recovered.')) return;
        api(URLS.holdDiscard.replace('__ID__', ticketId), { method: 'POST' }).then(function (data) {
            if (data.status === 'success') {
                heldCount = Math.max(0, heldCount - 1);
                updateHeldBadge();
                loadHeld();
                toast('Parked order discarded.', 'warn');
            } else {
                toast(data.message || 'Could not discard.', 'err');
            }
        });
    }

    function saveSale() {
        if (!cart.length) { toast('Cart is empty - nothing to save.', 'warn'); return; }
        var t = totals();
        $('saveTotal').textContent = money(t.gross);
        $('saveLabel').value = cart.length === 1
            ? cart[0].name
            : cart[0].name + ' +' + (cart.length - 1);
        openModal('modalSave');
    }

    function confirmSave() {
        var btn = $('btnSaveConfirm');
        btn.disabled = true;
        api(URLS.holdSave, {
            method: 'POST',
            body: {
                label: $('saveLabel').value.trim(),
                customer_id: customer ? customer.id : null,
                total: totals().gross,
                items: cart.map(function (l) {
                    return {
                        id: l.id, name: l.name, sku: l.sku, qty: l.qty,
                        price: l.price, original_price: l.original_price, comment: l.comment
                    };
                })
            }
        }).then(function (data) {
            btn.disabled = false;
            if (data.status === 'success') {
                closeModal('modalSave');
                clearCart(true);
                heldCount += 1;
                updateHeldBadge();
                toast('Parked as ' + data.ticket_id, 'ok');
            } else {
                toast(data.message || 'Could not save the order.', 'err');
            }
        });
    }

    function updateHeldBadge() {
        var b = $('heldBadge');
        b.textContent = heldCount;
        b.classList.toggle('show', heldCount > 0);
    }

    // ==========================================================================
    // REPEAT LAST SALE
    // ==========================================================================

    function repeatLast() {
        if (cart.length && !confirm('Repeat will replace the current order. Continue?')) return;
        api(URLS.repeatLast).then(function (data) {
            if (data.status !== 'success') { toast(data.message || 'Nothing to repeat.', 'err'); return; }
            clearCart(true);
            loadCart(data.items, { quiet: true });
            if (data.customer_id) {
                setCustomer({ id: data.customer_id, name: data.customer_name });
            } else {
                setCustomer(null);
            }
            toast('Repeated ' + data.receipt_id, 'ok');
        });
    }

    // ==========================================================================
    // TRANSFER  (ring the order at another till / hand off)
    // ==========================================================================

    function openTransfer() {
        if (!cart.length) { toast('Cart is empty - nothing to transfer.', 'warn'); return; }
        $('trfTotal').textContent = money(totals().gross);
        $('trfTo').value = '';
        openModal('modalTransfer');
    }

    function doTransfer() {
        var to = $('trfTo').value.trim();
        if (!to) { toast('Enter the receiving till or staff member.', 'err'); return; }
        var payload = {
            label: 'To ' + to,
            customer_id: customer ? customer.id : null,
            total: totals().gross,
            items: cart.map(function (l) {
                return {
                    id: l.id, name: l.name, sku: l.sku, qty: l.qty,
                    price: l.price, original_price: l.original_price, comment: l.comment
                };
            })
        };
        api(URLS.holdSave, { method: 'POST', body: payload }).then(function (data) {
            if (data.status === 'success') {
                closeModal('modalTransfer');
                clearCart(true);
                heldCount += 1;
                updateHeldBadge();
                toast('Transferred to ' + to + ' as ' + data.ticket_id, 'ok');
            } else {
                toast(data.message || 'Transfer failed.', 'err');
            }
        });
    }

    // ==========================================================================
    // CASH DRAWER
    // ==========================================================================

    function openDrawerDialog() {
        openModal('modalDrawer');
        api(URLS.drawerStatus).then(function (data) {
            drawerOpen = !!data.is_open;
            paintDrawer(data);
        });
    }

    function paintDrawer(data) {
        if (data.is_open) {
            $('drawerState').textContent = 'OPEN since ' + data.opened_at + (data.opened_by ? ' · ' + data.opened_by : '');
            $('drawerExpected').textContent = CURRENCY + data.expected_cash;
            $('drawerOpenForm').style.display = 'none';
            $('drawerCloseForm').style.display = '';
        } else {
            $('drawerState').textContent = 'CLOSED - no active session';
            $('drawerOpenForm').style.display = '';
            $('drawerCloseForm').style.display = 'none';
        }
    }

    function drawerOpenIt() {
        var v = parseFloat($('drawerFloat').value);
        if (isNaN(v) || v < 0) { toast('Enter a valid opening float.', 'err'); return; }
        api(URLS.drawerOpen, { method: 'POST', body: { opening_float: v } }).then(function (data) {
            if (data.status === 'success') {
                drawerOpen = true;
                paintDrawer({ is_open: true, opened_at: data.opened_at, expected_cash: '0.00' });
                toast('Drawer opened.', 'ok');
            } else {
                toast(data.message || 'Could not open the drawer.', 'err');
            }
        });
    }

    function drawerCloseIt() {
        var v = parseFloat($('drawerCounted').value);
        if (isNaN(v) || v < 0) { toast('Enter the amount you counted.', 'err'); return; }
        api(URLS.drawerClose, { method: 'POST', body: { counted_cash: v, notes: $('drawerNotes').value } }).then(function (data) {
            if (data.status === 'success') {
                drawerOpen = false;
                paintDrawer({ is_open: false });
                var diff = parseFloat(data.difference.replace(/,/g, ''));
                toast('Drawer closed. ' + (diff === 0 ? 'Balanced.' : (diff < 0 ? 'Short ' : 'Over ') + CURRENCY + Math.abs(diff).toFixed(2)),
                    diff === 0 ? 'ok' : 'warn');
            } else {
                toast(data.message || 'Could not close the drawer.', 'err');
            }
        });
    }

    // ==========================================================================
    // VOID
    // ==========================================================================

    function confirmVoid() {
        var t = totals();
        return window.confirm('Void this order?\n\n' + cart.length + ' item(s) · ' + money(t.gross));
    }

    // ==========================================================================
    // REFUND
    // ==========================================================================

    function openRefund() {
        $('refundId').value = '';
        $('refundResult').innerHTML = '<div class="state-msg"><i class="fa-solid fa-receipt"></i>'
            + '<p>Enter a receipt number</p></div>';
        openModal('modalRefund');
    }

    function searchRefund() {
        var rid = $('refundId').value.trim();
        if (!rid) return;
        var host = $('refundResult');
        host.innerHTML = '<div class="state-msg"><i class="fa-solid fa-circle-notch fa-spin"></i>'
            + '<p>Looking up…</p></div>';
        fetch(URLS.refundSearch + '?rid=' + encodeURIComponent(rid), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) { return r.json(); })
            .then(function (data) {
                host.innerHTML = '';
                if (data.status !== 'success' || !data.items || !data.items.length) {
                    host.innerHTML = '<div class="state-msg"><i class="fa-solid fa-circle-question"></i>'
                        + '<p>' + esc(data.message || 'No refundable items on that receipt.') + '</p></div>';
                    return;
                }
                var total = data.items.reduce(function (a, i) { return a + i.qty; }, 0);
                var h = '<div class="result-list">';
                data.items.forEach(function (i) {
                    h += '<div class="result-row"><div class="rr-main"><div class="rr-name">'
                        + esc(i.name) + '</div><div class="rr-meta">'
                        + i.qty + ' unit(s) returnable</div></div></div>';
                });
                host.innerHTML = h + '</div>'
                    + '<p class="field-hint">' + total + ' unit(s) returnable. Refunds are completed in the '
                    + 'Refund Portal, where the return reason is recorded against the sale.</p>';
            })
            .catch(function () {
                host.innerHTML = '<div class="state-msg"><i class="fa-solid fa-triangle-exclamation"></i>'
                    + '<p>Could not reach the server.</p></div>';
            });
    }

    // ==========================================================================
    // LOCK
    // ==========================================================================

    function lockTerminal() {
        // A multiplier armed on a screen someone walked away from should not
        // be sitting there waiting to quadruple the first scan after unlock.
        spendArmedQty();
        locked = true;
        $('lockScreen').classList.add('open');
        setTimeout(function () { $('lockPin').focus(); }, 80);
    }

    /**
     * This is a screen lock against a curious customer, NOT an authorisation
     * boundary - anything that matters (voids, price overrides, drawer counts)
     * is enforced server-side. So unlocking is a deliberate keypress, with no
     * fake PIN to imply a security guarantee that does not exist.
     */
    function unlockTerminal() {
        locked = false;
        $('lockScreen').classList.remove('open');
        $('lockPin').value = '';
        $('productSearch').focus();
    }

    // ==========================================================================
    // KEYBOARD
    // ==========================================================================

    function typingIn(t) {
        return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    }

    function onKeydown(e) {
        // --- function keys work everywhere except while typing ---
        var fk = e.key;
        if (fk === 'F9')  { e.preventDefault(); if (!locked) openHeld(); return; }
        if (fk === 'F10') { e.preventDefault(); if (!locked) openPayment(); return; }
        if (fk === 'F12') { e.preventDefault(); if (!locked) openPayment('CASH'); return; }
        if (fk === 'F1')  { e.preventDefault(); if (!locked) $('productSearch').focus(); return; }
        if (fk === 'F2')  { e.preventDefault(); if (!locked) openTransfer(); return; }
        if (fk === 'F3')  { e.preventDefault(); if (!locked) openDiscount(); return; }
        if (fk === 'F4')  { e.preventDefault(); if (!locked) openQty(); return; }
        if (fk === 'F5')  { e.preventDefault(); if (!locked && cart.length && confirmVoid()) clearCart(true); return; }
        if (fk === 'F6')  { e.preventDefault(); if (!locked) openRefund(); return; }
        if (fk === 'F7')  { e.preventDefault(); if (!locked) openDrawerDialog(); return; }
        if (fk === 'F8')  { e.preventDefault(); if (!locked) deleteSelected(); return; }
        if (fk === 'F11') { e.preventDefault(); if (!locked) lockTerminal(); return; }

        if (locked) {
            if (fk === 'Escape') { e.preventDefault(); unlockTerminal(); }
            return;
        }

        // --- Escape: close the topmost layer ---
        if (e.key === 'Escape') {
            if (anyModalOpen()) { e.preventDefault(); closeTopModal(); }
            return;
        }

        if (anyModalOpen()) return;

        // --- barcode scanner: Enter commits whatever was typed ---
        if (e.key === 'Enter' && typingIn(e.target) && e.target.id === 'productSearch') {
            e.preventDefault();
            var q = e.target.value.trim();
            if (!q) return;
            var exact = PRODUCTS.find(function (p) {
                return (p.sku || '').toLowerCase() === q.toLowerCase();
            });
            if (exact) {
                // No explicit qty: the armed F4 multiplier applies.
                if (addToCart(exact.id)) {
                    toast(exact.name + ' added', 'ok');
                    e.target.value = '';
                    query = '';
                    renderCatalog();
                }
                return;
            }
            var matches = visibleProducts();
            if (matches.length === 1) {
                addToCart(matches[0].id);
                e.target.value = '';
                query = '';
                renderCatalog();
                return;
            }
            toast(matches.length + ' matches - keep typing to narrow down', 'warn');
            return;
        }

        // --- Delete removes the selected line ---
        if ((e.key === 'Delete' || e.key === 'Backspace') && !typingIn(e.target)) {
            e.preventDefault();
            deleteSelected();
            return;
        }

        // --- Up/Down walk the cart without touching the mouse ---
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            if (!cart.length) return;
            e.preventDefault();
            var dir = e.key === 'ArrowDown' ? 1 : -1;
            selected = Math.max(0, Math.min(cart.length - 1, (selected < 0 ? 0 : selected + dir)));
            renderCart();
            var node = $('cartList').querySelector('.cart-line.selected');
            if (node) node.scrollIntoView({ block: 'nearest' });
            return;
        }

        // --- +/- on the selected line ---
        if ((e.key === '+' || e.key === '=') && !typingIn(e.target)) { e.preventDefault(); bumpQty(selected, 1); return; }
        if ((e.key === '-' || e.key === '_') && !typingIn(e.target)) { e.preventDefault(); bumpQty(selected, -1); return; }

        // --- any other printable key jumps to search, like a real till ---
        if (!typingIn(e.target) && !e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
            $('productSearch').focus();
        }
    }

    // ==========================================================================
    // WIRING
    // ==========================================================================

    /**
     * The terminal no longer needs to measure itself.
     *
     * It used to sit inside the old app shell as a rounded card and had to
     * work out how much height was left over. It is now a true full-screen
     * workspace: body is 100dvh with no page scroll, and .pos-shell is a
     * flex child that fills whatever is left under the slim top bar. CSS
     * owns the height, so this only nudges the cart width when the viewport
     * is too narrow for the default one.
     */
    function fitShell() {
        var shell = document.querySelector('.pos-shell');
        if (!shell) return;
        // Below ~900px the panes stack, so a fixed cart width is meaningless.
        if (window.innerWidth < 900) {
            shell.style.removeProperty('--pos-cart-w');
        }
    }

    function debounce(fn, ms) {
        var t;
        return function () {
            clearTimeout(t);
            var a = arguments, self = this;
            t = setTimeout(function () { fn.apply(self, a); }, ms);
        };
    }

    /* ---------------------------------------------------------------------
       ON-SCREEN KEYBOARD
       An all-touch till has no physical keyboard, so there is nowhere to type
       a product name. This builds a real keyboard out of <button>s (so it
       works with a finger, a mouse, Tab and Enter) and types into whichever
       input is focused - in practice the search box. It deliberately does NOT
       bind letter keys globally: the physical-keyboard path already exists in
       onKeydown, and hijacking it would break a till that has a real one.
       --------------------------------------------------------------------- */
    var oskOpen = false;

    function oskTargetInput() {
        // Prefer the search box; fall back to any text input in an open modal.
        var s = $('productSearch');
        if (s && !s.disabled) return s;
        var inputs = document.querySelectorAll('.modal-scrim.open input[type="text"]');
        for (var i = 0; i < inputs.length; i++) return inputs[i];
        return s;
    }

    function oskType(text) {
        var input = oskTargetInput();
        if (!input) return;
        input.focus();
        if (text === '\b') {
            var v = input.value;
            input.value = v.slice(0, v.length - 1);
        } else {
            input.value += text;
        }
        // Fire the same event a real keystroke would, so the existing
        // debounced search handler runs and the list filters.
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function buildOsk() {
        var host = $('oskBody');
        if (!host || host.childNodes.length) return;
        var rows = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
            ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', '-'],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm', '.', '/', "'"],
            ['\b', 'space', 'clear', 'enter']
        ];
        host.innerHTML = '';
        rows.forEach(function (keys) {
            var rowEl = el('div', 'osk-row');
            keys.forEach(function (k) {
                var label = k === '\b' ? 'Backspace'
                    : k === 'space' ? 'Space'
                    : k === 'clear' ? 'Clear'
                    : k === 'enter' ? 'Enter' : k;
                var icon = k === '\b' ? '<i class="fa-solid fa-delete-left"></i>'
                    : k === 'enter' ? '<i class="fa-solid fa-arrow-turn-down"></i>'
                    : k === 'clear' ? '<i class="fa-solid fa-eraser"></i>'
                    : k === 'space' ? 'Space' : '';
                var b = el('button', 'osk-key osk-key--' + (k === '\b' ? 'wide' : k === 'space' ? 'space' : (k === 'clear' || k === 'enter') ? 'action' : ''));
                b.type = 'button';
                b.setAttribute('data-key', k);
                b.setAttribute('aria-label', label);
                b.innerHTML = icon || k;
                b.addEventListener('click', function () {
                    if (k === 'enter') {
                        var first = document.querySelector('.p-tile:not([disabled])');
                        if (first) first.click();
                        return;
                    }
                    if (k === 'clear') {
                        var input = oskTargetInput();
                        if (input) { input.value = ''; input.dispatchEvent(new Event('input', { bubbles: true })); }
                        return;
                    }
                    oskType(k);
                });
                rowEl.appendChild(b);
            });
            host.appendChild(rowEl);
        });
    }

    function updateSearchClear() {
        var b = $('btnSearchClear');
        if (b) b.hidden = !query;
    }

    /** One debounced re-filter, shared by the input handler and the OSK so
     * both paths behave identically. */
    var debouncedSearch = debounce(function () { renderCatalog(); }, 130);

    /** Placeholder tiles while the search settles. */
    function showCatalogSkeleton() {
        var grid = $('productGrid');
        if (!grid) return;
        grid.innerHTML = '';
        for (var i = 0; i < 8; i++) {
            grid.appendChild(el('div', 'p-skeleton'));
        }
    }

    function toggleOsk() {
        oskOpen = !oskOpen;
        var osk = $('posOsk');
        var btn = $('btnOsk');
        if (osk) osk.hidden = !oskOpen;
        if (btn) {
            btn.classList.toggle('is-active', oskOpen);
            btn.setAttribute('aria-pressed', oskOpen ? 'true' : 'false');
        }
        if (oskOpen) {
            var input = oskTargetInput();
            if (input) input.focus();
        }
    }

    /* ---------------------------------------------------------------------
       DRAGGABLE DIVIDER
       The order-pane width is a single CSS custom property (--pos-cart-w), so
       resizing is just writing that one value. Pointer Events are used rather
       than mouse events so a touch screen on the till behaves the same.
       The width is remembered per browser profile; it is a display
       preference, not business data, so localStorage is the right home.
       --------------------------------------------------------------------- */
    var CART_W_KEY = 'posCartWidth';
    var CART_W_DEFAULT = 400;
    var CART_W_MIN = 300;
    var CART_W_MAX = 640;

    function applyCartWidth(px, persist) {
        var pane = document.querySelector('.cart-pane');
        if (!pane) return;
        var max = CART_W_MAX;
        // Never let the divider eat the catalogue: leave it a usable minimum.
        if (window.innerWidth > 900) {
            max = Math.min(CART_W_MAX, window.innerWidth - 420);
        }
        var w = Math.max(CART_W_MIN, Math.min(px, Math.max(CART_W_MIN, max)));
        pane.style.setProperty('--pos-cart-w', w + 'px');
        if (persist) {
            try { localStorage.setItem(CART_W_KEY, String(w)); } catch (e) {}
        }
    }

    function initDivider() {
        var divider = $('posDivider');
        var pane = document.querySelector('.cart-pane');
        if (!divider || !pane) return;

        // Restore the remembered width, clamped to what this screen can take.
        try {
            var stored = parseInt(localStorage.getItem(CART_W_KEY), 10);
            if (stored > 0) applyCartWidth(stored, false);
        } catch (e) {}

        var dragging = false;
        var startX = 0;
        var startW = 0;

        divider.addEventListener('pointerdown', function (e) {
            dragging = true;
            startX = e.clientX;
            // The PANE's width, not the shell's - the shell is always full
            // width, so measuring it would make every drag jump to the clamp.
            startW = pane.getBoundingClientRect().width;
            divider.classList.add('is-dragging');
            document.body.classList.add('pos-resizing');
            if (divider.setPointerCapture) {
                try { divider.setPointerCapture(e.pointerId); } catch (err) {}
            }
            e.preventDefault();
        });

        divider.addEventListener('pointermove', function (e) {
            if (!dragging) return;
            applyCartWidth(startW + (e.clientX - startX), false);
        });

        function endDrag(e) {
            if (!dragging) return;
            dragging = false;
            divider.classList.remove('is-dragging');
            document.body.classList.remove('pos-resizing');
            // Persist only on release, so we store the final value once.
            applyCartWidth(pane.getBoundingClientRect().width, true);
            if (e && e.pointerId != null && divider.releasePointerCapture) {
                try { divider.releasePointerCapture(e.pointerId); } catch (err) {}
            }
        }
        divider.addEventListener('pointerup', endDrag);
        divider.addEventListener('pointercancel', endDrag);

        // Double-click resets to the default.
        divider.addEventListener('dblclick', function () {
            applyCartWidth(CART_W_DEFAULT, true);
        });

        // Keyboard: the divider is focusable, so it must be operable without
        // a pointer. Arrows nudge 16px, PageUp/PageDown by 64, Home resets.
        divider.addEventListener('keydown', function (e) {
            var cur = pane.getBoundingClientRect().width;
            var step = 16;
            if (e.key === 'ArrowLeft') { applyCartWidth(cur - step, true); e.preventDefault(); }
            else if (e.key === 'ArrowRight') { applyCartWidth(cur + step, true); e.preventDefault(); }
            else if (e.key === 'PageUp') { applyCartWidth(cur - 64, true); e.preventDefault(); }
            else if (e.key === 'PageDown') { applyCartWidth(cur + 64, true); e.preventDefault(); }
            else if (e.key === 'Home') { applyCartWidth(CART_W_DEFAULT, true); e.preventDefault(); }
        });

        // Re-clamp when the window changes: a width that fitted 1920 will not
        // fit 1280, and the catalogue must not be squeezed out of existence.
        window.addEventListener('resize', debounce(function () {
            applyCartWidth(pane.getBoundingClientRect().width, false);
        }, 120));
    }

    function init() {
        // Config-derived initial paint
        setCustomer(null);
        // Arriving from a customer page (?customer_id=N) opens on that customer.
        if (CFG.preselected_customer_id) {
            var pre = CUSTOMERS.find(function (c) {
                return String(c.id) === String(CFG.preselected_customer_id);
            });
            if (pre) setCustomer({ id: pre.id, name: pre.name, customer_id: pre.customer_id });
        }
        updateHeldBadge();
        renderCategories();
        renderCatalog();
        renderCart();

        // Toolbar
        document.querySelectorAll('[data-act]').forEach(function (b) {
            b.addEventListener('click', function () {
                var a = b.getAttribute('data-act');
                if (a === 'search') $('productSearch').focus();
                else if (a === 'transfer') openTransfer();
                else if (a === 'discount') openDiscount();
                else if (a === 'qty') openQty();
                else if (a === 'comment') openComment();
                else if (a === 'new') { if (cart.length && confirmVoid()) { clearCart(true); $('productSearch').focus(); } }
                else if (a === 'refund') openRefund();
                else if (a === 'drawer') openDrawerDialog();
                else if (a === 'save') openHeld();
                else if (a === 'pay') openPayment();
                else if (a === 'cash') openPayment('CASH');
            });
        });

        // Catalog
        $('productSearch').addEventListener('input', function (e) {
            query = e.target.value;
            page = 1;
            updateSearchClear();
            // Show the skeleton immediately, then let the debounce settle.
            // The data is already in memory, so this is about telling the
            // cashier the list is being re-filtered rather than frozen.
            showCatalogSkeleton();
            debouncedSearch();
        });

        $('catFilters').addEventListener('click', function (e) {
            var chip = e.target.closest('.cat-chip');
            if (!chip) return;
            filterCat = chip.getAttribute('data-cat');
            page = 1;
            renderCategories();
            renderCatalog();
        });

        document.querySelectorAll('.view-btn').forEach(function (b) {
            b.addEventListener('click', function () { selectView(b.getAttribute('data-view')); });
        });
        // Paint the remembered density on load.
        selectView(view);

        // The two empty states carry their own recovery action.
        $('productGrid').addEventListener('click', function (e) {
            var act = e.target.closest('[data-empty-act]');
            if (!act) return;
            var what = act.getAttribute('data-empty-act');
            if (what === 'clear-search') {
                query = '';
                $('productSearch').value = '';
                updateSearchClear();
                page = 1;
            } else if (what === 'clear-filter') {
                filterCat = '__all__';
            }
            renderCategories();
            renderCatalog();
            $('productSearch').focus();
        });

        // Numbered page buttons (delegated - the strip is re-rendered).
        $('pgNumbers').addEventListener('click', function (e) {
            var b = e.target.closest('[data-page]');
            if (!b) return;
            page = parseInt(b.getAttribute('data-page'), 10);
            renderCatalog();
        });

        // Clear-search button, visible only when there is something to clear.
        $('btnSearchClear').addEventListener('click', function () {
            query = '';
            $('productSearch').value = '';
            updateSearchClear();
            page = 1;
            renderCatalog();
            $('productSearch').focus();
        });

        // On-screen keyboard
        $('btnOsk').addEventListener('click', toggleOsk);
        $('btnOskClose').addEventListener('click', toggleOsk);
        buildOsk();

        $('productGrid').addEventListener('click', function (e) {
            var tile = e.target.closest('.p-tile');
            if (!tile) return;
            // No explicit qty: the armed F4 multiplier applies to this tap.
            addToCart(parseInt(tile.getAttribute('data-pid'), 10));
        });

        // Pager
        $('pgHome').addEventListener('click', function () { page = 1; renderCatalog(); });
        $('pgFirst').addEventListener('click', function () { page = 1; renderCatalog(); });
        $('pgPrev').addEventListener('click', function () { page--; renderCatalog(); });
        $('pgNext').addEventListener('click', function () { page++; renderCatalog(); });
        $('pgLast').addEventListener('click', function () {
            page = Math.max(1, Math.ceil(visibleProducts().length / PAGE_SIZE));
            renderCatalog();
        });

        // Cart interactions (event delegation - rows are re-rendered often)
        $('cartList').addEventListener('click', function (e) {
            var row = e.target.closest('.cart-line');
            if (!row) return;
            var idx = parseInt(row.getAttribute('data-idx'), 10);
            var qb = e.target.closest('.cl-qty-btn');
            if (qb) {
                if (qb.getAttribute('data-act') === 'inc') bumpQty(idx, 1);
                else bumpQty(idx, -1);
                return;
            }
            // The per-line Void / Restore control.
            var vb = e.target.closest('.cl-void-btn');
            if (vb) {
                toggleVoidLine(idx);
                return;
            }
            selected = (selected === idx) ? -1 : idx;
            renderCart();
        });

        $('cartList').addEventListener('dblclick', function (e) {
            var row = e.target.closest('.cart-line');
            if (!row) return;
            selected = parseInt(row.getAttribute('data-idx'), 10);
            openComment();
        });

        $('btnDelete').addEventListener('click', deleteSelected);
        $('btnVoid').addEventListener('click', function () { clearCart(false); });
        $('btnLock').addEventListener('click', lockTerminal);
        $('btnRepeat').addEventListener('click', repeatLast);
        $('btnHelp').addEventListener('click', function () { openModal('modalHelp'); });

        // Customer: the picker UI was removed; nothing to wire up here.

        // Discount
        document.querySelectorAll('.disc-quick').forEach(function (b) {
            b.addEventListener('click', function () {
                var pct = parseFloat(b.getAttribute('data-pct'));
                var line = cart[selected];
                if (!line) return;
                $('discInput').value = round2(line.original_price * (1 - pct / 100)).toFixed(2);
            });
        });

        // Modals: close buttons, scrim clicks, confirm buttons
        document.querySelectorAll('.modal-scrim').forEach(function (scrim) {
            scrim.addEventListener('mousedown', function (e) { if (e.target === scrim) closeModal(scrim.id); });
        });
        document.querySelectorAll('[data-close]').forEach(function (b) {
            b.addEventListener('click', function () { closeModal(b.getAttribute('data-close')); });
        });

        $('btnApplyDiscount').addEventListener('click', applyDiscount);
        $('btnApplyComment').addEventListener('click', applyComment);

        // Quantity (F4). Enter in the box is the same as pressing the button,
        // because the keyboard is the primary input on this terminal.
        $('btnApplyQty').addEventListener('click', applyQty);
        $('qtyInput').addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); applyQty(); }
        });
        document.querySelectorAll('.qty-quick .qc-btn').forEach(function (b) {
            b.addEventListener('click', function () {
                $('qtyInput').value = b.getAttribute('data-q');
                applyQty();
            });
        });

        // Payment
        document.querySelectorAll('.pay-method').forEach(function (b) {
            b.addEventListener('click', function () {
                if (b.classList.contains('disabled')) {
                    toast('Select a customer first for a credit sale.', 'warn');
                    return;
                }
                setPayMethod(b.getAttribute('data-method'));
            });
        });
        $('payTender').addEventListener('input', updateChange);
        $('payRef').addEventListener('input', updateChange);
        document.querySelectorAll('.qc-btn[data-amt]').forEach(function (b) {
            b.addEventListener('click', function () {
                var amt = b.getAttribute('data-amt');
                $('payTender').value = (amt === 'exact')
                    ? totals().gross.toFixed(2)
                    : amt;
                updateChange();
            });
        });
        // Numpad (delegated - the pad is static but this keeps the wiring in
        // one place and survives a re-render of the modal markup).
        $('payNumpad').addEventListener('click', function (e) {
            var k = e.target.closest('[data-nk]');
            if (!k) return;
            numpadPress(k.getAttribute('data-nk'));
        });
        $('btnConfirmPay').addEventListener('click', submitPayment);
        $('btnDone').addEventListener('click', finishSale);
        $('btnPrint').addEventListener('click', function () { window.print(); });

        // Save sale
        $('btnSaveConfirm').addEventListener('click', confirmSave);
        $('btnParkCurrent').addEventListener('click', function () {
            closeModal('modalHeld');
            saveSale();
        });

        // Transfer
        $('btnDoTransfer').addEventListener('click', doTransfer);

        // Drawer
        $('btnDrawerOpen').addEventListener('click', drawerOpenIt);
        $('btnDrawerClose').addEventListener('click', drawerCloseIt);

        // Refund
        $('btnRefundSearch').addEventListener('click', searchRefund);
        $('refundId').addEventListener('keydown', function (e) { if (e.key === 'Enter') searchRefund(); });

        // Lock
        $('lockForm').addEventListener('submit', function (e) { e.preventDefault(); unlockTerminal(); });
        $('lockPin').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key.length === 1) unlockTerminal();
        });

        // Global keys
        document.addEventListener('keydown', onKeydown);

        // Fit the workspace, then keep it fitted as the window changes.
        fitShell();
        window.addEventListener('resize', debounce(fitShell, 120));

        // The draggable order/catalogue divider.
        initDivider();

        // Focus search on load
        $('productSearch').focus();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
