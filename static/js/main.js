const root = document.documentElement;
const productsContainer = document.getElementById("products");
const themeToggle = document.getElementById("themeToggle");
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

function getCurrentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function updateThemeButtonText() {
    const currentTheme = getCurrentTheme();
    const nextTheme = currentTheme === "dark" ? "light" : "dark";

    themeToggle.setAttribute(
        "aria-label",
        nextTheme === "dark" ? "فعال‌سازی حالت تاریک" : "فعال‌سازی حالت روشن"
    );

    themeToggle.title = nextTheme === "dark"
        ? "فعال‌سازی حالت تاریک"
        : "فعال‌سازی حالت روشن";
}

if (themeToggle) {
    themeToggle.addEventListener("click", function () {
        const nextTheme = getCurrentTheme() === "dark" ? "light" : "dark";

        root.setAttribute("data-theme", nextTheme);
        localStorage.setItem("selectedTheme", nextTheme);

        updateThemeButtonText();
    });
}

systemTheme.addEventListener("change", function (event) {
    const savedTheme = localStorage.getItem("selectedTheme");

    if (savedTheme !== "dark" && savedTheme !== "light") {
        root.setAttribute("data-theme", event.matches ? "dark" : "light");
        updateThemeButtonText();
    }
});

function getFlagPath(countryCode) {
    const code = String(countryCode || "").trim().toLowerCase();

    if (!/^[a-z]{2}$/.test(code)) {
        return `${STATIC_URL}flags/unknown.svg`;
    }

    return `${STATIC_URL}flags/${code}.svg`;
}

function escapeHTML(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
}

function getProductUrl(product) {
    const apiUrl = String(product.url || "").trim();

    if (apiUrl) {
        return apiUrl;
    }

    const slug = String(product.slug || "").trim();

    if (!slug) {
        return "#";
    }

    return `/products/${encodeURIComponent(slug)}/`;
}

function normalizeDiscount(discount) {
    if (discount === null || discount === undefined || discount === "") {
        return null;
    }

    const numericValue = Number(String(discount).replace("%", "").trim());

    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return null;
    }

    return numericValue;
}

function formatDiscount(discount) {
    return new Intl.NumberFormat("fa-IR", {
        maximumFractionDigits: 2
    }).format(discount);
}

function createDiscountBadge(discount) {
    const discountValue = Number(discount);

    if (!discountValue || discountValue <= 0) {
        return "";
    }

    return `
        <div class="discount-ribbon">
            تخفیف ویژه
            <strong>${discountValue}٪</strong>
        </div>
    `;
}

function createProductCard(product) {
    const article = document.createElement("article");

    article.className = "product-card";

    const country = product.country || {};
    const countryName = country.name || "بدون نام";
    const countryCode = String(country.code || "").trim().toUpperCase();

    const productUrl = getProductUrl(product);
    const flagPath = getFlagPath(countryCode);

    const discountBadge = createDiscountBadge(product.discount);

    article.innerHTML = `
        ${discountBadge}

        <div class="product-card__header">
            <div class="country">
                <div class="country__flag">
                    <img
                        src="${flagPath}"
                        alt="پرچم ${escapeHTML(countryName)}"
                        title="${escapeHTML(countryCode || "کد کشور ثبت نشده")}"
                        onerror="this.onerror=null; this.src='${STATIC_URL}flags/unknown.svg';"
                    >
                </div>

                <div>
                    <h2 class="country__name">
                        ${escapeHTML(countryName)}
                    </h2>

                    <span class="country__code">
                        ${escapeHTML(countryCode || "N/A")}
                    </span>
                </div>
            </div>
        </div>

        <div class="product-divider"></div>

        <div class="product-card__content">
            <span class="price-label">
                محصول کشور ${escapeHTML(countryName)}
            </span>
        </div>

        <a class="product-link" href="${escapeHTML(productUrl)}">
            مشاهده جزئیات
            <span aria-hidden="true">←</span>
        </a>
    `;

    return article;
}


async function loadProducts() {
    if (!productsContainer) {
        return;
    }

    try {
        const response = await fetch("/products/", {
            headers: {
                Accept: "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`Product API request failed with status ${response.status}.`);
        }

        const products = await response.json();

        productsContainer.innerHTML = "";

        if (!Array.isArray(products) || products.length === 0) {
            productsContainer.innerHTML = `
                <div class="status-message">محصولی برای نمایش وجود ندارد.</div>
            `;
            return;
        }

        products.forEach(function (product) {
            productsContainer.appendChild(createProductCard(product));
        });
    } catch (error) {
        console.error(error);

        productsContainer.innerHTML = `
            <div class="status-message status-message--error">
                دریافت اطلاعات محصولات با خطا مواجه شد.
            </div>
        `;
    }
}

const yearElement = document.getElementById("year");

if (yearElement) {
    yearElement.textContent = new Date().getFullYear();
}

updateThemeButtonText();
loadProducts();
