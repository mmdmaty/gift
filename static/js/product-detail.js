/* =========================================
   Product Detail
========================================= */


/* =========================================
   DOM
========================================= */

const plansGrid =
    document.getElementById("plansGrid");

const productLoading =
    document.getElementById("productLoading");

const productError =
    document.getElementById("productError");

const productTabsSection =
    document.getElementById("productTabsSection");

const commentsList =
    document.getElementById("commentsList");

const generalDetailsList =
    document.getElementById("generalDetails");

const productDescription =
    document.getElementById("productDescription");

const tabPanels = {
    plans:
        document.getElementById("plansTab"),

    comments:
        document.getElementById("commentsTab"),

    description:
        document.getElementById("descriptionTab")
};

const showAllComments =
    document.getElementById("showAllComments");


/* =========================================
   State
========================================= */

let productData = null;

let selectedPlanIndex = null;


/* =========================================
   Helpers
========================================= */

function formatPrice(price) {

    return new Intl.NumberFormat("fa-IR").format(
        Number(price || 0)
    );

}


function calculateDiscountedPrice(
    price,
    discount
) {

    const originalPrice =
        Number(price || 0);

    const discountPercent =
        Number(discount || 0);

    if (!discountPercent) {
        return originalPrice;
    }

    return Math.round(
        originalPrice *
        (100 - discountPercent) /
        100
    );

}


function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


/* =========================================
   Loading / Error
========================================= */

function showError(message = null) {

    if (!productError) {
        return;
    }

    if (message) {
        productError.textContent = message;
    }

    productError.classList.remove("hidden");

}


function hideError() {

    if (!productError) {
        return;
    }

    productError.classList.add("hidden");

}


/* =========================================
   Load Product
========================================= */

async function loadProduct() {

    try {

        if (productLoading) {
            productLoading.classList.remove("hidden");
        }

        hideError();


        console.log(
            "Loading product:",
            PRODUCT_CONFIG.detailUrl
        );


        const response =
            await fetch(
                PRODUCT_CONFIG.detailUrl,
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
                `Product API error: ${response.status}`
            );

        }


        const product =
            await response.json();


        console.log(
            "Product response:",
            product
        );


        /*
         * کل response را نگه می‌داریم.
         *
         * تب‌ها از همین object استفاده می‌کنند
         * و هیچ request دیگری ارسال نمی‌شود.
         */

        productData = product;


        /*
         * Render plans
         */

        renderPlans(
            product.plans || []
        );


        /*
         * Render comments
         */

        renderComments(
            product.comments || []
        );


        /*
         * Render general details
         */

        renderGeneralDetails(
            product.general_details || {}
        );


        /*
         * Render description
         */

        renderDescription(
            product.description || ""
        );


        /*
         * تب‌ها را فعال می‌کنیم
         */

        setupTabs();


        /*
         * بخش تب‌ها را نمایان می‌کنیم
         */

        if (productTabsSection) {
            productTabsSection.classList.remove("hidden");
        }


    } catch (error) {

        console.error(
            "Product detail error:",
            error
        );

        showError(
            "دریافت اطلاعات سرویس با خطا مواجه شد."
        );


    } finally {

        if (productLoading) {
            productLoading.classList.add("hidden");
        }

    }

}


/* =========================================
   Render Plans
========================================= */

