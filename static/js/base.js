/* =========================================
   DOM
========================================= */

const themeToggle =
    document.getElementById("themeToggle");

const cartButton =
    document.getElementById("cartButton");

const cartSidebar =
    document.getElementById("cartSidebar");

const cartOverlay =
    document.getElementById("cartOverlay");

const closeCart =
    document.getElementById("closeCart");

const cartItemsContainer =
    document.getElementById("cartItems");

const cartLoading =
    document.getElementById("cartLoading");

const cartEmpty =
    document.getElementById("cartEmpty");

const cartCount =
    document.getElementById("cartCount");

const cartItemsTitle =
    document.getElementById("cartItemsTitle");

const cartTotal =
    document.getElementById("cartTotal");


/* =========================================
   Helpers
========================================= */

function formatPrice(price) {

    return new Intl.NumberFormat("fa-IR")
        .format(Number(price || 0));
}


function calculateDiscountedPrice(
    price,
    discount
) {

    const original =
        Number(price || 0);

    const percent =
        Number(discount || 0);

    return Math.round(
        original *
        (100 - percent) /
        100
    );
}


function getFlagUrl(code) {

    const countryCode =
        String(code || "")
            .trim()
            .toLowerCase();

    if (!countryCode) {
        return "";
    }

    return `${window.APP_CONFIG.flagPath}${countryCode}.svg`;
}


function getCsrfToken() {

    const input =
        document.querySelector(
            '[name="csrfmiddlewaretoken"]'
        );

    return input ? input.value : "";
}


/* =========================================
   Theme
========================================= */

function loadTheme() {

    const theme =
        localStorage.getItem("theme");

    if (theme === "dark") {

        document.documentElement
            .classList
            .add("dark");

        if (themeToggle) {
            themeToggle.textContent = "🌙";
        }

    } else {

        document.documentElement
            .classList
            .remove("dark");

        if (themeToggle) {
            themeToggle.textContent = "☀️";
        }
    }
}


function toggleTheme() {

    const isDark =
        document.documentElement
            .classList
            .toggle("dark");

    localStorage.setItem(
        "theme",
        isDark ? "dark" : "light"
    );

    if (themeToggle) {
        themeToggle.textContent =
            isDark ? "🌙" : "☀️";
    }
}


if (themeToggle) {

    themeToggle.addEventListener(
        "click",
        toggleTheme
    );
}


loadTheme();


/* =========================================
   Cart Open / Close
========================================= */

function openCart() {

    if (!cartSidebar) {
        return;
    }

    cartSidebar.classList.add("active");

    if (cartOverlay) {
        cartOverlay.classList.add("active");
    }

    document.body.style.overflow = "hidden";
}


function closeCartSidebar() {

    if (cartSidebar) {
        cartSidebar.classList.remove("active");
    }

    if (cartOverlay) {
        cartOverlay.classList.remove("active");
    }

    document.body.style.overflow = "";
}


if (cartButton) {

    cartButton.addEventListener(
        "click",
        openCart
    );
}


if (closeCart) {

    closeCart.addEventListener(
        "click",
        closeCartSidebar
    );
}


if (cartOverlay) {

    cartOverlay.addEventListener(
        "click",
        closeCartSidebar
    );
}


document.addEventListener(
    "keydown",
    event => {

        if (event.key === "Escape") {
            closeCartSidebar();
        }

    }
);


/* =========================================
   Load Cart
========================================= */

async function loadCart() {

    if (!cartItemsContainer) {
        return;
    }

    if (cartLoading) {
        cartLoading.classList.remove("hidden");
    }

    if (cartEmpty) {
        cartEmpty.classList.add("hidden");
    }

    cartItemsContainer.innerHTML = "";

    try {

        const response =
            await fetch(
                window.APP_CONFIG.cartUrl,
                {
                    method: "GET",

                    headers: {
                        "Accept":
                            "application/json"
                    }
                }
            );

        if (!response.ok) {

            throw new Error(
                `Cart API error: ${response.status}`
            );
        }

        const data =
            await response.json();

        const items =
            Array.isArray(data)
                ? data
                : (
                    data.results ||
                    []
                );

        renderCart(items);

    } catch (error) {

        console.error(error);

        cartItemsContainer.innerHTML = `
            <div class="cart-empty">
                <p>
                    دریافت سبد خرید با خطا مواجه شد.
                </p>
            </div>
        `;

    } finally {

        if (cartLoading) {
            cartLoading.classList.add("hidden");
        }
    }
}


/* =========================================
   Render Cart
========================================= */

