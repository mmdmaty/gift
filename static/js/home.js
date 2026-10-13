/* =========================================
   Product List DOM
========================================= */

const productsGrid =
    document.getElementById("productsGrid");

const productsLoading =
    document.getElementById("productsLoading");

const productsError =
    document.getElementById("productsError");


/* =========================================
   Helpers
========================================= */

function getFlagUrl(countryCode) {

    const code =
        String(countryCode || "")
            .trim()
            .toLowerCase();

    if (!code) {
        return "";
    }

    return `${window.APP_CONFIG.flagPath}${code}.svg`;
}


// قیمت را با ارقام فارسی نمایش می‌دهیم؛ اگر formatPrice سراسری بود از آن استفاده می‌کنیم.
function displayPrice(value) {

    if (typeof window.formatPrice === "function") {
        return window.formatPrice(value);
    }

    try {
        return Number(value).toLocaleString("fa-IR");
    } catch (e) {
        return String(value);
    }
}


function escapeHtml(text) {

    return String(text == null ? "" : text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}


/* =========================================
   Skeletons (loading placeholder)
========================================= */

function renderSkeletons(count) {

    productsGrid.innerHTML = "";

    for (let i = 0; i < count; i++) {

        const card =
            document.createElement("article");

        card.className =
            "product-card product-card--skeleton";

        card.innerHTML = `
            <div class="product-country">
                <span class="skeleton skel-flag"></span>
                <div class="country-info" style="flex:1">
                    <span class="skeleton skel-line skel-line-lg"></span>
                    <span class="skeleton skel-line skel-line-sm"></span>
                </div>
            </div>

            <span class="skeleton skel-line skel-desc"></span>
            <span class="skeleton skel-line skel-desc skel-desc-2"></span>

            <div class="product-footer">
                <span class="skeleton skel-line skel-price"></span>
                <span class="skeleton skel-pill"></span>
            </div>

            <span class="skeleton skel-cta"></span>
        `;

        productsGrid.appendChild(card);
    }
}


/* =========================================
   Load Products
========================================= */

async function loadProducts() {

    try {

        // اسپینرِ سراسری را کنار می‌گذاریم و کارت‌های اسکلتی نشان می‌دهیم.
        productsLoading
            .classList
            .add("hidden");

        productsError
            .classList
            .add("hidden");

        renderSkeletons(6);


        const response =
            await fetch(
                window.APP_CONFIG.productsUrl,
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
                `Products API error: ${response.status}`
            );
        }


        const products =
            await response.json();


        renderProducts(products);


    } catch (error) {

        console.error(error);

        productsGrid.innerHTML = "";

        productsError
            .classList
            .remove("hidden");

    } finally {

        productsLoading
            .classList
            .add("hidden");
    }
}


/* =========================================
   Render Products
========================================= */

function renderProducts(products) {

    productsGrid.innerHTML = "";


    if (
        !products ||
        products.length === 0
    ) {

        productsGrid.innerHTML = `
            <div class="empty-state products-empty">
                <span class="empty-state-icon">🌐</span>
                <h3>هنوز سروری اضافه نشده است</h3>
                <p>به‌زودی سرورهای جدید در این‌جا نمایش داده می‌شوند.</p>
            </div>
        `;

        return;
    }


    products.forEach(product => {

        const country =
            product.country || {};


        const countryName =
            escapeHtml(country.name || product.name || "نامشخص");


        const countryCode =
            country.code || "";


        const description =
            escapeHtml(product.description || "");


        const discount =
            Number(product.discount || 0);


        const planCount =
            Number(product.plan_count || 0);


        const minPrice =
            product.min_price;


        const slug =
            product.slug || "";


        const flagUrl =
            getFlagUrl(countryCode);


        const detailUrl =
            (window.APP_CONFIG.detailPageUrl || "")
                .replace("__SLUG__", encodeURIComponent(slug));


        // بلوک قیمت / متادیتا
        let priceBlock;

        if (planCount > 0 && minPrice != null) {

            priceBlock = `
                <div class="price-block">
                    <span class="price-label">شروع از</span>
                    <span class="price-value">
                        ${displayPrice(minPrice)}
                        <span class="price-unit">تومان</span>
                    </span>
                </div>
            `;

        } else {

            priceBlock = `
                <div class="price-block price-block--empty">
                    <span class="price-value price-value--muted">
                        قیمت‌گذاری به‌زودی
                    </span>
                </div>
            `;
        }


        const card =
            document.createElement("article");

        card.className = "product-card";

        card.innerHTML = `

            ${
                discount > 0
                ? `<span class="discount-badge">${discount}% تخفیف</span>`
                : ""
            }

            <div class="product-country">

                ${
                    flagUrl
                    ? `<img
                            class="country-flag"
                            src="${flagUrl}"
                            alt="${countryName}"
                            loading="lazy"
                        >`
                    : `<span class="country-flag country-flag--placeholder">${countryCode ? escapeHtml(countryCode) : "?"}</span>`
                }

                <div class="country-info">
                    <h3>${countryName}</h3>
                    ${
                        countryCode
                        ? `<span class="country-code">${escapeHtml(countryCode)}</span>`
                        : ""
                    }
                </div>

            </div>

            ${
                description
                ? `<p class="product-desc">${description}</p>`
                : `<p class="product-desc product-desc--empty">سرور اختصاصی ${countryName} با پلن‌های متنوع.</p>`
            }

            <div class="product-footer">

                ${priceBlock}

                <div class="product-meta">
                    ${
                        planCount > 0
                        ? `<span class="plan-count">${displayPrice(planCount)} پلن</span>`
                        : `<span class="plan-count plan-count--empty">بدون پلن فعال</span>`
                    }
                </div>

            </div>

            <a href="${detailUrl}" class="btn btn-primary btn-block product-cta">
                مشاهده و خرید
            </a>
        `;


        productsGrid.appendChild(card);

    });
}


/* =========================================
   Initial
========================================= */

loadProducts();
