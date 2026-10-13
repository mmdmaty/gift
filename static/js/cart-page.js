/* =========================================
   Cart Page
========================================= */


/* =========================================
   DOM Elements
========================================= */

const cartPageLoading =
    document.getElementById("cartPageLoading");

const cartPageError =
    document.getElementById("cartPageError");

const cartPageEmpty =
    document.getElementById("cartPageEmpty");

const cartPageContent =
    document.getElementById("cartPageContent");

const cartItemsList =
    document.getElementById("cartItemsList");

const cartItemsCount =
    document.getElementById("cartItemsCount");

const summaryItemsCount =
    document.getElementById("summaryItemsCount");

const summaryOriginalPrice =
    document.getElementById("summaryOriginalPrice");

const summaryDiscount =
    document.getElementById("summaryDiscount");

const summaryTotalPrice =
    document.getElementById("summaryTotalPrice");


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
   Load Cart
========================================= */

async function loadCartPage() {

    if (cartPageLoading) {
        cartPageLoading.classList.remove("hidden");
    }

    if (cartPageError) {
        cartPageError.classList.add("hidden");
    }

    if (cartPageEmpty) {
        cartPageEmpty.classList.add("hidden");
    }

    if (cartPageContent) {
        cartPageContent.classList.add("hidden");
    }

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

        renderCartPage(items);

    } catch (error) {

        console.error(error);

        if (cartPageError) {
            cartPageError.classList.remove("hidden");
        }

    } finally {

        if (cartPageLoading) {
            cartPageLoading.classList.add("hidden");
        }
    }
}


/* =========================================
   Render Cart Page
========================================= */

function renderCartPage(items) {

    if (
        !items ||
        items.length === 0
    ) {

        if (cartPageEmpty) {
            cartPageEmpty.classList.remove("hidden");
        }

        return;
    }

    if (cartPageContent) {
        cartPageContent.classList.remove("hidden");
    }

    renderCartItems(items);

    renderCartSummary(items);
}


/* =========================================
   Render Cart Items
========================================= */

function renderCartItems(items) {

    if (!cartItemsList) {
        return;
    }

    cartItemsList.innerHTML = "";

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

        const totalItemPrice =
            finalPrice * quantity;

        const element =
            document.createElement("div");

        element.className =
            "cart-page-item";

        element.innerHTML = `

            <img
                src="${getFlagUrl(countryCode)}"
                class="item-flag"
                alt="${countryCode}"
            >

            <div class="item-info">

                <h3>
                    VPN ${countryCode.toUpperCase()}
                </h3>

                <p>
                    ${formatPrice(duration)}
                    روز اعتبار
                    ·
                    ${formatPrice(traffic)}
                    GB ترافیک
                </p>

            </div>

            <div class="item-quantity">

                <span class="item-quantity-label">
                    تعداد
                </span>

                <div class="quantity-controls">

                    <button
                        type="button"
                        data-action="decrease"
                        data-plan-id="${plan.id}"
                        aria-label="کاهش تعداد"
                    >
                        −
                    </button>

                    <span>
                        ${formatPrice(quantity)}
                    </span>

                    <button
                        type="button"
                        data-action="increase"
                        data-plan-id="${plan.id}"
                        aria-label="افزایش تعداد"
                    >
                        +
                    </button>

                </div>

            </div>

            <div class="item-price">

                <span class="item-price-label">
                    قیمت
                </span>

                ${
                    discount > 0
                    ? `
                        <span class="item-original-price">
                            ${formatPrice(price)}
                            تومان
                        </span>

                        <span class="item-discount-badge">
                            ${formatPrice(discount)}% تخفیف
                        </span>
                    `
                    : ""
                }

                <strong class="item-final-price">
                    ${formatPrice(totalItemPrice)}
                    تومان
                </strong>

            </div>

            <button
                type="button"
                class="item-remove"
                data-action="remove"
                data-plan-id="${plan.id}"
                aria-label="حذف محصول"
            >
                ×
            </button>

        `;


        element
            .querySelector(
                '[data-action="increase"]'
            )
            ?.addEventListener(
                "click",
                () => {
                    updateCartItemQuantity(
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
                        updateCartItemQuantity(
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


        cartItemsList
            .appendChild(element);
    });


    if (cartItemsCount) {

        cartItemsCount.textContent =
            `${formatPrice(items.length)} محصول`;
    }
}


/* =========================================
   Render Cart Summary
========================================= */

function renderCartSummary(items) {

    let totalQuantity = 0;
    let totalOriginalPrice = 0;
    let totalFinalPrice = 0;


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

        totalOriginalPrice +=
            price * quantity;

        totalFinalPrice +=
            finalPrice * quantity;
    });


    const totalDiscount =
        totalOriginalPrice - totalFinalPrice;


    if (summaryItemsCount) {

        summaryItemsCount.textContent =
            formatPrice(totalQuantity);
    }


    if (summaryOriginalPrice) {

        summaryOriginalPrice.textContent =
            `${formatPrice(totalOriginalPrice)} تومان`;
    }


    if (summaryDiscount) {

        summaryDiscount.textContent =
            `${formatPrice(totalDiscount)} تومان`;
    }


    if (summaryTotalPrice) {

        summaryTotalPrice.textContent =
            `${formatPrice(totalFinalPrice)} تومان`;
    }
}


/* =========================================
   Update Cart Item Quantity
========================================= */

async function updateCartItemQuantity(planId, newQuantity) {

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

        await loadCartPage();

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

        await loadCartPage();

    } catch (error) {

        console.error(
            "Remove cart item failed:",
            error
        );
    }
}


/* =========================================
   Initial Load
========================================= */

loadCartPage();
