(function () {
    const badge = document.querySelector("[data-unread-chats]");
    const conversationUrl = window.NOTIFY_CONVERSATION_URL || "/chat/0/";
    const groupUrl = window.NOTIFY_GROUP_URL || "/chat/groups/0/";
    const RECONNECT_MS = 3000;
    const TOAST_MS = 4500;
    const MAX_TOASTS = 3;

    let socket = null;
    let retryTimer = null;
    let audioCtx = null;
    let count = Number(window.NOTIFY_UNREAD || 0);

    function setCount(value) {
        count = Math.max(0, Number(value) || 0);
        if (!badge) return;
        badge.textContent = String(count);
        badge.hidden = count === 0;
    }

    function conversationUrlFor(peerId) {
        return conversationUrl.replace("/0/", "/" + encodeURIComponent(peerId) + "/");
    }

    function urlFor(data) {
        const template = data.kind === "group" ? groupUrl : conversationUrl;
        return template.replace("/0/", "/" + encodeURIComponent(data.peer_id) + "/");
    }

    function isSameConversation(data) {
        const page = document.querySelector(".chat-page[data-messages-url]");
        if (!page) return false;
        if (data.kind === "group") {
            return String(page.dataset.chatGroupId) === String(data.peer_id);
        }
        return String(page.dataset.chatUserId) === String(data.peer_id);
    }

    function beep() {
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            if (!audioCtx) audioCtx = new Ctx();
            if (audioCtx.state === "suspended") {
                audioCtx.resume().catch(function () {});
            }
            const start = audioCtx.currentTime;
            [
                [880, 0],
                [1175, 0.11],
            ].forEach(function (note) {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = "sine";
                osc.frequency.value = note[0];
                gain.gain.setValueAtTime(0.0001, start + note[1]);
                gain.gain.exponentialRampToValueAtTime(
                    0.16,
                    start + note[1] + 0.02
                );
                gain.gain.exponentialRampToValueAtTime(
                    0.0001,
                    start + note[1] + 0.16
                );
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(start + note[1]);
                osc.stop(start + note[1] + 0.2);
            });
        } catch (error) {
            /* صدا در دسترس نیست؛ بی‌صدا ادامه بده */
        }
    }

    function stack() {
        let el = document.querySelector(".toast-stack");
        if (!el) {
            el = document.createElement("div");
            el.className = "toast-stack";
            el.setAttribute("aria-live", "polite");
            document.body.appendChild(el);
        }
        return el;
    }

    function showToast(data) {
        const container = stack();
        while (container.children.length >= MAX_TOASTS) {
            container.removeChild(container.firstElementChild);
        }

        const toast = document.createElement("div");
        toast.className = "toast";
        toast.setAttribute("role", "button");
        toast.setAttribute("tabindex", "0");

        const avatar = document.createElement("span");
        avatar.className = "toast-avatar";
        avatar.textContent = (data.peer_username || "?").slice(0, 1).toUpperCase();

        const body = document.createElement("div");
        body.className = "toast-body";

        const title = document.createElement("span");
        title.className = "toast-title";
        title.textContent = data.peer_username || "پیام جدید";

        const text = document.createElement("span");
        text.className = "toast-text";
        text.textContent = data.preview || "پیام جدید";

        body.appendChild(title);
        body.appendChild(text);
        toast.appendChild(avatar);
        toast.appendChild(body);
        container.appendChild(toast);

        let removed = false;
        function dismiss() {
            if (removed) return;
            removed = true;
            toast.classList.add("is-leaving");
            window.setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 220);
        }

        function open() {
            dismiss();
            window.location.href = urlFor(data);
        }

        toast.addEventListener("click", open);
        toast.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                open();
            }
        });
        window.setTimeout(dismiss, TOAST_MS);
    }

    function handleMessage(data) {
        if (!data || !data.type) return;

        if (data.type === "notify.sync" || data.type === "notify.badge") {
            setCount(data.unread_chats);
            return;
        }

        if (data.type !== "notify.message") return;

        setCount(data.unread_chats);

        if (data.muted || isSameConversation(data)) return;

        showToast(data);
        beep();
    }

    function connect() {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(`${scheme}://${window.location.host}/ws/notify/`);

        socket.addEventListener("message", function (event) {
            try {
                handleMessage(JSON.parse(event.data));
            } catch (error) {
                /* رویداد نامعتبر */
            }
        });

        socket.addEventListener("close", function () {
            window.clearTimeout(retryTimer);
            retryTimer = window.setTimeout(connect, RECONNECT_MS);
        });

        socket.addEventListener("error", function () {
            if (socket) socket.close();
        });
    }

    setCount(count);
    window.RahaNotify = { setCount: setCount, open: conversationUrlFor };
    connect();
})();