function renderPlans(plans) {

    if (!plansGrid) {
        return;
    }


    plansGrid.innerHTML = "";


    if (!plans || plans.length === 0) {

        plansGrid.innerHTML = `
            <div class="no-plans">
                پلنی برای این سرویس وجود ندارد.
            </div>
        `;

        return;

    }


    plans.forEach(
        (plan, index) => {

            const duration =
                Number(
                    plan.duration || 0
                );


            const traffic =
                Number(
                    plan.traffic || 0
                );


            const price =
                Number(
                    plan.price || 0
                );


            const discount =
                Number(
                    plan.discount || 0
                );


            const finalPrice =
                calculateDiscountedPrice(
                    price,
                    discount
                );


            /*
             * فقط اگر بیشتر از یک پلن داشته باشیم،
             * پلن دوم محبوب‌ترین می‌شود.
             */

            const isFeatured =
                plans.length > 1 &&
                index === 1;


            const card =
                document.createElement(
                    "article"
                );


            card.className =
                "plan-card";


            if (isFeatured) {

                card.classList.add(
                    "featured"
                );

            }


            card.dataset.planIndex =
                index;


            card.innerHTML = `

                ${
                    isFeatured
                    ? `
                        <div class="popular-badge">
                            <span class="popular-icon">
                                ★
                            </span>

                            <span>
                                محبوب‌ترین
                            </span>
                        </div>
                    `
                    : ""
                }


                <div class="plan-card-header">

                    <h3>
                        پلن ${formatPrice(index + 1)}
                    </h3>

                </div>


                <div class="plan-content">


                    <div class="plan-features">

                        <div class="plan-feature">

                            <span class="feature-icon">
                                ◉
                            </span>

                            <span>
                                ${formatPrice(duration)}
                                روز اعتبار
                            </span>

                        </div>


                        <div class="plan-feature">

                            <span class="feature-icon">
                                ◉
                            </span>

                            <span>
                                ${formatPrice(traffic)}
                                GB ترافیک
                            </span>

                        </div>


                        <div class="plan-feature">

                            <span class="feature-icon">
                                ✓
                            </span>

                            <span>
                                دسترسی به سرویس VPN
                            </span>

                        </div>

                    </div>


                    <div class="plan-price-box">

                        ${
                            discount > 0
                            ? `

                                <span class="discount-label">
                                    تخفیف
                                </span>

                                <strong class="discount-value">
                                    ${formatPrice(discount)}٪
                                </strong>

                                <span class="original-price">
                                    ${formatPrice(price)}
                                    تومان
                                </span>

                            `
                            : `

                                <span class="discount-label">
                                    قیمت
                                </span>

                            `
                        }


                        <strong class="final-price">
                            ${formatPrice(finalPrice)}
                            تومان
                        </strong>

                    </div>

                </div>


                <div
                    class="select-plan-button"
                    data-plan-index="${index}"
                    role="button"
                    tabindex="0"
                >
                    افزودن به سبد خرید
                </div>

            `;


            plansGrid.appendChild(
                card
            );

        }
    );


    setupPlanSelection();

}


/* =========================================
   Plan Selection
========================================= */

function setupPlanSelection() {

    if (!plansGrid) {
        return;
    }


    const buttons =
        plansGrid.querySelectorAll(
            ".select-plan-button"
        );


    buttons.forEach(
        button => {

            button.addEventListener(
                "click",
                async (event) => {

                    event.stopPropagation();

                    if (button.disabled || button.getAttribute('aria-disabled') === 'true') {
                        return;
                    }


                    const index =
                        Number(
                            button.dataset.planIndex
                        );


                    const plan =
                        productData &&
                        productData.plans
                        ? productData.plans[index]
                        : null;


                    if (
                        !plan ||
                        !plan.id
                    ) {

                        console.error(
                            "Plan id is not available."
                        );

                        return;

                    }


                    /*
                     * کارت انتخاب‌شده را مشخص می‌کنیم.
                     */

                    plansGrid
                        .querySelectorAll(
                            ".plan-card"
                        )
                        .forEach(
                            card => {

                                card.classList.remove(
                                    "selected"
                                );

                            }
                        );


                    button
                        .closest(".plan-card")
                        ?.classList.add(
                            "selected"
                        );


                    selectedPlanIndex =
                        index;


                    /*
                     * افزودن پلن به سبد خرید
                     * از طریق API.
                     */

                    button.setAttribute('aria-disabled', 'true');

                    const originalLabel =
                        button.textContent;

                    button.textContent =
                        "در حال افزودن...";


                    const added =
                        await addToCart(
                            plan.id,
                            1
                        );


                    button.classList.add(
                        added
                        ? "added"
                        : "error"
                    );


                    button.textContent =
                        added
                        ? "به سبد اضافه شد ✓"
                        : "خطا در افزودن!";


                    setTimeout(
                        () => {

                            button.textContent =
                                originalLabel;

                            button.removeAttribute('aria-disabled');

                            button.classList.remove(
                                "added",
                                "error"
                            );

                        },
                        1600
                    );

                }
            );

        }
    );

}


