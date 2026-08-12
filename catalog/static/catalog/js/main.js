/**
 * Main frontend logic for the e-shop.
 *
 * Handles:
 *   - AJAX add-to-cart with modal feedback and overstock warnings
 *   - Navbar cart badge updates
 *   - Overstock warning on product detail page
 *   - AJAX quantity update and item removal on cart detail page
 */

document.addEventListener('DOMContentLoaded', function () {
    // ===================== DOM REFERENCES =====================
    const cartModal = document.getElementById('cart-modal');
    const modalProductName = document.getElementById('modal-product-name');
    const btnContinueShopping = document.getElementById('btn-continue-shopping');
    const cartBadge = document.querySelector('.badge');
    const cartLink = document.querySelector('.btn-cart');

    // ===================== CART BADGE =====================
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

    // ===================== PRODUCT DETAIL OVERSTOCK =====================
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

    // ===================== MODAL CLOSE =====================
    if (btnContinueShopping && cartModal) {
        btnContinueShopping.addEventListener('click', function () {
            cartModal.style.display = 'none';
        });
    }

    // ===================== AJAX ADD TO CART =====================
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
                    const errorData = await response.json().catch(() => null);
                    throw { status: response.status, data: errorData };
                }
                return response.json();
            })
            .then(data => {
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

    // ===================== CART DETAIL: QUANTITY UPDATE =====================
    document.querySelectorAll('.cart-item .quantity-form').forEach(form => {
        const row = form.closest('tr');
        const qtyInput = form.querySelector('input[name="quantity"]');
        const warningWrapper = row.querySelector('.overstock-warning-wrapper');
        const checkbox = warningWrapper ? warningWrapper.querySelector('.overstock-checkbox') : null;;
        const stockValElem = warningWrapper ? warningWrapper.querySelector('.stock-val') : null;
        const qtySpan = warningWrapper ? warningWrapper.querySelector('.qty-val') : null;
        const submitBtn = form.querySelector('button[type="submit"]');
        const stockLimit = stockValElem ? parseInt(stockValElem.textContent, 10) : NaN;

        if (!qtyInput || !warningWrapper || !submitBtn) return;

        let confirmed = warningWrapper.dataset.confirmed === 'true';

        function updateWarningState() {
            const currentQty = parseInt(qtyInput.value, 10) || 0;
            const isOverstock = !isNaN(stockLimit) && currentQty > stockLimit;

            if (isOverstock && confirmed) {
                warningWrapper.style.display = 'none';
                submitBtn.disabled = false;
            } else if (isOverstock) {
                if (qtySpan) qtySpan.textContent = currentQty.toString();
                warningWrapper.style.display = 'block';
                submitBtn.disabled = !(checkbox && checkbox.checked);
            } else {
                warningWrapper.style.display = 'none';
                if (checkbox) checkbox.checked = false;
                submitBtn.disabled = false;
            }
        }

        updateWarningState();

        qtyInput.addEventListener('input', function () {
            confirmed = false;
            updateWarningState();
        });
        qtyInput.addEventListener('change', function () {
            confirmed = false;
            updateWarningState();
        });

        const hiddenConfirmed = form.querySelector('input[name="overstock_confirmed"]');

        function syncHiddenInput() {
            if (hiddenConfirmed) {
                hiddenConfirmed.value = (checkbox && checkbox.checked) ? 'true' : '';
            }
        }

        if (checkbox) {
            checkbox.addEventListener('change', function () {
                submitBtn.disabled = !this.checked;
                syncHiddenInput();
            });
        }

        syncHiddenInput();
    });

    // ===================== CART DETAIL: SUBMIT QUANTITY =====================
    document.querySelectorAll('.quantity-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const url = this.action;
            const csrfToken = this.querySelector('[name=csrfmiddlewaretoken]').value;
            const row = this.closest('tr');
            const qtyInput = this.querySelector('input[name="quantity"]');
            const oldQty = qtyInput.value;

            const formData = new FormData(this);

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            })
            .then(res => res.json().then(data => ({ status: res.status, data })))
            .then(({ status, data }) => {
                if (data.success) {
                    updateCartBadge(data.cart_total_quantity);

                    const totalGrossEl = document.querySelector('.total-gross strong');
                    if (totalGrossEl) totalGrossEl.textContent = data.total_gross + ' Kč';

                    const totalNetEl = document.querySelector('.total-net small');
                    if (totalNetEl && data.total_net) {
                        totalNetEl.textContent = 'Celkem bez DPH: ' + data.total_net + ' Kč';
                    }

                    const subtotalNetCell = row.querySelector('.cart-item-subtotal-net');
                    if (subtotalNetCell) subtotalNetCell.textContent = data.item_subtotal_net + ' Kč';

                    const subtotalGrossCell = row.querySelector('.cart-item-subtotal-gross strong');
                    if (subtotalGrossCell) subtotalGrossCell.textContent = data.item_subtotal_gross + ' Kč';

                    if (qtyInput) qtyInput.value = data.item_quantity;

                    const warningWrapper = row.querySelector('.overstock-warning-wrapper');
                    if (warningWrapper) {
                        const qtySpanEl = warningWrapper.querySelector('.qty-val');
                        const checkbox = warningWrapper.querySelector('.overstock-checkbox');
                        const rowSubmitBtn = row.querySelector('.quantity-form button[type="submit"]');

                        warningWrapper.dataset.confirmed = data.overstock_confirmed ? 'true' : 'false';

                        if (data.is_overstock && !data.overstock_confirmed) {
                            if (qtySpanEl) qtySpanEl.textContent = data.item_quantity;
                            warningWrapper.style.display = 'block';
                            if (rowSubmitBtn) rowSubmitBtn.disabled = !(checkbox && checkbox.checked);
                        } else {
                            warningWrapper.style.display = 'none';
                            if (checkbox) checkbox.checked = false;
                            if (rowSubmitBtn) rowSubmitBtn.disabled = false;
                        }
                    }

                    const titleEl = document.querySelector('.cart-title');
                    if (titleEl) titleEl.textContent = 'Košík (' + data.cart_total_quantity + ' ks)';
                } else {
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
                        if (qtyInput) qtyInput.value = oldQty;
                    } else if (data.error_field === 'overstock_confirmed') {
                        const warningWrapper = row.querySelector('.overstock-warning-wrapper');
                        if (warningWrapper) {
                            const qtySpan = warningWrapper.querySelector('.qty-val');
                            const stockSpan = warningWrapper.querySelector('.stock-val');
                            const checkbox = warningWrapper.querySelector('.overstock-checkbox');
                            const submitBtn = row.querySelector('button[type="submit"]');

                            if (qtySpan) qtySpan.textContent = qtyInput.value;
                            if (stockSpan) stockSpan.textContent = data.stock;
                            warningWrapper.style.display = 'block';
                            if (checkbox) checkbox.checked = false;
                            if (submitBtn) submitBtn.disabled = true;

                            if (checkbox) {
                                checkbox.addEventListener('change', function() {
                                    if (submitBtn) submitBtn.disabled = !this.checked;
                                });
                            }
                        }
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

    // ===================== CART DETAIL: REMOVE ITEM =====================
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

// ===================== CART DETAIL: BLOCK CHECKOUT ON UNCONFIRMED TYPED OVERSTOCK =====================
    const checkoutLink = document.getElementById('btn-checkout');
    if (checkoutLink) {
        checkoutLink.addEventListener('click', function (e) {
            const visibleWarnings = document.querySelectorAll('.overstock-warning-wrapper');
            let hasUnconfirmedTyped = false;

            visibleWarnings.forEach(function (wrapper) {
                if (window.getComputedStyle(wrapper).display !== 'none') {
                    hasUnconfirmedTyped = true;
                }
            });

            if (hasUnconfirmedTyped) {
                e.preventDefault();

                const modal = document.getElementById('cart-modal');
                const productNameEl = document.getElementById('modal-product-name');
                const standardActions = document.getElementById('modal-actions-standard');
                const alertActions = document.getElementById('modal-actions-alert');

                if (modal && productNameEl) {
                    productNameEl.innerText = 'V košíku máte zboží, které překračuje naše skladové zásoby. ' +
                        'Potvrďte formulář s podmínkami nebo odstraňte položku z košíku.';

                    if (standardActions) standardActions.style.display = 'none';
                    if (alertActions) alertActions.style.display = 'block';

                    modal.style.display = 'block';
                }
            }
        });
    }

    const modalOkBtn = document.getElementById('btn-modal-ok');
    if (modalOkBtn) {
        modalOkBtn.addEventListener('click', function () {
            const modal = document.getElementById('cart-modal');
            const standardActions = document.getElementById('modal-actions-standard');
            const alertActions = document.getElementById('modal-actions-alert');

            if (modal) {
                modal.style.display = 'none';

                if (standardActions) standardActions.style.display = 'flex';
                if (alertActions) alertActions.style.display = 'none';
            }
        });
    }
});
