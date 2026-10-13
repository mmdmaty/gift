/* =========================================
   Checkout Page
========================================= */


/* =========================================
   DOM Elements
========================================= */

const checkoutLoading =
    document.getElementById("checkoutLoading");

const checkoutError =
    document.getElementById("checkoutError");

const checkoutEmpty =
    document.getElementById("checkoutEmpty");

const checkoutContent =
    document.getElementById("checkoutContent");

const discountCodeInput =
    document.getElementById("discountCode");

const applyDiscountButton =
    document.getElementById("applyDiscountButton");

const discountFeedback =
    document.getElementById("discountFeedback");

const paymentMethodsContainer =
    document.getElementById("paymentMethods");

const orderItemsCount =
    document.getElementById("orderItemsCount");

const orderOriginalPrice =
    document.getElementById("orderOriginalPrice");

const orderExtraDiscount =
    document.getElementById("orderExtraDiscount");

const discountRow =
    document.getElementById("discountRow");

const orderTotalPrice =
    document.getElementById("orderTotalPrice");

const submitOrderButton =
    document.getElementById("submitOrderButton");

const orderFeedback =
    document.getElementById("orderFeedback");


/* =========================================
   State
========================================= */

let cartItems = [];
let appliedDiscountCode = "";
let selectedPaymentMethodId = null;


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


function getCsrfToken() {

    const input =
        document.querySelector(
            '[name="csrfmiddlewaretoken"]'
        );

    return input ? input.value : "";
}


/* =========================================
   Load Checkout
========================================= */

