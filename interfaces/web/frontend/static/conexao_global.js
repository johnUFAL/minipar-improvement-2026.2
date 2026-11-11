(() => {
    "use strict";

    // Camada global da conexão: pastilha de status no topo de todas as páginas,
    // aviso de convite de execução e chat flutuante.
    const lib = window.MiniparConexao;
    if (!lib) return;

    const OPEN_KEY = "minipar-conexao-chat-open";
    const onConexaoPage = Boolean(document.getElementById("page-conexao"));

    const chip = document.getElementById("conn-chip");
    const chipText = document.getElementById("conn-chip-text");
    const invite = {
        root: document.getElementById("conn-invite"),
        text: document.getElementById("conn-invite-text"),
        accept: document.getElementById("conn-invite-accept"),
        reject: document.getElementById("conn-invite-reject"),
        count: document.getElementById("conn-invite-count"),
    };
    const root = document.getElementById("global-chat");
    const chat = root ? {
        toggle: document.getElementById("global-chat-toggle"),
        panel: document.getElementById("global-chat-panel"),
        close: document.getElementById("global-chat-close"),
        status: document.getElementById("global-chat-status"),
        messages: document.getElementById("global-chat-messages"),
        form: document.getElementById("global-chat-form"),
        input: document.getElementById("global-chat-input"),
        send: document.getElementById("global-chat-send"),
        badge: document.getElementById("global-chat-badge"),
    } : null;

    let lastSignature = "";
    let lastMessageCount = 0;
    let unread = 0;
    let open = true;
    try {
        open = sessionStorage.getItem(OPEN_KEY) !== "0";
    } catch (error) {
        open = true;
    }
    let respondendo = false;

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[character]));
    }

    // ------------------------------------------------------------- pastilha
    function renderChip(state) {
        if (!chip || !chipText) return;
        const info = lib.describe(state);
        chipText.textContent = info.curto;
        chip.title = info.texto;
        chip.className = `conn-chip conn-chip-${info.tom}`;
        chip.setAttribute("aria-label", `Conexão: ${info.texto}`);
    }

    // ---------------------------------------------------------------- convite
    function renderInvite(state) {
        if (!invite.root) return;
        const convites = Array.isArray(state.convites) ? state.convites : [];
        if (!convites.length) {
            invite.root.hidden = true;
            return;
        }
        const convite = convites[0];
        const dados = convite.dados || {};
        invite.root.hidden = false;
        invite.root.setAttribute("data-convite", convite.convite_id || "");
        invite.text.textContent = `${convite.nome || "Alguém"} quer executar "${dados.programa || "um programa"}" em par com você. `
            + `Você vai rodar ${dados.par_arquivo || "o programa par"} como ${dados.papel_convidado || "convidado"}.`;
        invite.count.textContent = convites.length > 1 ? `+${convites.length - 1} convite(s)` : "";
        invite.accept.disabled = respondendo;
        invite.reject.disabled = respondendo;
    }

    async function responderConvite(aceitar) {
        const id = invite.root && invite.root.getAttribute("data-convite");
        if (!id || respondendo) return;
        respondendo = true;
        try {
            const data = await lib.post("/api/conexao/execucao/convite/responder", {
                convite_id: id,
                aceitar,
            });
            if (aceitar) irParaEditor(data);
        } catch (error) {
            if (invite.text) invite.text.textContent = error.message;
        } finally {
            respondendo = false;
            renderInvite(lib.state() || {});
        }
    }

    function irParaEditor(state) {
        if (!state || !state.execucao_multi) return;
        if (window.location.pathname === "/editor") return;
        window.location.href = "/editor";
    }

    if (invite.accept) invite.accept.addEventListener("click", () => responderConvite(true));
    if (invite.reject) invite.reject.addEventListener("click", () => responderConvite(false));

    // ------------------------------------------------------------------- chat
    function renderBadge() {
        if (!chat) return;
        chat.badge.textContent = String(unread);
        chat.badge.hidden = unread <= 0;
    }

    function setOpen(value) {
        if (!chat) return;
        open = value;
        try {
            sessionStorage.setItem(OPEN_KEY, value ? "1" : "0");
        } catch (error) {
            // Preferência apenas visual.
        }
        chat.panel.hidden = !value;
        chat.toggle.setAttribute("aria-expanded", value ? "true" : "false");
        if (value) {
            unread = 0;
            renderBadge();
            chat.messages.scrollTop = chat.messages.scrollHeight;
        }
    }

    function renderMessages(messages) {
        if (!messages.length) {
            chat.messages.innerHTML = '<p class="global-chat-empty">Nenhuma mensagem nesta sala ainda.</p>';
            return;
        }
        chat.messages.innerHTML = messages.slice(-100).map(item => `
            <div class="connection-chat-message${item.proprio ? " connection-chat-own" : ""}">
                <span class="connection-chat-meta">${escapeHtml(item.hora || "")} · ${escapeHtml(item.nome || (item.proprio ? "Você" : "Parceiro"))}</span>
                <p>${escapeHtml(item.texto || "")}</p>
            </div>
        `).join("");
    }

    function renderChat(state) {
        if (!chat) return;
        const registered = lib.isRegistered(state);
        if (!registered || onConexaoPage) {
            root.hidden = true;
            chat.input.disabled = true;
            chat.send.disabled = true;
            lastSignature = "";
            lastMessageCount = 0;
            unread = 0;
            renderBadge();
            return;
        }
        root.hidden = false;
        chat.input.disabled = false;
        chat.send.disabled = false;
        const parceiro = state.conectado_com;
        const sala = state.sala;
        chat.status.textContent = parceiro
            ? `conectado com ${parceiro.nome}`
            : sala && sala.codigo !== "publica" ? `sala ${sala.nome}` : "sala pública";

        const messages = Array.isArray(state.chat) ? state.chat : [];
        const signature = messages.map(item => `${item.hora}-${item.proprio ? 1 : 0}-${item.texto}`).join("|");
        if (signature !== lastSignature) {
            lastSignature = signature;
            renderMessages(messages);
            if (messages.length > lastMessageCount && !open) {
                unread += messages.length - lastMessageCount;
                renderBadge();
            }
            lastMessageCount = messages.length;
            if (open) chat.messages.scrollTop = chat.messages.scrollHeight;
        }
    }

    async function sendMessage(event) {
        event.preventDefault();
        const texto = (chat.input.value || "").trim();
        if (!texto) return;
        chat.input.value = "";
        try {
            await lib.post("/api/conexao/chat", { texto });
        } catch (error) {
            chat.input.value = texto;
            chat.status.textContent = error.message;
        }
    }

    if (chat) {
        setOpen(open);
        chat.toggle.addEventListener("click", () => setOpen(!open));
        chat.close.addEventListener("click", () => setOpen(false));
        chat.form.addEventListener("submit", sendMessage);
    }

    // ----------------------------------------------------------------- estado
    lib.subscribe(state => {
        renderChip(state);
        renderInvite(state);
        renderChat(state);
        irParaEditor(state);
    });

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && !onConexaoPage) lib.refresh();
    });

    // A página de conexão tem o próprio polling e publica o estado por aqui.
    if (!onConexaoPage) lib.start();
})();
