(function () {
    const page = document.querySelector(".chat-page[data-messages-url]");
    if (!page) return;

    const isGroup = page.dataset.chatKind === "group";
    const wsUrl = page.dataset.wsUrl;
    const messagesUrl = page.dataset.messagesUrl;
    const uploadUrl = page.dataset.uploadUrl;
    const messagesEl = page.querySelector("[data-chat-messages]");
    const loadingEl = page.querySelector("[data-chat-loading]");
    const form = page.querySelector("[data-chat-form]");
    const input = page.querySelector("[data-chat-input]");
    const sendBtn = page.querySelector("[data-chat-send]");
    const statusEl = page.querySelector("[data-chat-status]");
    const attachBtn = page.querySelector("[data-chat-attach]");
    const voiceBtn = page.querySelector("[data-chat-voice]");
    const fileInput = page.querySelector("[data-chat-file]");
    const noteEl = page.querySelector("[data-chat-note]");
    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
    const idleStatus = statusEl ? statusEl.textContent.trim() : "";
    const inboxHref = (page.querySelector(".chat-back") || {}).href || "/chat/";

    const HEARTBEAT_MS = 20000;
    let socket = null;
    let heartbeatTimer = null;
    let noteTimer = null;
    let recorder = null;
    let recordChunks = [];
    let recordBlobType = "";
    let replyTarget = null;

    const replyBar = form.querySelector("[data-reply-bar]");
    const replyNameEl = form.querySelector("[data-reply-name]");
    const replyPreviewEl = form.querySelector("[data-reply-preview]");
    const replyCancelBtn = form.querySelector("[data-reply-cancel]");

    function setReply(id, senderUsername, preview) {
        replyTarget = { id: Number(id), senderUsername: senderUsername || "", preview: preview || "" };
        if (replyNameEl) replyNameEl.textContent = replyTarget.senderUsername;
        if (replyPreviewEl) replyPreviewEl.textContent = replyTarget.preview;
        if (replyBar) replyBar.hidden = false;
        input.focus();
    }

    function clearReply() {
        replyTarget = null;
        if (replyBar) replyBar.hidden = true;
    }

    if (replyCancelBtn) replyCancelBtn.addEventListener("click", clearReply);

    function setStatus(text, online) {
        statusEl.textContent = text;
        statusEl.classList.toggle("is-online", Boolean(online));
    }

    function showNote(text, isError) {
        if (!noteEl) return;
        noteEl.textContent = text;
        noteEl.classList.toggle("is-error", Boolean(isError));
        noteEl.hidden = false;
        clearTimeout(noteTimer);
        noteTimer = setTimeout(() => {
            noteEl.hidden = true;
        }, 3500);
    }

    function formatTime(iso) {
        const date = new Date(iso);
        return new Intl.DateTimeFormat("fa-IR", {
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function formatSize(bytes) {
        if (!bytes) return "";
        const units = ["B", "KB", "MB", "GB"];
        let i = 0;
        let n = bytes;
        while (n >= 1024 && i < units.length - 1) {
            n /= 1024;
            i++;
        }
        return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
    }

    function mediaUrl(path) {
        const base = page.dataset.mediaUrl || "/media/";
        return base.replace(/\/?$/, "/") + path;
    }

    function isImageName(name) {
        return /\.(png|jpe?g|gif|webp)$/i.test(name || "");
    }

    function isVoiceName(name) {
        return /\.(mp3|ogg|m4a|wav|webm)$/i.test(name || "");
    }

    function buildAttachment(data) {
        const url = mediaUrl(data.file);
        const name = data.file_name || data.file.split("/").pop();

        if (data.is_voice || isVoiceName(name)) {
            const audio = document.createElement("audio");
            audio.className = "chat-voice";
            audio.controls = true;
            audio.preload = "metadata";
            audio.src = url;
            return audio;
        }

        if (isImageName(name)) {
            const img = document.createElement("img");
            img.className = "chat-img";
            img.loading = "lazy";
            img.src = url;
            img.alt = name;
            return img;
        }

        const link = document.createElement("a");
        link.className = "chat-file";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.innerHTML = `<span>📎</span><span class="chat-file-name"></span>`;
        link.querySelector(".chat-file-name").textContent = name;
        return link;
    }

    function appendMessage(data) {
        const mine = Number(data.sender_id) === Number(window.CHAT_SELF_ID);
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble " + (mine ? "is-mine" : "is-theirs");
        bubble.dataset.messageId = String(data.id);
        bubble.dataset.senderId = String(data.sender_id);
        bubble.dataset.senderUsername = data.sender_username || "";
        bubble.dataset.replyPreview =
            (data.body || "").trim() ||
            data.file_name ||
            (data.is_voice ? "پیام صوتی" : "پیام بدون متن");

        const placeholder = messagesEl.querySelector(".chat-empty");
        if (placeholder) placeholder.remove();

        if (isGroup && !mine && data.sender_username) {
            const who = document.createElement("div");
            who.className = "chat-sender";
            who.textContent = data.sender_username;
            bubble.appendChild(who);
        }

        if (data.reply) {
            const quote = document.createElement("button");
            quote.type = "button";
            quote.className = "chat-reply-quote";
            quote.dataset.replyTo = String(data.reply.id);

            const quoteName = document.createElement("span");
            quoteName.className = "chat-reply-quote-name";
            quoteName.textContent = data.reply.sender_username || "";

            const quoteText = document.createElement("span");
            quoteText.className = "chat-reply-quote-text";
            quoteText.textContent =
                (data.reply.body || "").trim() ||
                data.reply.file_name ||
                (data.reply.is_voice ? "پیام صوتی" : "پیام");

            quote.appendChild(quoteName);
            quote.appendChild(quoteText);
            bubble.appendChild(quote);
        }

        if (data.file) {
            bubble.appendChild(buildAttachment(data));
        }

        if (data.body) {
            const body = document.createElement("div");
            body.className = "chat-body";
            body.textContent = data.body;
            bubble.appendChild(body);
        }

        const meta = document.createElement("span");
        meta.className = "chat-meta";

        const time = document.createElement("span");
        time.className = "chat-time";
        time.textContent = formatTime(data.created_at);
        meta.appendChild(time);

        if (mine && !isGroup) {
            meta.appendChild(buildTicks(Boolean(data.is_read)));
        }
        bubble.appendChild(meta);

        messagesEl.appendChild(bubble);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function buildTicks(read) {
        const ticks = document.createElement("span");
        ticks.className = "chat-ticks";
        ticks.dataset.read = read ? "1" : "0";
        ticks.textContent = read ? "✓✓" : "✓";
        ticks.setAttribute("aria-label", read ? "خوانده شده" : "ارسال شده");
        return ticks;
    }

    function applyReadReceipt(data) {
        if (Number(data.reader_id) !== Number(window.CHAT_SELF_ID)) {
            (data.message_ids || []).forEach((id) => {
                const ticks = messagesEl.querySelector(
                    `[data-message-id="${Number(id)}"] .chat-ticks`
                );
                if (!ticks) return;
                ticks.dataset.read = "1";
                ticks.textContent = "✓✓";
                ticks.setAttribute("aria-label", "خوانده شده");
            });
        }

        if (window.RahaNotify && data.unread_chats !== undefined) {
            window.RahaNotify.setCount(data.unread_chats);
        }
    }

    function removeMessage(data) {
        const forEveryone = Boolean(data.for_everyone);
        if (!forEveryone && Number(data.target_user_id) !== Number(window.CHAT_SELF_ID)) {
            return;
        }
        const bubble = messagesEl.querySelector(
            `[data-message-id="${Number(data.id)}"]`
        );
        if (bubble) bubble.remove();
    }

    function clearThread() {
        messagesEl.innerHTML = "";
        clearReply();
        const empty = document.createElement("div");
        empty.className = "chat-empty";
        empty.textContent = isGroup
            ? "پیام‌ها برای شما پاک شد. می‌توانید پیام جدید بفرستید."
            : "گفتگو پاک شد. می‌توانید پیام جدید بفرستید.";
        messagesEl.appendChild(empty);
    }

    async function loadHistory() {
        try {
            const response = await fetch(messagesUrl, {
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error(response.status);
            const data = await response.json();
            loadingEl.remove();
            (data.messages || []).forEach(appendMessage);
        } catch (error) {
            loadingEl.textContent =
                "دریافت پیام‌ها با خطا مواجه شد. صفحه را دوباره بارگذاری کنید.";
            loadingEl.classList.add("chat-error");
        }
    }

    function startHeartbeat() {
        stopHeartbeat();
        heartbeatTimer = setInterval(() => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: "heartbeat" }));
            }
        }, HEARTBEAT_MS);
    }

    function stopHeartbeat() {
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }
    }

    function connect() {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const url = `${scheme}://${window.location.host}${wsUrl}`;

        setStatus("در حال اتصال…", false);
        socket = new WebSocket(url);

        socket.addEventListener("open", () => {
            if (isGroup) {
                setStatus(idleStatus, false);
            } else {
                setStatus("در حال دریافت وضعیت…", false);
                socket.send(JSON.stringify({ type: "heartbeat" }));
                startHeartbeat();
            }
            input.focus();
        });

        socket.addEventListener("message", (event) => {
            const data = JSON.parse(event.data);

            if (data.type === "presence") {
                setStatus(data.online ? "آنلاین" : "آفلاین", data.online);
                return;
            }

            if (data.type === "error") {
                showNote(data.message || "خطا در ارسال پیام.", true);
                return;
            }

            if (data.type === "chat.read") {
                applyReadReceipt(data);
                return;
            }

            if (data.type === "chat.message.deleted") {
                removeMessage(data);
                return;
            }

            if (
                data.type === "chat.conversation.deleted" ||
                data.type === "chat.cleared_for_me"
            ) {
                clearThread();
                return;
            }

            if (data.type === "group.members") {
                showNote("فهرست اعضا به‌روز شد.");
                return;
            }

            if (data.type === "chat.group.deleted") {
                showNote("گروه حذف شد.");
                window.location.href = inboxHref;
                return;
            }

            if (data.type !== "chat.message") return;

            appendMessage(data);

            if (
                Number(data.sender_id) !== Number(window.CHAT_SELF_ID) &&
                document.visibilityState === "visible"
            ) {
                socket.send(JSON.stringify({ type: "read" }));
            }
        });

        socket.addEventListener("close", (event) => {
            stopHeartbeat();
            if (event.code === 4001 || event.code === 4003 || event.code === 4004) {
                setStatus("اتصال مجاز نیست", false);
                input.disabled = true;
                sendBtn.disabled = true;
                return;
            }
            if (event.code === 4005) {
                setStatus("دیگر عضو این گروه نیستید", false);
                input.disabled = true;
                sendBtn.disabled = true;
                return;
            }
            setStatus("قطع شد؛ در حال اتصال دوباره…", false);
            setTimeout(connect, 3000);
        });

        socket.addEventListener("error", () => {
            socket.close();
        });
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const body = input.value.trim();
        if (!body || !socket || socket.readyState !== WebSocket.OPEN) return;

        const payload = { body };
        if (replyTarget) payload.reply_to = replyTarget.id;
        socket.send(JSON.stringify(payload));
        clearReply();
        input.value = "";
        input.focus();
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    /* --- فایل --- */

    if (attachBtn && fileInput) {
        attachBtn.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", () => {
            const file = fileInput.files && fileInput.files[0];
            fileInput.value = "";
            if (file) uploadFile(file);
        });
    }

    async function uploadFile(file) {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            showNote("اتصال برقرار نیست؛ چند لحظه دیگر دوباره تلاش کنید.", true);
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        showNote("در حال ارسال فایل…");

        try {
            const response = await fetch(uploadUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "آپلود فایل ناموفق بود.");
            }

            const filePayload = {
                file: data.file,
                file_name: data.file_name,
                is_voice: data.is_voice,
            };
            if (replyTarget) filePayload.reply_to = replyTarget.id;
            socket.send(JSON.stringify(filePayload));
            clearReply();
        } catch (error) {
            showNote(error.message || "آپلود فایل ناموفق بود.", true);
        }
    }

    /* --- ویس --- */

    if (voiceBtn) {
        voiceBtn.addEventListener("click", async () => {
            if (recorder && recorder.state === "recording") {
                recorder.stop();
                return;
            }

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showNote("ضبط ویس در این مرورگر پشتیبانی نمی‌شود.", true);
                return;
            }

            if (!socket || socket.readyState !== WebSocket.OPEN) {
                showNote("اتصال برقرار نیست؛ چند لحظه دیگر دوباره تلاش کنید.", true);
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recordChunks = [];
                const mime = ["audio/webm", "audio/ogg", "audio/mp4"].find(
                    (m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)
                );
                recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
                recordBlobType = mime || "audio/webm";

                recorder.addEventListener("dataavailable", (e) => {
                    if (e.data && e.data.size > 0) recordChunks.push(e.data);
                });

                recorder.addEventListener("stop", async () => {
                    stream.getTracks().forEach((t) => t.stop());
                    voiceBtn.classList.remove("is-recording");
                    voiceBtn.textContent = "🎙️";

                    const blob = new Blob(recordChunks, { type: recordBlobType });
                    const ext = (recordBlobType.split("/")[1] || "webm").split(";")[0];
                    const file = new File([blob], `voice-${Date.now()}.${ext}`, {
                        type: recordBlobType,
                    });
                    recorder = null;
                    await uploadFile(file);
                });

                recorder.start();
                voiceBtn.classList.add("is-recording");
                voiceBtn.textContent = "⏹️";
                showNote("در حال ضبط ویس… برای پایان دوباره بزنید.");
            } catch (error) {
                showNote("دسترسی به میکروفون مقدور نشد.", true);
            }
        });
    }

    /* --- بی‌صدا کردن گفتگو --- */

    const muteBtn = page.querySelector("[data-chat-mute]");
    let muted = Boolean(muteBtn) && muteBtn.getAttribute("aria-pressed") === "true";

    function setMuted(value) {
        muted = Boolean(value);
        const subject = isGroup ? "این گروه" : "این گفتگو";
        if (muteBtn) {
            const label = muted
                ? `فعال کردن صدای ${subject}`
                : `بی‌صدا کردن ${subject}`;
            muteBtn.setAttribute("aria-pressed", muted ? "true" : "false");
            muteBtn.textContent = muted ? "🔕" : "🔔";
            muteBtn.title = label;
            muteBtn.setAttribute("aria-label", label);
        }
        const menuItem = ctxConversation.querySelector('[data-action="mute"]');
        if (menuItem) {
            menuItem.textContent = muted ? "فعال کردن صدای گفتگو" : "بی‌صدا کردن گفتگو";
        }
        showNote(muted ? "بی‌صدا شد." : "صدای این گفتگو فعال شد.");
    }

    async function toggleMute() {
        const url = page.dataset.muteUrl;
        if (!url) return;
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({}),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "خطا");
            setMuted(data.muted);
        } catch (error) {
            showNote("تغییر وضعیت بی‌صدا انجام نشد.", true);
        }
    }

    if (muteBtn) {
        muteBtn.addEventListener("click", toggleMute);
    }

    /* --- منوی راست‌کلیک --- */

    function createMenu(className) {
        const menu = document.createElement("div");
        menu.className = "ctx-menu " + className;
        menu.hidden = true;
        document.body.appendChild(menu);
        return menu;
    }

    const ctxMessage = createMenu("ctx-menu-message");
    ctxMessage.innerHTML = `
        <button type="button" class="ctx-item" data-action="reply">پاسخ</button>
        <button type="button" class="ctx-item" data-action="copy">کپی متن</button>
        <div class="ctx-sep"></div>
        <label class="ctx-item ctx-check">
            <input type="checkbox" data-action="for-everyone" checked>
            <span>${isGroup ? "حذف برای همه" : "حذف برای هر دو طرف"}</span>
        </label>
        <button type="button" class="ctx-item is-danger" data-action="delete">حذف پیام</button>
    `;

    const isGroupAdmin = page.dataset.groupAdmin === "1";

    const ctxConversation = createMenu("ctx-menu-conversation");
    ctxConversation.innerHTML = `
        <button type="button" class="ctx-item" data-action="mute">${
            muted ? "فعال کردن صدای گفتگو" : "بی‌صدا کردن گفتگو"
        }</button>
        <button type="button" class="ctx-item" data-action="clear">${
            isGroup
                ? "پاک کردن پیام‌ها برای من"
                : "پاک کردن گفتگو برای هر دو طرف"
        }</button>
        ${
            isGroup
                ? '<div class="ctx-sep"></div>' +
                  (isGroupAdmin
                      ? '<button type="button" class="ctx-item is-danger" data-action="delete-group">حذف گروه</button>'
                      : '<button type="button" class="ctx-item is-danger" data-action="leave">ترک گروه</button>')
                : ""
        }
    `;

    let ctxBubble = null;

    function closeMenus() {
        ctxMessage.hidden = true;
        ctxConversation.hidden = true;
    }

    function placeMenu(menu, x, y) {
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

    function openMessageMenu(bubble, x, y) {
        ctxBubble = bubble;
        const forEveryoneBox = ctxMessage.querySelector('[data-action="for-everyone"]');
        const mine = Number(bubble.dataset.senderId) === Number(window.CHAT_SELF_ID);
        forEveryoneBox.checked = mine;
        forEveryoneBox.disabled = !mine;
        placeMenu(ctxMessage, x, y);
    }

    function sendSocket(payload) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(payload));
            return true;
        }
        showNote("اتصال برقرار نیست؛ چند لحظه دیگر تلاش کنید.", true);
        return false;
    }

    function deleteCurrentMessage() {
        if (!ctxBubble) return;
        const forEveryoneBox = ctxMessage.querySelector('[data-action="for-everyone"]');
        const forEveryone = !forEveryoneBox.disabled && forEveryoneBox.checked;
        const id = Number(ctxBubble.dataset.messageId);
        ctxBubble = null;
        closeMenus();
        if (
            forEveryone &&
            !window.confirm(
                isGroup
                    ? "این پیام برای همهٔ اعضا پاک می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟"
                    : "این پیام برای هر دو طرف پاک می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟"
            )
        ) {
            return;
        }
        sendSocket({ type: "delete_message", id: id, for_everyone: forEveryone });
    }

    async function copyCurrentMessage() {
        const bubble = ctxBubble;
        ctxBubble = null;
        closeMenus();
        const body = bubble && bubble.querySelector(".chat-body");
        const text = body ? body.textContent : "";
        if (!text) {
            showNote("این پیام متنی ندارد.", true);
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            showNote("پیام کپی شد.");
        } catch (error) {
            showNote("کپی انجام نشد.", true);
        }
    }

    function clearConversation() {
        closeMenus();
        const question = isGroup
            ? "پیام‌های این گروه فقط برای شما پنهان می‌شود و برای دیگران می‌ماند. ادامه می‌دهید؟"
            : "کل گفتگو برای هر دو طرف پاک می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟";
        if (!window.confirm(question)) return;
        sendSocket({ type: "delete_conversation" });
    }

    async function confirmAndPost(url, question, redirectTo) {
        if (!url) return;
        if (!window.confirm(question)) return;
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: new FormData(),
            });
            if (!response.ok) throw new Error(String(response.status));
            if (redirectTo) window.location.href = redirectTo;
        } catch (error) {
            showNote("انجام نشد؛ دوباره تلاش کنید.", true);
        }
    }

    messagesEl.addEventListener("contextmenu", (event) => {
        const bubble = event.target.closest(".chat-bubble");
        closeMenus();

        if (bubble) {
            event.preventDefault();
            openMessageMenu(bubble, event.clientX, event.clientY);
            return;
        }

        if (event.target.closest(".chat-messages")) {
            event.preventDefault();
            ctxBubble = null;
            placeMenu(ctxConversation, event.clientX, event.clientY);
        }
    });

    ctxMessage.addEventListener("click", (event) => {
        const action = event.target.closest("[data-action]");
        if (!action) return;
        if (action.dataset.action === "reply") {
            const bubble = ctxBubble;
            ctxBubble = null;
            closeMenus();
            if (bubble) {
                setReply(
                    bubble.dataset.messageId,
                    bubble.dataset.senderUsername,
                    bubble.dataset.replyPreview
                );
            }
        }
        if (action.dataset.action === "copy") copyCurrentMessage();
        if (action.dataset.action === "delete") deleteCurrentMessage();
    });

    let suppressClick = false;
    let longPressTimer = null;
    let pressStart = null;

    messagesEl.addEventListener(
        "click",
        (event) => {
            if (suppressClick) {
                event.preventDefault();
                event.stopPropagation();
                suppressClick = false;
                return;
            }

            const quote = event.target.closest(".chat-reply-quote");
            if (!quote) return;
            const target = messagesEl.querySelector(
                `[data-message-id="${CSS.escape(quote.dataset.replyTo)}"]`
            );
            if (!target) {
                showNote("پیام اصلی در دسترس نیست.");
                return;
            }
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            target.classList.add("is-highlighted");
            setTimeout(() => target.classList.remove("is-highlighted"), 1200);
        },
        true
    );

    messagesEl.addEventListener("touchstart", (event) => {
        const bubble = event.target.closest(".chat-bubble");
        if (!bubble || event.touches.length !== 1) return;
        const touch = event.touches[0];
        pressStart = { x: touch.clientX, y: touch.clientY };
        clearTimeout(longPressTimer);
        longPressTimer = setTimeout(() => {
            suppressClick = true;
            openMessageMenu(bubble, pressStart.x, pressStart.y);
        }, 500);
    });

    messagesEl.addEventListener("touchmove", (event) => {
        if (!pressStart || !longPressTimer) return;
        const touch = event.touches[0];
        const dx = touch.clientX - pressStart.x;
        const dy = touch.clientY - pressStart.y;
        if (Math.hypot(dx, dy) > 10) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    });

    function endLongPress() {
        clearTimeout(longPressTimer);
        longPressTimer = null;
        pressStart = null;
    }

    messagesEl.addEventListener("touchend", endLongPress);
    messagesEl.addEventListener("touchcancel", endLongPress);

    ctxConversation.addEventListener("click", (event) => {
        const action = event.target.closest("[data-action]");
        if (!action) return;
        if (action.dataset.action === "mute") {
            closeMenus();
            toggleMute();
        }
        if (action.dataset.action === "clear") {
            clearConversation();
        }
        if (action.dataset.action === "leave") {
            closeMenus();
            confirmAndPost(
                page.dataset.leaveUrl,
                "از گروه خارج می‌شوید و دیگر پیام‌های آن را نمی‌بینید. ادامه می‌دهید؟",
                inboxHref
            );
        }
        if (action.dataset.action === "delete-group") {
            closeMenus();
            confirmAndPost(
                page.dataset.deleteUrl,
                "کل گروه و همهٔ پیام‌های آن برای همه پاک می‌شود. ادامه می‌دهید؟",
                inboxHref
            );
        }
    });

    document.addEventListener("click", (event) => {
        if (event.target.closest(".ctx-menu")) return;
        closeMenus();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenus();
            clearReply();
        }
    });
    window.addEventListener("scroll", closeMenus, true);
    window.addEventListener("resize", closeMenus);

    if (isGroup) {
        setStatus(idleStatus, false);
    } else if (page.dataset.otherOnline === "1") {
        setStatus("آنلاین", true);
    } else {
        setStatus("آفلاین", false);
    }

    loadHistory();
    connect();
})();
