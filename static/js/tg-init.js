/*
 * راه‌اندازی مینی‌اپ تلگرام:
 * وقتی سایت داخل تلگرام باز می‌شود، initData را برای احرازهویت خودکار
 * به سرور می‌فرستد و در صورت موفقیت صفحه را یک‌بار رفرش می‌کند.
 */
(function () {
    "use strict";

    var tg = window.Telegram && window.Telegram.WebApp;

    // خارج از تلگرام (مرورگر معمولی): کاری نکن
    if (!tg || !tg.initData) {
        return;
    }

    // آماده‌سازی ظاهر مینی‌اپ
    try {
        tg.ready();
        tg.expand();
    } catch (e) {
        /* بی‌اهمیت */
    }

    var cfg = window.TG_CONFIG || {};

    // اگر از قبل لاگین است، نیازی به احرازهویت دوباره نیست
    if (cfg.isAuthenticated) {
        return;
    }

    // جلوگیری از حلقه‌ی رفرش در صورت شکست احرازهویت
    var GUARD_KEY = "tgAuthAttempted";
    if (sessionStorage.getItem(GUARD_KEY)) {
        return;
    }
    sessionStorage.setItem(GUARD_KEY, "1");

    fetch(cfg.authUrl || "/api/tg/auth/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ initData: tg.initData })
    })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data && data.ok) {
                // نشست ساخته شد؛ رفرش تا سرور کاربر لاگین‌شده را ببیند
                window.location.reload();
            } else {
                console.warn("احرازهویت تلگرام ناموفق بود:", data && data.error);
            }
        })
        .catch(function (err) {
            console.warn("خطا در احرازهویت تلگرام:", err);
        });
})();