/* =========================================
   Render Comments
========================================= */

function renderComments(comments) {

    /*
     * هیچ‌وقت روی عنصر null
     * classList اجرا نمی‌کنیم.
     */

    if (!commentsList) {
        console.warn(
            "commentsList element not found."
        );

        return;
    }


    commentsList.innerHTML = "";


    if (
        !comments ||
        comments.length === 0
    ) {

        commentsList.innerHTML = `

            <div class="no-comments">

                هنوز نظری ثبت نشده است.

            </div>

        `;

    } else {

        comments.forEach(
            comment => {

                const user =
                    comment.user || "کاربر";


                const text =
                    comment.text || "";


                const score =
                    Math.max(
                        0,
                        Math.min(
                            5,
                            Number(
                                comment.score || 0
                            )
                        )
                    );


                const stars =
                    "★".repeat(score) +
                    "☆".repeat(5 - score);


                const firstLetter =
                    String(user)
                        .charAt(0);


                const element =
                    document.createElement(
                        "article"
                    );


                element.className =
                    "comment-card";


                element.innerHTML = `

                    <div class="comment-user">

                        <div class="comment-avatar">
                            ${escapeHtml(firstLetter)}
                        </div>

                        <strong>
                            ${escapeHtml(user)}
                        </strong>

                    </div>


                    <div class="comment-content">

                        <div class="comment-stars">
                            ${stars}
                        </div>

                        <p>
                            ${escapeHtml(text)}
                        </p>

                    </div>

                `;


                commentsList.appendChild(
                    element
                );

            }
        );

    }


}


/* =========================================
   Render General Details
========================================= */

function renderGeneralDetails(
    generalDetails
) {

    if (!generalDetailsList) {

        console.warn(
            "generalDetailsList element not found."
        );

        return;

    }


    generalDetailsList.innerHTML = "";


    /*
     * API فعلی:
     *
     * "general_details": {
     *     "Datacenter": "Aeza"
     * }
     *
     */


    if (
        !generalDetails ||
        typeof generalDetails !== "object" ||
        Object.keys(generalDetails).length === 0
    ) {

        generalDetailsList.innerHTML = `

            <div class="no-details">

                مشخصات تکمیلی برای این سرویس ثبت نشده است.

            </div>

        `;

        return;

    }


    Object.entries(
        generalDetails
    ).forEach(
        ([key, value]) => {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "general-detail-item";


            item.innerHTML = `

                <span class="detail-key">
                    ${escapeHtml(key)}
                </span>

                <span class="detail-value">
                    ${escapeHtml(value)}
                </span>

            `;


            generalDetailsList.appendChild(
                item
            );

        }
    );

}


/* =========================================
   Render Description
========================================= */

function renderDescription(
    description
) {

    if (!productDescription) {
        return;
    }


    if (
        !description ||
        !String(description).trim()
    ) {

        productDescription.innerHTML = `

            <div class="no-description">

                توضیحات تکمیلی برای این سرویس ثبت نشده است.

            </div>

        `;

        return;

    }


    /*
     * textContent برای جلوگیری از
     * تزریق HTML ناخواسته.
     */

    productDescription.textContent =
        description;

}


/* =========================================
   Tabs
========================================= */