function renderCart(items) {

    cartItemsContainer.innerHTML = "";

    if (
        !items ||
        items.length === 0
    ) {

        if (cartEmpty) {
            cartEmpty.classList.remove("hidden");
        }

        updateCartSummary([]);

        return;
    }

    if (cartEmpty) {
        cartEmpty.classList.add("hidden");
    }


    items.forEach(item => {

        const plan =
            item.plan || {};

        const countryCode =
            plan.country_code || "";

        const duration =
            Number(plan.duration || 0);

        const traffic =
            Number(plan.traffic || 0);

        const price =
            Number(plan.price || 0);

        const discount =
            Number(plan.discount || 0);

        const quantity =
            Number(item.quantity || 1);

        const finalPrice =
            calculateDiscountedPrice(
                price,
                discount
            );

        const element =
            document.createElement("div");

        element.className =
            "cart-item";

        element.innerHTML = `

            <div class="cart-item-top">

                <img
                    src="${getFlagUrl(countryCode)}"
                    class="cart-item-flag"
                    alt="${countryCode}"
                >

                <div class="cart-item-info">

                    <strong>
                        VPN ${countryCode}
                    </strong>

                    <small>
                        ${duration}
                        روز
                        ·
                        ${traffic}
                        GB
                    </small>

                </div>

            </div>


            <div class="cart-price-section">

                ${
                    discount > 0
                    ? `
                        <span class="cart-original-price">
                            ${formatPrice(price)}
                            تومان
                        </span>

                        <span class="cart-discount">
                            ${discount}%
                            تخفیف
                        </span>
                    `
                    : ""
                }

                <div class="cart-item-price">

                    ${formatPrice(finalPrice)}
                    تومان

                </div>

            </div>


            <div class="cart-item-bottom">

                <div class="quantity-control">

                    <button
                        type="button"
                        data-action="decrease"
                        data-id="${plan.id}"
                    >
                        −
                    </button>

                    <span>
                        ${quantity}
                    </span>

                    <button
                        type="button"
                        data-action="increase"
                        data-id="${plan.id}"
                    >
                        +
                    </button>

                </div>


                <button
                    type="button"
                    class="remove-item"
                    data-action="remove"
                    data-id="${plan.id}"
                >
                    حذف
                </button>

            </div>
        `;


        element
            .querySelector(
                '[data-action="increase"]'
            )
            ?.addEventListener(
                "click",
                () => {
                    updateCartItem(
                        plan.id,
                        quantity + 1
                    );
                }
            );


        element
            .querySelector(
                '[data-action="decrease"]'
            )
            ?.addEventListener(
                "click",
                () => {
                    if (quantity <= 1) {
                        removeCartItem(plan.id);
                    } else {
                        updateCartItem(
                            plan.id,
                            quantity - 1
                        );
                    }
                }
            );


        element
            .querySelector(
                '[data-action="remove"]'
            )
            ?.addEventListener(
                "click",
                () => {
                    removeCartItem(plan.id);
                }
            );


        cartItemsContainer
            .appendChild(element);
    });


    updateCartSummary(items);
}


/* =========================================
   Cart Summary
========================================= */

function updateCartSummary(items) {

    let totalQuantity = 0;
    let totalPrice = 0;


    items.forEach(item => {

        const plan =
            item.plan || {};

        const price =
            Number(plan.price || 0);

        const discount =
            Number(plan.discount || 0);

        const quantity =
            Number(item.quantity || 1);

        const finalPrice =
            calculateDiscountedPrice(
                price,
                discount
            );

        totalQuantity += quantity;

        totalPrice +=
            finalPrice * quantity;
    });


    if (cartCount) {

        cartCount.textContent =
            formatPrice(totalQuantity);
    }


    if (cartItemsTitle) {

        cartItemsTitle.textContent =
            `${formatPrice(totalQuantity)} محصول`;
    }


    if (cartTotal) {

        cartTotal.textContent =
            `${formatPrice(totalPrice)} تومان`;
    }
}


/* =========================================
   Update Cart Item
========================================= */

async function updateCartItem(planId, newQuantity) {

    try {

        const response =
            await fetch(
                `${window.APP_CONFIG.cartUrl}${planId}/`,
                {
                    method: "PATCH",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken(),

                        "Accept":
                            "application/json"
                    },

                    body: JSON.stringify({
                        quantity: newQuantity
                    })
                }
            );

        if (!response.ok) {

            throw new Error(
                `Update cart error: ${response.status}`
            );
        }

        await loadCart();

    } catch (error) {

        console.error(
            "Update cart item failed:",
            error
        );
    }
}


/* =========================================
   Remove Cart Item
========================================= */

async function removeCartItem(planId) {

    try {

        const response =
            await fetch(
                `${window.APP_CONFIG.cartUrl}${planId}/`,
                {
                    method: "DELETE",

                    headers: {
                        "Accept":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken()
                    }
                }
            );

        if (
            !response.ok &&
            response.status !== 204
        ) {

            throw new Error(
                `Remove cart error: ${response.status}`
            );
        }

        await loadCart();

    } catch (error) {

        console.error(
            "Remove cart item failed:",
            error
        );
    }
}


/* =========================================
   Add to Cart (global)
========================================= */

async function addToCart(planId, quantity) {

    if (!planId) {
        console.error("No plan ID provided.");
        return;
    }

    try {

        const response =
            await fetch(
                window.APP_CONFIG.cartUrl,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken(),

                        "Accept":
                            "application/json"
                    },

                    body: JSON.stringify({
                        plan: planId,
                        quantity: quantity || 1
                    })
                }
            );

        if (!response.ok) {

            throw new Error(
                `Add to cart error: ${response.status}`
            );
        }

        await loadCart();

        openCart();

        return true;

    } catch (error) {

        console.error(
            "Add to cart failed:",
            error
        );

        return false;
    }
}


/* =========================================
   Initial Cart
========================================= */

loadCart();