(() => {
    "use strict";

    const CLIENT_KEY = "minipar-conexao-client";
    const OPEN_KEY = "minipar-conexao-chat-open";
    const POLL_INTERVAL = 2000;

    const root = document.getElementById("global-chat");
    if (!root || document.getElementById("page-conexao")) return;

    const clientId = sessionStorage.getItem(CLIENT_KEY);
    if (!clientId) return;

    const elements = {
        toggle: document.getElementById("global-chat-toggle"),
        panel: document.getElementById("global-chat-panel"),
        close: document.getElementById("global-chat-close"),
        status: document.getElementById("global-chat-status"),
        messages: document.getElementById("global-chat-messages"),
        form: document.getElementById("global-chat-form"),
        input: document.getElementById("global-chat-input"),
        send: document.getElementById("global-chat-send"),
        badge: document.getElementById("global-chat-badge"),
    };

    let timer = null;
    let polling = false;
    let lastSignature = "";
    let lastMessageCount = 0;
    let unread = 0;
    let open = sessionStorage.getItem(OPEN_KEY) !== "0";

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[character]));
    }

    function renderBadge() {
        elements.badge.textContent = String(unread);
        elements.badge.hidden = unread <= 0;
    }

    function setOpen(value) {
        open = value;
        sessionStorage.setItem(OPEN_KEY, value ? "1" : "0");
        elements.panel.hidden = !value;
        elements.toggle.setAttribute("aria-expanded", value ? "true" : "false");
        if (value) {
            unread = 0;
            renderBadge();
            elements.messages.scrollTop = elements.messages.scrollHeight;
        }
    }

    function renderMessages(messages) {
        if (!messages.length) {
            elements.messages.innerHTML = '<p class="global-chat-empty">O chat aparece quando a conexão for aceita.</p>';
            return;
        }
        elements.messages.innerHTML = messages.slice(-100).map(item => `
            <div class="connection-chat-message${item.proprio ? " connection-chat-own" : ""}">
                <span class="connection-chat-meta">${escapeHtml(item.hora || "")} · ${escapeHtml(item.nome || (item.proprio ? "Você" : "Parceiro"))}</span>
                <p>${escapeHtml(item.texto || "")}</p>
            </div>
        `).join("");
    }

    function render(state) {
        const connected = state.estado === "conectado";
        if (!connected) {
            root.hidden = true;
            elements.input.disabled = true;
            elements.send.disabled = true;
            lastSignature = "";
            lastMessageCount = 0;
            unread = 0;
            renderBadge();
            return;
        }

        root.hidden = false;
        elements.input.disabled = false;
        elements.send.disabled = false;
        const parceiro = state.conectado_com;
        elements.status.textContent = parceiro
            ? `conectado com ${parceiro.nome}`
            : "conectado";

        const messages = Array.isArray(state.chat) ? state.chat : [];
        const signature = messages.map(item => (
            `${item.hora}-${item.proprio ? 1 : 0}-${item.texto}`
        )).join("|");
        if (signature !== lastSignature) {
            lastSignature = signature;
            renderMessages(messages);
            if (messages.length > lastMessageCount && !open) {
                unread += messages.length - lastMessageCount;
                renderBadge();
            }
            lastMessageCount = messages.length;
            if (open) {
                elements.messages.scrollTop = elements.messages.scrollHeight;
            }
        }
    }

    async function poll() {
        if (polling) return;
        polling = true;
        try {
            const response = await fetch(
                `/api/conexao/estado?client_id=${encodeURIComponent(clientId)}`,
            );
            if (!response.ok) return;
            const data = await response.json();
            if (data.success === false) return;
            if (!data.estado || data.estado === "desconectado") {
                root.hidden = true;
                if (timer) {
                    clearInterval(timer);
                    timer = null;
                }
                return;
            }
            render(data);
        } catch (error) {
            // O chat silencioso evita poluir a tela quando o servidor reinicia.
        } finally {
            polling = false;
        }
    }

    async function sendMessage(event) {
        event.preventDefault();
        const texto = (elements.input.value || "").trim();
        if (!texto) return;
        elements.input.value = "";
        try {
            const response = await fetch("/api/conexao/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ client_id: clientId, texto }),
            });
            const data = await response.json();
            if (!response.ok || data.success === false) {
                throw new Error(data.error || "Falha ao enviar a mensagem.");
            }
            render(data);
        } catch (error) {
            elements.input.value = texto;
            elements.status.textContent = error.message;
        }
        poll();
    }

    function startPolling() {
        if (timer) return;
        timer = setInterval(poll, POLL_INTERVAL);
        poll();
    }

    setOpen(open);
    elements.toggle.addEventListener("click", () => setOpen(!open));
    elements.close.addEventListener("click", () => setOpen(false));
    elements.form.addEventListener("submit", sendMessage);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) poll();
    });

    startPolling();
})();