function setupTabs() {

    /*
     * دکمه‌های تب با data-tab
     * به پنل‌های محتوا وصل می‌شوند.
     */

    const buttons =
        document.querySelectorAll(
            ".product-tab"
        );


    if (buttons.length === 0) {

        console.warn(
            "Tab buttons not found."
        );

        return;

    }


    buttons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    activateTab(
                        button.dataset.tab
                    );

                }
            );

        }
    );

}


/* =========================================
   Activate Tab
========================================= */

function activateTab(
    tabName
) {

    /*
     * دکمه‌ی تب فعال
     */

    document
        .querySelectorAll(
            ".product-tab"
        )
        .forEach(
            button => {

                button.classList.toggle(
                    "active",
                    button.dataset.tab === tabName
                );

            }
        );


    /*
     * پنل فعال
     */

    Object.entries(
        tabPanels
    ).forEach(
        ([name, panel]) => {

            if (panel) {

                panel.classList.toggle(
                    "active",
                    name === tabName
                );

            }

        }
    );

}


/* =========================================
   Rating
========================================= */

const ratingStars =
    document.getElementById(
        "ratingStars"
    );


const commentScore =
    document.getElementById(
        "commentScore"
    );


if (
    ratingStars &&
    commentScore
) {

    const stars =
        ratingStars.querySelectorAll(
            "button"
        );


    stars.forEach(
        star => {

            star.addEventListener(
                "click",
                () => {

                    const score =
                        Number(
                            star.dataset.score
                        );


                    commentScore.value =
                        score;


                    stars.forEach(
                        item => {

                            const itemScore =
                                Number(
                                    item.dataset.score
                                );


                            item.textContent =
                                itemScore <= score
                                    ? "★"
                                    : "☆";

                        }
                    );

                }
            );

        }
    );

}


/* =========================================
   Comment Form
========================================= */

const commentForm =
    document.getElementById(
        "commentForm"
    );


const commentFeedback =
    document.getElementById(
        "commentFeedback"
    );


if (commentForm) {

    commentForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const textElement =
                document.getElementById(
                    "commentText"
                );


            if (!textElement || !commentScore) {
                return;
            }


            const text =
                textElement.value.trim();


            const score =
                Number(
                    commentScore.value
                );


            if (!text) {

                return;

            }


            if (
                score < 1 ||
                score > 5
            ) {

                return;

            }


            /*
             * ثبت نظر از طریق API
             */

            const submitButton =
                commentForm.querySelector(
                    ".submit-comment-button"
                );


            if (submitButton) {

                submitButton.disabled = true;

                submitButton.textContent =
                    "در حال ثبت...";

            }


            try {

                const response =
                    await fetch(
                        `${PRODUCT_CONFIG.detailUrl}comments/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                "Accept":
                                    "application/json",

                                "X-CSRFToken":
                                    getCsrfToken()
                            },

                            body: JSON.stringify({
                                text,
                                score
                            })
                        }
                    );


                if (!response.ok) {

                    throw new Error(
                        `Comment API error: ${response.status}`
                    );

                }


                if (commentFeedback) {

                    commentFeedback.textContent =
                        "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.";

                    commentFeedback.classList.add(
                        "success"
                    );

                    commentFeedback.classList.remove(
                        "hidden",
                        "error"
                    );

                }


                commentForm.reset();


                ratingStars
                    ?.querySelectorAll("button")
                    .forEach(
                        star => {

                            star.textContent =
                                "☆";

                        }
                    );

                commentScore.value = 0;


            } catch (error) {

                console.error(
                    "Comment submit failed:",
                    error
                );


                if (commentFeedback) {

                    commentFeedback.textContent =
                        "ثبت نظر با خطا مواجه شد. دوباره تلاش کنید.";

                    commentFeedback.classList.add(
                        "error"
                    );

                    commentFeedback.classList.remove(
                        "hidden",
                        "success"
                    );

                }


            } finally {

                if (submitButton) {

                    submitButton.disabled = false;

                    submitButton.textContent =
                        "ثبت نظر";

                }

            }

        }
    );

}


/* =========================================
   Initial
========================================= */

loadProduct();