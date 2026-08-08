/**
 * Main frontend logic for the e-shop.
 *
 * Handles:
 *   - AJAX add-to-cart with modal feedback (overstock warnings)
 *   - Navbar cart badge updates
 *   - Overstock warning on product detail page
 *   - AJAX quantity update and item removal on cart detail page
 */

document.addEventListener('DOMContentLoaded', function () {
    // ==============================
    // 1. DOM element references
    // ==============================
    const cartModal = document.getElementById('cart-modal');
    const modalProductName = document.getElementById('modal-product-name');
    const btnContinueShopping = document.getElementById('btn-continue-shopping');
    const cartBadge = document.querySelector('.badge');
    const cartLink = document.querySelector('.btn-cart');

    // ==============================
    // 2. Helper: update cart badge
    // ==============================
    function updateCartBadge(count) {
        if (cartBadge) {
            if (count > 0) {
                cartBadge.textContent = count;
                cartBadge.style.display = 'inline';
            } else {
                cartBadge.style.display = 'none';
            }
        } else if (count > 0 && cartLink) {
            const newBadge = document.createElement('span');
            newBadge.className = 'badge';
            newBadge.textContent = count;
            cartLink.appendChild(newBadge);
        }
    }

    // ==============================
    // 3. Overstock warning on product detail page
    // ==============================
    const qtyInput = document.getElementById('id_quantity');
    const overstockWarningBox = document.getElementById('overstock-warning');

    if (qtyInput && overstockWarningBox) {
        const submitBtn = document.getElementById('submit-btn');
        const confirmCheckbox = overstockWarningBox.querySelector('.overstock-checkbox');
        const qtySpan = overstockWarningBox.querySelector('.qty-val');
        const stockValElem = overstockWarningBox.querySelector('.stock-val');
        const stockLimit = stockValElem ? parseInt(stockValElem.textContent, 10) : NaN;

        function checkStockLimit() {
            const currentQty = parseInt(qtyInput.value, 10) || 1;

            if (currentQty > 99) {
                    overstockWarningBox.style.display = 'none';
                    submitBtn.disabled = false;
                    return;
                }
            if (!isNaN(stockLimit) && currentQty > stockLimit) {
                if (qtySpan) qtySpan.textContent = currentQty.toString();
                overstockWarningBox.style.display = 'block';
                if (confirmCheckbox && submitBtn) {
                    submitBtn.disabled = !confirmCheckbox.checked;
                }
            } else {
                overstockWarningBox.style.display = 'none';
                if (confirmCheckbox) confirmCheckbox.checked = false;
                if (submitBtn) submitBtn.disabled = false;
            }
        }

        qtyInput.addEventListener('input', checkStockLimit);
        qtyInput.addEventListener('change', checkStockLimit);
        if (confirmCheckbox) {
            confirmCheckbox.addEventListener('change', checkStockLimit);
        }
        checkStockLimit();
    }

    // ==============================
    // 4. Modal close button
    // ==============================
    if (btnContinueShopping && cartModal) {
        btnContinueShopping.addEventListener('click', function () {
            cartModal.style.display = 'none';
        });
    }

        // ==============================
    // 5. AJAX Add to Cart (global listener)
    // ==============================
    document.addEventListener('submit', function (e) {
        const form = e.target;

        if (form.classList.contains('add-to-cart-form')) {
            e.preventDefault();

            const formData = new FormData(form);
            const actionUrl = form.action;

            fetch(actionUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(async response => {
                if (!response.ok) {
                    // Pokus o parsování JSON i z chybové odpovědi
                    const errorData = await response.json().catch(() => null);
                    throw { status: response.status, data: errorData };
                }
                return response.json();
            })
            .then(data => {
                // Úspěch
                if (modalProductName) {
                    modalProductName.textContent = data.message || `"${data.product_name}" byl přidán do košíku.`;
                }

                updateCartBadge(data.cart_total_quantity);

                if (cartModal) {
                    cartModal.style.display = 'flex';
                }
            })
            .catch(error => {
                console.error('AJAX Add to Cart error:', error);

                if (error && error.data && error.data.quote_url) {
                    // Over limit – upravit modál
                    if (modalProductName) {
                        modalProductName.innerHTML = error.data.over_limit_message || error.data.error;
                    }
                    const goToCartBtn = document.getElementById('btn-go-to-cart');
                    if (goToCartBtn) {
                        goToCartBtn.textContent = 'Přejít na formulář poptávky';
                        goToCartBtn.href = error.data.quote_url;
                    }
                    if (cartModal) {
                        cartModal.style.display = 'flex';
                    }
                } else {
                    alert((error && error.data && error.data.error) || 'Došlo k chybě.');
                }
            });
        }
    });

    // ==============================
    // 6. Cart detail page: quantity update (AJAX)
    // ==============================
    document.querySelectorAll('.quantity-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const formData = new FormData(this);
            const url = this.action;
            const csrfToken = this.querySelector('[name=csrfmiddlewaretoken]').value;
            const row = this.closest('tr');

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            })
            .then(res => res.ok ? res.json() : Promise.reject(res))
            .then(data => {
                if (data.success) {
                    updateCartBadge(data.cart_total_quantity);

                    const totalGrossEl = document.querySelector('.total-gross strong');
                    if (totalGrossEl) totalGrossEl.textContent = data.total_gross + ' Kč';

                    const totalNetEl = document.querySelector('.total-net small');
                    if (totalNetEl && data.total_net) {
                        totalNetEl.textContent = 'Celkem bez DPH: ' + data.total_net + ' Kč';
                    }

                    const subtotalCell = row.querySelector('.cart-item-price strong');
                    if (subtotalCell) subtotalCell.textContent = data.item_subtotal + ' Kč';

                    const qtyInputEl = row.querySelector('input[name="quantity"]');
                    if (qtyInputEl) qtyInputEl.value = data.item_quantity;

                    const warningWrapper = row.querySelector('.overstock-warning-wrapper');
                    if (warningWrapper) {
                        const qtySpanEl = warningWrapper.querySelector('.qty-val');
                        const checkbox = warningWrapper.querySelector('.overstock-checkbox');
                        if (data.is_overstock) {
                            if (qtySpanEl) qtySpanEl.textContent = data.quantity || data.item_quantity;
                            warningWrapper.style.display = 'block';
                        } else {
                            warningWrapper.style.display = 'none';
                            if (checkbox) checkbox.checked = false;
                        }
                    }

                    const titleEl = document.querySelector('.cart-title');
                    if (titleEl) titleEl.textContent = 'Košík (' + data.cart_total_quantity + ' ks)';
                 } else {
                    // Chyba – pokud je quote_url, zobrazit modál
                    if (data.quote_url) {
                        if (modalProductName) {
                            modalProductName.innerHTML = data.over_limit_message || data.error;
                        }
                        const goToCartBtn = document.getElementById('btn-go-to-cart');
                        if (goToCartBtn) {
                            goToCartBtn.textContent = 'Přejít na formulář poptávky';
                            goToCartBtn.href = data.quote_url;
                        }
                        if (cartModal) {
                            cartModal.style.display = 'flex';
                        }
                        // Vrátit input na původní hodnotu (aby nezůstalo >99)
                        const originalQty = this.querySelector('input[name="quantity"]').defaultValue;
                        this.querySelector('input[name="quantity"]').value = originalQty;
                    } else {
                        alert('Chyba: ' + (data.error || 'Nepodařilo se aktualizovat košík.'));
                    }
                }
            })
            .catch(err => {
                console.error('AJAX update error:', err);
                form.submit();
            });
        });
    });

    // ==============================
    // 7. Cart detail page: remove item (AJAX)
    // ==============================
    document.querySelectorAll('.remove-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const url = this.action;
            const csrfToken = this.querySelector('[name=csrfmiddlewaretoken]').value;
            const row = this.closest('tr');

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                },
            })
            .then(res => res.ok ? res.json() : Promise.reject(res))
            .then(data => {
                if (data.success) {
                    row.remove();
                    updateCartBadge(data.cart_total_quantity);

                    const totalGrossEl = document.querySelector('.total-gross strong');
                    if (totalGrossEl) totalGrossEl.textContent = data.total_gross + ' Kč';

                    const totalNetEl = document.querySelector('.total-net small');
                    if (totalNetEl && data.total_net) {
                        totalNetEl.textContent = 'Celkem bez DPH: ' + data.total_net + ' Kč';
                    }

                    const titleEl = document.querySelector('.cart-title');
                    if (titleEl) titleEl.textContent = 'Košík (' + data.cart_total_quantity + ' ks)';

                    const tbody = document.querySelector('.cart-table tbody');
                    if (tbody && tbody.children.length === 0) {
                        location.reload();
                    }
                } else {
                    alert('Chyba: ' + (data.error || 'Nepodařilo se odstranit položku.'));
                }
            })
            .catch(err => {
                console.error('AJAX remove error:', err);
                form.submit();
            });
        });
    });
});