async function loadCheckout() {

    if (checkoutLoading) {
        checkoutLoading.classList.remove("hidden");
    }

    if (checkoutError) {
        checkoutError.classList.add("hidden");
    }

    if (checkoutEmpty) {
        checkoutEmpty.classList.add("hidden");
    }

    if (checkoutContent) {
        checkoutContent.classList.add("hidden");
    }

    try {

        const response =
            await fetch(
                window.CHECKOUT_CONFIG.cartUrl,
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

        cartItems = items;

        if (items.length === 0) {

            if (checkoutEmpty) {
                checkoutEmpty.classList.remove("hidden");
            }

            return;
        }

        if (checkoutContent) {
            checkoutContent.classList.remove("hidden");
        }

        renderOrderSummary();

        await loadPaymentMethods();

    } catch (error) {

        console.error(error);

        if (checkoutError) {
            checkoutError.classList.remove("hidden");
        }

    } finally {

        if (checkoutLoading) {
            checkoutLoading.classList.add("hidden");
        }
    }
}


/* =========================================
   Render Order Summary
========================================= */

function renderOrderSummary() {

    let totalQuantity = 0;
    let totalOriginalPrice = 0;
    let totalFinalPrice = 0;


    cartItems.forEach(item => {

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


    if (orderItemsCount) {

        orderItemsCount.textContent =
            formatPrice(totalQuantity);
    }


    if (orderOriginalPrice) {

        orderOriginalPrice.textContent =
            `${formatPrice(totalFinalPrice)} تومان`;
    }


    if (orderTotalPrice) {

        orderTotalPrice.textContent =
            `${formatPrice(totalFinalPrice)} تومان`;
    }
}


/* =========================================
   Load Payment Methods
========================================= */

async function loadPaymentMethods() {

    if (!paymentMethodsContainer) {
        return;
    }

    try {

        // روش‌های پرداخت از API خوانده می‌شوند
        // (هر روش فعال جدیدی که در ادمین اضافه شود اینجا نمایش داده می‌شود)

        const response =
            await fetch(
                window.CHECKOUT_CONFIG.paymentMethodsUrl,
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
                `Payment methods API error: ${response.status}`
            );
        }

        const data =
            await response.json();

        const paymentMethods =
            Array.isArray(data)
                ? data
                : (data.results || []);

        if (paymentMethods.length === 0) {

            paymentMethodsContainer.innerHTML = `
                <div class="payment-loading">
                    در حال حاضر روش پرداخت فعالی وجود ندارد.
                </div>
            `;

            return;
        }

        renderPaymentMethods(paymentMethods);

    } catch (error) {

        console.error(
            "Load payment methods failed:",
            error
        );

        paymentMethodsContainer.innerHTML = `
            <div class="payment-loading">
                دریافت روش‌های پرداخت با خطا مواجه شد.
            </div>
        `;
    }
}


/* =========================================
   Render Payment Methods
========================================= */

function renderPaymentMethods(methods) {

    if (!paymentMethodsContainer) {
        return;
    }

    paymentMethodsContainer.innerHTML = "";

    methods.forEach(method => {

        const element =
            document.createElement("div");

        element.className =
            "payment-method";

        element.dataset.methodId =
            method.id;

        // display_name از دیتابیس می‌آید؛ اگر خالی بود از name (کد درگاه) استفاده می‌شود
        const title =
            method.display_name || method.name;

        const description =
            method.description || "";

        const descriptionHtml =
            description
                ? `<span class="payment-description">${description}</span>`
                : "";

        element.innerHTML = `

            <div class="payment-radio"></div>

            <div class="payment-info">

                <span class="payment-name">
                    ${title}
                </span>

                ${descriptionHtml}

            </div>

        `;

        element.addEventListener(
            "click",
            () => {
                selectPaymentMethod(method.id);
            }
        );

        paymentMethodsContainer
            .appendChild(element);
    });
}


/* =========================================
   Select Payment Method
========================================= */

function selectPaymentMethod(methodId) {

    selectedPaymentMethodId = methodId;

    document
        .querySelectorAll(".payment-method")
        .forEach(
            el => {
                el.classList.remove("selected");
            }
        );

    const selected =
        document.querySelector(
            `.payment-method[data-method-id="${methodId}"]`
        );

    if (selected) {
        selected.classList.add("selected");
    }

    if (submitOrderButton) {
        submitOrderButton.disabled = false;
    }
}


/* =========================================
   Apply Discount
========================================= */

if (applyDiscountButton) {

    applyDiscountButton.addEventListener(
        "click",
        async () => {

            if (!discountCodeInput) {
                return;
            }

            const code =
                discountCodeInput.value.trim();

            if (!code) {
                return;
            }

            applyDiscountButton.disabled = true;

            applyDiscountButton.textContent =
                "در حال بررسی...";

            // فعلاً فقط کد رو ذخیره می‌کنیم
            // در زمان ثبت سفارش به API ارسال می‌شود

            appliedDiscountCode = code;

            if (discountFeedback) {

                discountFeedback.textContent =
                    "کد تخفیف در زمان ثبت سفارش اعمال می‌شود.";

                discountFeedback.classList.add("success");

                discountFeedback.classList.remove(
                    "hidden",
                    "error"
                );
            }

            setTimeout(
                () => {

                    applyDiscountButton.disabled = false;

                    applyDiscountButton.textContent =
                        "اعمال کد";

                },
                1000
            );

        }
    );
}


/* =========================================
   Submit Order
========================================= */

if (submitOrderButton) {

    submitOrderButton.addEventListener(
        "click",
        async () => {

            if (
                !selectedPaymentMethodId ||
                submitOrderButton.disabled
            ) {
                return;
            }

            submitOrderButton.disabled = true;

            submitOrderButton.textContent =
                "در حال ثبت سفارش...";

            if (orderFeedback) {
                orderFeedback.classList.add("hidden");
            }

            try {

                // ثبت سفارش

                const orderResponse =
                    await fetch(
                        window.CHECKOUT_CONFIG.orderUrl,
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
                                discount_code:
                                    appliedDiscountCode || ""
                            })
                        }
                    );

                if (!orderResponse.ok) {

                    throw new Error(
                        `Order API error: ${orderResponse.status}`
                    );
                }

                const orderData =
                    await orderResponse.json();

                // شناسه سفارشی که همین الان ساخته شد
                // (از پاسخ ثبت سفارش خوانده می‌شود)

                const orderId = orderData.id;

                if (!orderId) {

                    throw new Error(
                        "Order id not found"
                    );
                }

                // ساخت مسیر پرداخت نستد‌شده:
                // /api/shop/order/<orderId>/payment/

                const paymentUrl =
                    window.CHECKOUT_CONFIG
                        .orderPaymentUrlTemplate
                        .replace("__ORDER_ID__", orderId);

                // ایجاد پرداخت

                const paymentResponse =
                    await fetch(
                        paymentUrl,
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
                                payment_method:
                                    selectedPaymentMethodId
                            })
                        }
                    );

                if (!paymentResponse.ok) {

                    throw new Error(
                        `Payment API error: ${paymentResponse.status}`
                    );
                }

                const paymentData =
                    await paymentResponse.json();

                // ریدایرکت به صفحه پرداخت

                if (paymentData.payment_url) {

                    window.location.href =
                        paymentData.payment_url;

                } else {

                    throw new Error(
                        "Payment URL not found"
                    );
                }

            } catch (error) {

                console.error(
                    "Submit order failed:",
                    error
                );

                if (orderFeedback) {

                    orderFeedback.textContent =
                        "ثبت سفارش با خطا مواجه شد. لطفاً دوباره تلاش کنید.";

                    orderFeedback.classList.add("error");

                    orderFeedback.classList.remove(
                        "hidden",
                        "success"
                    );
                }

                submitOrderButton.disabled = false;

                submitOrderButton.textContent =
                    "ثبت سفارش و پرداخت";

            }

        }
    );
}


/* =========================================
   Initial Load
========================================= */

loadCheckout();
