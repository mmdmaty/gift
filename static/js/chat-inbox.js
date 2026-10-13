(function () {
    const page = document.querySelector(".chat-inbox-page");
    if (!page) return;

    const searchInput = page.querySelector("[data-inbox-search]");
    const tabs = Array.from(page.querySelectorAll("[data-tab]"));
    const sections = Array.from(page.querySelectorAll("[data-section]"));
    const emptyEl = page.querySelector("[data-inbox-empty]");
    const rows = () => Array.from(page.querySelectorAll("[data-chat-row]"));
    const modal = page.querySelector("[data-new-group-modal]");
    const csrfToken = page.querySelector('[name="csrfmiddlewaretoken"]').value;

    let activeTab = "all";

    /* --- جست‌وجو و تب‌ها --- */

    function applyFilter() {
        const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
        let visible = 0;

        rows().forEach((row) => {
            const kindOk = activeTab === "all" || row.dataset.kind === activeTab;
            const name = (row.dataset.name || "").toLowerCase();
            const textOk = !query || name.includes(query);
            const show = kindOk && textOk;
            row.hidden = !show;
            if (show) visible += 1;
        });

        sections.forEach((section) => {
            const kind = section.dataset.section;
            const kindOk = activeTab === "all" || activeTab === kind;
            const hasVisible = Array.from(
                section.querySelectorAll("[data-chat-row]")
            ).some((row) => !row.hidden);
            section.hidden = !kindOk || !hasVisible;
        });

        if (emptyEl) emptyEl.hidden = visible !== 0;
    }

    if (searchInput) searchInput.addEventListener("input", applyFilter);

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            activeTab = tab.dataset.tab;
            tabs.forEach((other) =>
                other.classList.toggle("is-active", other === tab)
            );
            applyFilter();
        });
    });

    /* --- مودال ساخت گروه --- */

    function openModal() {
        if (!modal) return;
        modal.hidden = false;
        const first = modal.querySelector("input[type='text']");
        if (first) first.focus();
    }

    function closeModal() {
        if (!modal) return;
        modal.hidden = true;
    }

    page.querySelectorAll("[data-open-new-group]").forEach((btn) =>
        btn.addEventListener("click", openModal)
    );
    if (modal) {
        modal.querySelectorAll("[data-modal-close]").forEach((el) =>
            el.addEventListener("click", closeModal)
        );
    }

    /* --- منوی راست‌کلیک --- */

    const menu = document.createElement("div");
    menu.className = "ctx-menu ctx-menu-inbox";
    menu.hidden = true;
    document.body.appendChild(menu);

    let menuRow = null;

    function closeMenu() {
        menu.hidden = true;
        menuRow = null;
    }

    function placeMenu(x, y) {
        menu.hidden = false;
        const rect = menu.getBoundingClientRect();
        let left = x;
        let top = y;
        if (left + rect.width > window.innerWidth - 8) {
            left = window.innerWidth - rect.width - 8;
        }
        if (top + rect.height > window.innerHeight - 8) {
            top = window.innerHeight - rect.height - 8;
        }
        menu.style.left = Math.max(8, left) + "px";
        menu.style.top = Math.max(8, top) + "px";
    }

    function menuItem(label, action, danger) {
        return (
            '<button type="button" class="ctx-item' +
            (danger ? " is-danger" : "") +
            '" data-action="' +
            action +
            '">' +
            label +
            "</button>"
        );
    }

    function openMenu(row, x, y) {
        const kind = row.dataset.kind;
        const muted = row.dataset.muted === "1";
        const isAdmin = row.dataset.admin === "1";
        const muteLabel = muted ? "فعال کردن صدای گفتگو" : "بی‌صدا کردن گفتگو";

        let html = menuItem(muteLabel, "mute", false);
        html += '<div class="ctx-sep"></div>';
        if (kind === "group" && isAdmin) {
            html += menuItem("حذف گروه", "delete", true);
        } else if (kind === "group") {
            html += menuItem("ترک گروه", "leave", true);
        } else {
            html += menuItem("پاک کردن گفتگو", "delete", true);
        }

        menu.innerHTML = html;
        menuRow = row;
        placeMenu(x, y);
    }

    function post(url) {
        return fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: new FormData(),
        }).then((response) => {
            if (!response.ok) throw new Error(String(response.status));
            return response.json().catch(() => ({}));
        });
    }

    function setRowMuted(row, muted) {
        row.dataset.muted = muted ? "1" : "0";
        let flag = row.querySelector(".chat-mute-flag");
        if (muted) {
            if (!flag) {
                flag = document.createElement("span");
                flag.className = "chat-mute-flag";
                flag.title = "بی‌صدا";
                flag.textContent = "🔕";
                const anchor = row.querySelector(".chat-user-row");
                const badge = row.querySelector(".chat-unread-badge");
                const dot = row.querySelector(".chat-dot");
                const before = badge || dot || null;
                if (anchor) anchor.insertBefore(flag, before);
            }
        } else if (flag) {
            flag.remove();
        }
    }

    function runAction(row, action) {
        const kind = row.dataset.kind;

        if (action === "mute") {
            post(row.dataset.muteUrl)
                .then((data) => setRowMuted(row, Boolean(data.muted)))
                .catch(() => {});
            return;
        }

        if (action === "delete") {
            const question =
                kind === "group"
                    ? "کل گروه و همهٔ پیام‌های آن پاک می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟"
                    : "کل گفتگو برای هر دو طرف پاک می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟";
            if (!window.confirm(question)) return;
            post(row.dataset.deleteUrl)
                .then(() => removeRow(row))
                .catch(() => {});
            return;
        }

        if (action === "leave") {
            if (!window.confirm("از گروه خارج می‌شوید و دیگر پیام‌های آن را نمی‌بینید. ادامه می‌دهید؟")) {
                return;
            }
            post(row.dataset.leaveUrl)
                .then(() => removeRow(row))
                .catch(() => {});
        }
    }

    function removeRow(row) {
        row.remove();
        applyFilter();
    }

    menu.addEventListener("click", (event) => {
        const action = event.target.closest("[data-action]");
        if (!action || !menuRow) return;
        const row = menuRow;
        closeMenu();
        runAction(row, action.dataset.action);
    });

    const listRoot = page;
    let suppressClick = false;
    let pressTimer = null;

    listRoot.addEventListener("contextmenu", (event) => {
        const row = event.target.closest("[data-chat-row]");
        if (!row) return;
        event.preventDefault();
        openMenu(row, event.clientX, event.clientY);
    });

    listRoot.addEventListener(
        "touchstart",
        (event) => {
            const row = event.target.closest("[data-chat-row]");
            if (!row) return;
            const touch = event.touches[0];
            const x = touch.clientX;
            const y = touch.clientY;
            clearTimeout(pressTimer);
            pressTimer = setTimeout(() => {
                suppressClick = true;
                openMenu(row, x, y);
            }, 500);
        },
        { passive: true }
    );

    ["touchend", "touchmove", "touchcancel"].forEach((type) =>
        listRoot.addEventListener(type, () => clearTimeout(pressTimer), {
            passive: true,
        })
    );

    listRoot.addEventListener(
        "click",
        (event) => {
            if (suppressClick) {
                suppressClick = false;
                event.preventDefault();
                event.stopPropagation();
            }
        },
        true
    );

    document.addEventListener("click", (event) => {
        if (event.target.closest(".ctx-menu")) return;
        closeMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
            closeModal();
        }
    });
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);

    applyFilter();
})();
