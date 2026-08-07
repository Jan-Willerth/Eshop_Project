document.addEventListener('DOMContentLoaded', function () {
    const cartModal = document.getElementById('cart-modal');
    const modalProductName = document.getElementById('modal-product-name');
    const btnContinueShopping = document.getElementById('btn-continue-shopping');

    // Update navbar badge selector if needed (e.g. .cart-count or #cart-count)
    const cartCountBadge = document.querySelector('.cart-count') || document.querySelector('a[href*="cart"]');

    // ----------------------------------------------------
    // 1. Overstock Warning Logic (Product Detail Page)
    // ----------------------------------------------------
    const qtyInput = document.getElementById('id_quantity');
    const warningBox = document.getElementById('overstock-warning');

    if (qtyInput && warningBox) {
        // Read stock limit from overstock warning template data attribute or script variable context
        const submitBtn = document.getElementById('submit-btn');
        const confirmCheckbox = warningBox.querySelector('.overstock-checkbox');
        const qtySpan = warningBox.querySelector('.qty-val');

        // Retrieve stock value from warning box if embedded, fallback to data attribute
        const stockLimit = parseInt(warningBox.dataset.stock, 10);

        function checkStockLimit() {
            const currentQty = parseInt(qtyInput.value, 10) || 1;

            if (!isNaN(stockLimit) && currentQty > stockLimit) {
                if (qtySpan) qtySpan.textContent = currentQty.toString();
                warningBox.style.display = 'block';
                if (confirmCheckbox && submitBtn) {
                    submitBtn.disabled = !confirmCheckbox.checked;
                }
            } else {
                warningBox.style.display = 'none';
                if (confirmCheckbox) confirmCheckbox.checked = false;
                if (submitBtn) submitBtn.disabled = false;
            }
        }

        qtyInput.addEventListener('input', checkStockLimit);
        qtyInput.addEventListener('change', checkStockLimit);
        if (confirmCheckbox) {
            confirmCheckbox.addEventListener('change', checkStockLimit);
        }
    }

    // ----------------------------------------------------
    // 2. Modal Close Event
    // ----------------------------------------------------
    if (btnContinueShopping && cartModal) {
        btnContinueShopping.addEventListener('click', function () {
            cartModal.style.display = 'none';
        });
    }

    // ----------------------------------------------------
    // 3. AJAX Add to Cart Handler
    // ----------------------------------------------------
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
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                if (data.success || data.message) {
                    // Update modal message
                    if (modalProductName) {
                        modalProductName.textContent = data.message || `"${data.product_name}" was added to cart.`;
                    }

                    // Update navbar cart count
                    if (data.total_items !== undefined && cartCountBadge) {
                        cartCountBadge.textContent = data.total_items;
                    }

                    // Show modal
                    if (cartModal) {
                        cartModal.style.display = 'flex';
                    }
                } else if (data.error) {
                    alert(data.error);
                }
            })
            .catch(error => {
                console.error('AJAX Error:', error);
                // Fallback to regular HTTP POST if fetch fails
                form.submit();
            });
        }
    });
});
