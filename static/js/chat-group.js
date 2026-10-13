(function () {
    const page = document.querySelector(".chat-page[data-chat-group-id]");
    if (!page) return;

    const modal = page.querySelector("[data-members-modal]");
    if (!modal) return;

    const noteEl = modal.querySelector("[data-members-note]");
    const csrfToken = modal.querySelector('[name="csrfmiddlewaretoken"]').value;
    const membersUrl = page.dataset.membersUrl;
    const leaveUrl = page.dataset.leaveUrl;
    const deleteUrl = page.dataset.deleteUrl;
    const inboxHref =
        (page.querySelector(".chat-back") || {}).href || "/chat/";

    function showNote(text, isError) {
        if (!noteEl) return;
        noteEl.textContent = text;
        noteEl.classList.toggle("is-error", Boolean(isError));
        noteEl.hidden = false;
    }

    function open() {
        modal.hidden = false;
        if (noteEl) noteEl.hidden = true;
    }

    function close() {
        modal.hidden = true;
    }

    function post(url, fields) {
        const body = new FormData();
        Object.keys(fields || {}).forEach((key) => body.append(key, fields[key]));
        return fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: body,
        }).then(async (response) => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.error || "انجام نشد.");
            }
            return data;
        });
    }

    page.querySelectorAll("[data-open-members]").forEach((btn) =>
        btn.addEventListener("click", open)
    );
    modal.querySelectorAll("[data-modal-close]").forEach((el) =>
        el.addEventListener("click", close)
    );

    const addForm = modal.querySelector("[data-add-members-form]");
    if (addForm) {
        addForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const body = new FormData(addForm);
            if (!body.getAll("members").length) {
                showNote("حداقل یک عضو انتخاب کنید.", true);
                return;
            }
            body.append("action", "add");
            fetch(membersUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: body,
            })
                .then(async (response) => {
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        throw new Error(data.error || "افزودن عضو انجام نشد.");
                    }
                    window.location.reload();
                })
                .catch((error) => showNote(error.message, true));
        });
    }

    modal.querySelectorAll("[data-remove-member]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.removeMember;
            if (!window.confirm("این عضو از گروه حذف شود؟")) return;
            post(membersUrl, { action: "remove", user_id: id })
                .then(() => window.location.reload())
                .catch((error) => showNote(error.message, true));
        });
    });

    const leaveBtn = modal.querySelector("[data-leave-group]");
    if (leaveBtn) {
        leaveBtn.addEventListener("click", () => {
            if (!window.confirm("از گروه خارج می‌شوید. ادامه می‌دهید؟")) return;
            post(leaveUrl, {})
                .then(() => {
                    window.location.href = inboxHref;
                })
                .catch((error) => showNote(error.message, true));
        });
    }

    const deleteBtn = modal.querySelector("[data-delete-group]");
    if (deleteBtn) {
        deleteBtn.addEventListener("click", () => {
            if (
                !window.confirm(
                    "کل گروه و همهٔ پیام‌های آن برای همه پاک می‌شود. ادامه می‌دهید؟"
                )
            ) {
                return;
            }
            post(deleteUrl, {})
                .then(() => {
                    window.location.href = inboxHref;
                })
                .catch((error) => showNote(error.message, true));
        });
    }

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close();
    });
})();
