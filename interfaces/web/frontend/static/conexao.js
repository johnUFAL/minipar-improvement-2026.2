(() => {
    "use strict";

    const CLIENT_KEY = "minipar-conexao-client";
    const CLIENT_NAME_KEY = "minipar-conexao-nome";
    const CONEXAO_HANDOFF_KEY = "minipar-conexao-handoff";
    const SERVER_KEY = "minipar-conexao-servers";
    const POLL_INTERVAL = 1000;

    const elements = {
        host: document.getElementById("connection-host"),
        port: document.getElementById("connection-port"),
        name: document.getElementById("connection-name"),
        hubHost: document.getElementById("connection-hub-host"),
        startHub: document.getElementById("connection-start-hub"),
        stopHub: document.getElementById("connection-stop-hub"),
        connect: document.getElementById("connection-connect"),
        disconnect: document.getElementById("connection-disconnect"),
        serverList: document.getElementById("connection-server-list"),
        serverRefresh: document.getElementById("connection-server-refresh"),
        serverDiscover: document.getElementById("connection-server-discover"),
        roomName: document.getElementById("connection-room-name"),
        roomPassword: document.getElementById("connection-room-password"),
        createRoom: document.getElementById("connection-create-room"),
        roomCode: document.getElementById("connection-room-code"),
        joinPassword: document.getElementById("connection-room-join-password"),
        joinRoom: document.getElementById("connection-join-room"),
        leaveRoom: document.getElementById("connection-leave-room"),
        log: document.getElementById("connection-log"),
        status: document.getElementById("connection-status"),
        room: document.getElementById("connection-room"),
        peers: document.getElementById("connection-peers"),
        request: document.getElementById("connection-request"),
        requestText: document.getElementById("connection-request-text"),
        accept: document.getElementById("connection-accept"),
        reject: document.getElementById("connection-reject"),
        chat: document.getElementById("connection-chat"),
        chatState: document.getElementById("connection-chat-state"),
        chatForm: document.getElementById("connection-chat-form"),
        chatInput: document.getElementById("connection-chat-input"),
        chatSend: document.getElementById("connection-chat-send"),
        programTitle: document.getElementById("connection-program-title"),
        programInfo: document.getElementById("connection-program-info"),
        statusbar: document.getElementById("connection-statusbar"),
        barTimer: document.getElementById("connection-bar-timer"),
        reconnect: document.getElementById("connection-reconnect"),
        viewHubs: document.getElementById("connection-view-hubs"),
        viewHub: document.getElementById("connection-view-hub"),
        roomsCard: document.getElementById("connection-rooms-card"),
        rooms: document.getElementById("connection-rooms"),
        roomsCount: document.getElementById("connection-rooms-count"),
        joinBox: document.getElementById("connection-join-box"),
        joinTitle: document.getElementById("connection-join-title"),
        joinConfirm: document.getElementById("connection-join-confirm"),
        joinCancel: document.getElementById("connection-join-cancel"),
        roomCard: document.getElementById("connection-room-card"),
        roomTitle: document.getElementById("connection-room-title"),
        roomInfo: document.getElementById("connection-room-info"),
        roomHint: document.getElementById("connection-room-hint"),
        toasts: document.getElementById("connection-toasts"),
    };

    function generateId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID().replace(/-/g, "").slice(0, 16);
        }
        return `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
    }

    let clientId = sessionStorage.getItem(CLIENT_KEY);
    if (!clientId) {
        clientId = generateId();
        sessionStorage.setItem(CLIENT_KEY, clientId);
    }

    if (elements.name && !elements.name.value) {
        elements.name.value = sessionStorage.getItem(CLIENT_NAME_KEY) || `Sessão-${clientId.slice(0, 4)}`;
    }

    const program = new URLSearchParams(window.location.search).get("program") || "";
    let state = { estado: "desconectado", peers: [], chat: [], solicitacao: null, sala: null };
    let pollTimer = null;
    let polling = false;
    let lastChatSignature = "";
    let programSpec = null;
    let hubAtivo = false;
    let serverSignature = "";
    let wasOnline = false;
    let userLeft = false;
    let lastHub = null;
    let fechaRef = null;
    let roomsSignature = "";
    let pendingJoin = null;
    const PUBLICA = "publica";

    function readServers() {
        try {
            const raw = localStorage.getItem(SERVER_KEY);
            const lista = raw ? JSON.parse(raw) : [];
            if (!Array.isArray(lista)) return [];
            return lista.filter(item => (
                item
                && typeof item.host === "string"
                && item.host.trim()
                && Number.isInteger(Number(item.porta))
                && Number(item.porta) >= 1
                && Number(item.porta) <= 65535
            )).slice(0, 20);
        } catch (error) {
            return [];
        }
    }

    function saveServers(lista) {
        try {
            localStorage.setItem(SERVER_KEY, JSON.stringify(lista.slice(0, 20)));
        } catch (error) {
            // O armazenamento local pode estar indisponível em modo privado.
        }
    }

    function serverId(host, porta) {
        return `${String(host || "").trim()}:${Number(porta) || 0}`;
    }

    function rememberServer(host, porta, nome = "") {
        const endereco = String(host || "").trim();
        const numero = Number(porta);
        if (!endereco || !Number.isInteger(numero) || numero < 1 || numero > 65535) return;
        const lista = readServers().filter(
            item => serverId(item.host, item.porta) !== serverId(endereco, numero)
        );
        lista.unshift({
            host: endereco,
            porta: numero,
            nome: String(nome || "").trim(),
        });
        saveServers(lista);
    }

    function forgetServer(host, porta) {
        const alvo = serverId(host, porta);
        saveServers(readServers().filter(
            item => serverId(item.host, item.porta) !== alvo
        ));
    }

    function renderServers(hubs) {
        if (!elements.serverList) return;
        const lista = Array.isArray(hubs) ? hubs : [];
        const assinatura = JSON.stringify(lista);
        if (assinatura === serverSignature) return;
        serverSignature = assinatura;
        if (!lista.length) {
            elements.serverList.innerHTML =
                '<li class="connection-empty">Nenhum hub encontrado. Verifique se está na mesma rede, clique em "Procurar na rede" ou adicione manualmente.</li>';
            return;
        }
        elements.serverList.innerHTML = lista.map(item => {
            const host = escapeHtml(item.host || "");
            const porta = Number(item.porta) || 0;
            const nome = escapeHtml(item.nome || item.host || "Servidor");
            const ativo = Boolean(item.ativo);
            const local = item.local ? " · local" : "";
            return `<li class="connection-server ${ativo ? "connection-server-online" : "connection-server-offline"}">
                <button type="button" class="connection-server-pick" data-host="${host}" data-port="${porta}" title="Entrar neste hub" ${ativo ? "" : "disabled"}>
                    <span class="connection-server-name">${nome}</span>
                    <small>${host}:${porta}${local} · ${ativo ? "disponível — clique para entrar" : "sem resposta"}</small>
                </button>
                <button type="button" class="connection-server-remove" data-host="${host}" data-port="${porta}" title="Remover servidor">×</button>
            </li>`;
        }).join("");
    }

    async function refreshServers(descobrir = false) {
        if (!elements.serverList) return;
        const salvos = readServers();
        try {
            const data = await requestJson("/api/conexao/hubs", { hubs: salvos, descobrir });
            const hubs = data.hubs || [];
            hubs.filter(item => item.descoberto).forEach(item => {
                rememberServer(item.host, item.porta, item.nome);
            });
            renderServers(hubs);
        } catch (error) {
            renderServers(salvos.map(item => ({ ...item, ativo: false, local: false })));
        }
    }

    function updateHubButtons() {
        if (elements.stopHub) elements.stopHub.hidden = !hubAtivo;
    }

    async function loadNetwork() {
        try {
            const response = await fetch("/api/conexao/rede");
            if (!response.ok) return;
            const rede = await response.json();
            const ips = Array.isArray(rede.ips_locais) ? rede.ips_locais : [];
            if (elements.hubHost) {
                const atual = elements.hubHost.value;
                const opcoes = ["0.0.0.0", ...ips.filter(ip => ip !== "0.0.0.0")];
                elements.hubHost.innerHTML = opcoes.map(ip => (
                    `<option value="${escapeHtml(ip)}">${ip === "0.0.0.0" ? "Todos os endereços (0.0.0.0)" : escapeHtml(ip)}</option>`
                )).join("");
                elements.hubHost.value = opcoes.includes(atual) ? atual : "0.0.0.0";
            }
            hubAtivo = Boolean(rede.hub_ativo);
            updateHubButtons();
            await refreshServers();
        } catch (error) {
            renderServers([]);
        }
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "\"": "&quot;",
            "'": "&#39;",
        })[character]);
    }

    function timestamp() {
        const now = new Date();
        return [now.getHours(), now.getMinutes(), now.getSeconds()]
            .map(value => String(value).padStart(2, "0"))
            .join(":");
    }

    function log(message, tone = "info") {
        if (!elements.log) return;
        const line = document.createElement("span");
        line.className = `connection-log-line connection-log-${tone}`;
        line.textContent = `[${timestamp()}] ${message}`;
        elements.log.appendChild(line);
        elements.log.appendChild(document.createTextNode("\n"));
        while (elements.log.childNodes.length > 400) {
            elements.log.removeChild(elements.log.firstChild);
        }
        elements.log.scrollTop = elements.log.scrollHeight;
    }

    function describeEvent(event) {
        switch (event.type) {
            case "registrado":
                return `Registrado no hub como ${event.nome || "participante"}.`;
            case "sala_atual": {
                const sala = event.sala || {};
                const motivo = event.motivo || "entrada";
                if (motivo === "inatividade") return "A sala foi fechada por inatividade.";
                if (motivo === "sala_encerrada") return "O dono encerrou a sala.";
                return `Sala ${motivo}: ${sala.nome || "?"} [${sala.codigo || "?"}].`;
            }
            case "aguardando":
                return `Aguardando aceite de ${(event.peer || {}).nome || "?"}...`;
            case "resposta":
                return event.aceitar
                    ? `Conexão aceita por ${(event.peer || {}).nome || "?"}.`
                    : `${(event.peer || {}).nome || "?"} recusou a conexão.`;
            case "conectado":
                return `Conectado a ${(event.peer || {}).nome || "?"}.`;
            case "peer_desconectou":
                return `${(event.peer || {}).nome || "?"} desconectou.`;
            case "desconectado":
                return "Conexão encerrada.";
            case "solicitacao":
                return `${event.nome || "?"} quer se conectar.`;
            case "exec_contexto": {
                const contexto = event.contexto || {};
                return `Parceiro preparou o papel ${contexto.papel || "?"}` +
                    (contexto.host ? ` em ${contexto.host}:${contexto.porta || "?"}` : ".") ;
            }
            case "exec_preparado":
                return "O outro lado terminou de preparar a execução.";
            case "exec_pronto":
                return `O outro lado abriu a porta ${event.porta || "do canal"}.`;
            case "exec_fim":
                return `O outro lado terminou com código ${event.exit_code ?? "?"}.`;
            case "exec_erro":
                return `Execução: ${event.mensagem || "falha no outro lado"}`;
            case "exec_parar":
                return `Execução encerrada: ${event.motivo || "pedido do outro lado"}.`;
            case "erro":
                return event.mensagem || "Erro no hub.";
            default:
                return "";
        }
    }

    function toast(message, tone = "info") {
        if (!elements.toasts || !message) return;
        const item = document.createElement("div");
        item.className = `connection-toast connection-toast-${tone}`;
        item.textContent = message;
        elements.toasts.appendChild(item);
        while (elements.toasts.childNodes.length > 4) {
            elements.toasts.removeChild(elements.toasts.firstChild);
        }
        setTimeout(() => item.remove(), 5000);
    }

    const TOAST_EVENTS = ["solicitacao", "conectado", "peer_desconectou", "exec_erro", "erro"];

    function applyEvents(events) {
        (events || []).forEach(event => {
            const message = describeEvent(event);
            if (!message) return;
            const tone = ["erro", "exec_erro"].includes(event.type)
                ? "error"
                : ["conectado", "registrado", "exec_pronto"].includes(event.type)
                    ? "ok"
                    : "info";
            log(message, tone);
            const sala = event.type === "sala_atual"
                && ["inatividade", "sala_encerrada"].includes(event.motivo);
            const recusa = event.type === "resposta" && !event.aceitar;
            if (TOAST_EVENTS.includes(event.type) || sala || recusa) {
                toast(message, tone === "ok" ? "ok" : tone === "error" ? "error" : "info");
            }
        });
    }

    function diffPeers(anterior, atual) {
        if (!anterior || !atual || !anterior.sala || !atual.sala) return;
        if (anterior.sala.codigo !== atual.sala.codigo) return;
        const antes = new Map((anterior.peers || []).map(peer => [peer.id, peer.nome]));
        const depois = new Map((atual.peers || []).map(peer => [peer.id, peer.nome]));
        depois.forEach((nome, id) => {
            if (!antes.has(id)) toast(`${nome} entrou na sala.`);
        });
        antes.forEach((nome, id) => {
            if (!depois.has(id)) toast(`${nome} saiu da sala.`);
        });
    }

    function applyState(data) {
        if (data && typeof data === "object" && "estado" in data) {
            const anterior = state;
            state = { ...state, ...data };
            if (["registrado", "conectado"].includes(anterior.estado)) {
                diffPeers(anterior, state);
            }
        }
        applyEvents(data && data.eventos);
        render();
    }

    const lib = window.MiniparConexao;

    function render() {
        const info = lib.describe(state);
        const registered = info.registered;
        const connected = info.connected;
        const perdida = info.perdida;
        const sala = state.sala;
        const publica = info.publica;
        const dono = info.dono;
        if (registered) userLeft = false;

        elements.status.textContent = info.texto;
        elements.statusbar.className = `connection-statusbar connection-bar-${info.tom}`;
        elements.barTimer.hidden = info.restante === null;
        if (info.restante !== null) {
            elements.barTimer.textContent = `A sala fecha em ${info.restante}s por inatividade`;
        }

        elements.disconnect.hidden = !registered;
        elements.reconnect.hidden = !perdida || !lastHub;
        elements.leaveRoom.hidden = !registered || publica;
        elements.leaveRoom.textContent = dono ? "Encerrar sala" : "Sair da sala";

        elements.viewHubs.hidden = registered;
        elements.viewHub.hidden = !registered;
        elements.roomsCard.hidden = !publica;
        elements.roomCard.hidden = publica;
        elements.room.textContent = sala
            ? `${sala.nome} [${sala.codigo}] · ${sala.lotacao}${sala.maximo ? `/${sala.maximo}` : ""}`
            : "Sem sala";

        if (!publica && sala) {
            elements.roomTitle.textContent = `${sala.com_senha ? "🔒 " : ""}${sala.nome}`;
            elements.roomInfo.textContent = `código ${sala.codigo} · dono: ${sala.dono || "-"}`;
            elements.roomHint.textContent = connected
                ? "Vocês estão conectados. Para executar em par, volte ao editor e clique em Executar."
                : sala.lotacao < (sala.maximo || 2)
                    ? `Aguardando outro participante. Compartilhe o código ${sala.codigo}${sala.com_senha ? " e a senha" : ""}, ou ele pode escolher a sala na lista.`
                    : "Para executar em par, volte ao editor e clique em Executar: o convite chega ao outro participante.";
        }

        renderRooms();
        renderPeers();
        renderRequest();
        renderChat(registered);
        lib.publish(state);
    }

    function renderRooms() {
        const salas = Array.isArray(state.salas) ? state.salas : [];
        elements.roomsCount.textContent = `${salas.length} ${salas.length === 1 ? "sala" : "salas"}`;
        const assinatura = JSON.stringify(salas);
        if (assinatura === roomsSignature) return;
        roomsSignature = assinatura;
        if (!salas.length) {
            elements.rooms.innerHTML = '<li class="connection-empty">Nenhuma sala criada. Crie uma abaixo ou peça conexão a alguém da sala pública.</li>';
            return;
        }
        elements.rooms.innerHTML = salas.map(sala => {
            const cheia = sala.maximo && sala.lotacao >= sala.maximo;
            const cadeado = sala.com_senha
                ? '<span class="connection-lock" title="Sala com senha" aria-label="Sala com senha">🔒</span>'
                : '<span class="connection-lock connection-lock-open" title="Sala sem senha" aria-label="Sala sem senha"></span>';
            return `<li class="connection-room-item">
                ${cadeado}
                <span class="connection-peer-name"><b>${escapeHtml(sala.nome)}</b><small>${sala.lotacao}/${sala.maximo || "∞"} · dono: ${escapeHtml(sala.dono || "-")} · ${escapeHtml(sala.codigo)}</small></span>
                <button type="button" class="button button-outline connection-room-join" data-room-code="${escapeHtml(sala.codigo)}" data-room-name="${escapeHtml(sala.nome)}" data-room-locked="${sala.com_senha ? "1" : "0"}" ${cheia ? "disabled" : ""}>${cheia ? "Cheia" : "Entrar"}</button>
            </li>`;
        }).join("");
    }

    function renderPeers() {
        const peers = Array.isArray(state.peers) ? state.peers : [];
        if (!peers.length) {
            elements.peers.innerHTML = '<li class="connection-empty">Ninguém mais nesta sala.</li>';
            return;
        }
        const connected = state.estado === "conectado";
        elements.peers.innerHTML = peers.map(peer => {
            const busy = peer.estado === "conectado";
            const disabled = busy || connected;
            return `<li class="connection-peer">
                <span class="connection-peer-name"><b>${escapeHtml(peer.nome)}</b><small>${escapeHtml(peer.id)}${busy ? " · ocupado" : ""}</small></span>
                <button type="button" class="button button-outline connection-peer-connect" data-peer-id="${escapeHtml(peer.id)}" ${disabled ? "disabled" : ""}>Pedir conexão</button>
            </li>`;
        }).join("");
    }

    function renderRequest() {
        const pedido = state.solicitacao;
        if (!pedido) {
            elements.request.hidden = true;
            elements.requestText.textContent = "";
            return;
        }
        elements.request.hidden = false;
        const sala = state.sala && state.sala.codigo !== PUBLICA ? "na sua sala" : "na sala pública";
        elements.requestText.textContent = `${pedido.nome || "Participante"} quer se conectar com você ${sala}.`;
    }

    function renderChat(registered) {
        const sala = state.sala;
        elements.chatInput.disabled = !registered;
        elements.chatSend.disabled = !registered;
        elements.chatState.textContent = registered && sala
            ? (sala.codigo === PUBLICA ? "sala pública" : `sala ${sala.nome}`)
            : "sem sala";

        const mensagens = Array.isArray(state.chat) ? state.chat : [];
        const signature = mensagens.map(item => `${item.hora}-${item.proprio ? 1 : 0}-${item.texto}`).join("|");
        if (signature !== lastChatSignature) {
            lastChatSignature = signature;
            if (!mensagens.length) {
                elements.chat.innerHTML = '<p class="connection-empty">Nenhuma mensagem nesta sala ainda.</p>';
            } else {
                elements.chat.innerHTML = mensagens.map(item => `
                    <div class="connection-chat-message ${item.proprio ? "connection-chat-own" : ""}">
                        <span class="connection-chat-meta">${escapeHtml(item.nome || "?")} · ${escapeHtml(item.hora || "")}</span>
                        <p>${escapeHtml(item.texto)}</p>
                    </div>`).join("");
                elements.chat.scrollTop = elements.chat.scrollHeight;
            }
        }
    }

    async function requestJson(path, payload, method = "POST") {
        const init = { method, headers: {} };
        if (method === "POST") {
            init.headers["Content-Type"] = "application/json";
            init.body = JSON.stringify({ client_id: clientId, ...(payload || {}) });
        }
        const response = await fetch(path, init);
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = { success: false, error: "Resposta inválida do servidor." };
        }
        if (!response.ok || data.success === false) {
            throw new Error(data.error || "Falha na operação.");
        }
        return data;
    }

    async function action(path, payload, successMessage) {
        try {
            const data = await requestJson(path, payload);
            applyState(data);
            if (successMessage) log(successMessage, "ok");
            return data;
        } catch (error) {
            log(error.message, "error");
            return null;
        }
    }

    async function poll() {
        if (polling) return;
        polling = true;
        try {
            const response = await fetch(`/api/conexao/estado?client_id=${encodeURIComponent(clientId)}`);
            if (response.ok) {
                applyState(await response.json());
            }
        } catch (error) {
            // O polling silencioso evita poluir o terminal quando o servidor cai.
        } finally {
            polling = false;
        }
    }

    function startPolling() {
        if (pollTimer) return;
        pollTimer = setInterval(poll, POLL_INTERVAL);
    }

    // ------------------------------------------------------------- ações
    elements.startHub.addEventListener("click", async () => {
        const host = (elements.hubHost.value || "0.0.0.0").trim() || "0.0.0.0";
        const porta = Number(elements.port.value) || 5010;
        try {
            const data = await requestJson("/api/conexao/hub/iniciar", { host, porta });
            elements.port.value = data.porta;
            if (!elements.host.value || elements.host.value === "0.0.0.0") {
                elements.host.value = data.host === "0.0.0.0" ? "127.0.0.1" : data.host;
            }
            hubAtivo = true;
            updateHubButtons();
            rememberServer("127.0.0.1", data.porta, "Hub local");
            (data.enderecos || []).forEach(endereco => {
                rememberServer(endereco, data.porta, "Hub local");
            });
            await refreshServers();
            const enderecos = (data.enderecos || []).join(", ");
            log(
                `Hub local ativo em ${data.host}:${data.porta}` +
                (enderecos ? ` — endereços: ${enderecos}` : "") + ".",
                "ok",
            );
        } catch (error) {
            log(error.message, "error");
        }
    });

    elements.stopHub.addEventListener("click", async () => {
        try {
            await requestJson("/api/conexao/hub/parar", {});
            hubAtivo = false;
            updateHubButtons();
            await refreshServers();
            log("Hub local parado.", "ok");
        } catch (error) {
            log(error.message, "error");
        }
    });

    elements.serverRefresh.addEventListener("click", async () => {
        await refreshServers();
        log("Lista de servidores atualizada.");
    });

    elements.serverDiscover.addEventListener("click", async () => {
        log("Procurando hubs MiniPar na rede local...");
        await refreshServers(true);
        log("Busca na rede concluída.", "ok");
    });

    async function enterHub(host, porta, nome) {
        const data = await action(
            "/api/conexao/conectar",
            { host, porta, nome },
            `Conectado ao hub ${host}:${porta}.`,
        );
        if (data) {
            lastHub = { host, porta, nome };
            userLeft = false;
            rememberServer(host, porta, host);
            startPolling();
        }
        return data;
    }

    function currentName() {
        const nome = (elements.name.value || "").trim();
        if (!nome) {
            log("Informe o nome deste participante.", "error");
            toast("Informe seu nome antes de entrar em um hub.", "error");
            elements.name.focus();
            return "";
        }
        sessionStorage.setItem(CLIENT_NAME_KEY, nome);
        return nome;
    }

    elements.serverList.addEventListener("click", async event => {
        const remover = event.target.closest("[data-host][data-port].connection-server-remove");
        if (remover) {
            forgetServer(remover.getAttribute("data-host"), remover.getAttribute("data-port"));
            serverSignature = "";
            await refreshServers();
            return;
        }
        const escolher = event.target.closest("[data-host][data-port].connection-server-pick");
        if (!escolher || escolher.disabled) return;
        const host = escolher.getAttribute("data-host") || "";
        const porta = Number(escolher.getAttribute("data-port")) || 5010;
        elements.host.value = host;
        elements.port.value = String(porta);
        const nome = currentName();
        if (!nome) return;
        await enterHub(host, porta, nome);
    });

    elements.connect.addEventListener("click", async () => {
        const host = (elements.host.value || "").trim();
        const porta = Number(elements.port.value) || 5010;
        const nome = currentName();
        if (!nome) return;
        await enterHub(host, porta, nome);
    });

    elements.reconnect.addEventListener("click", async () => {
        if (!lastHub) return;
        await enterHub(lastHub.host, lastHub.porta, lastHub.nome);
    });

    function execucaoAtiva() {
        const local = state.execucao_local || {};
        return Boolean(local.ativo && ["preparando", "preparado", "executando"].includes(local.status));
    }

    elements.disconnect.addEventListener("click", async () => {
        if (execucaoAtiva() && !window.confirm("Há uma execução em andamento. Deseja mesmo desligar do hub?")) return;
        userLeft = true;
        lib.markLeft();
        const data = await action("/api/conexao/desligar", {}, "Desligado do hub.");
        if (data) {
            wasOnline = false;
            state = {
                estado: "desconectado",
                peers: [],
                salas: [],
                chat: [],
                solicitacao: null,
                sala: null,
                conectado_com: null,
                hub: null,
            };
            roomsSignature = "";
            lastChatSignature = "";
            lib.markLeft();
            render();
            refreshServers(true);
        }
    });

    elements.createRoom.addEventListener("click", async () => {
        const nome = (elements.roomName.value || "Sala MiniPar").trim();
        const senha = elements.roomPassword.value || "";
        await action(
            "/api/conexao/sala/criar",
            { nome, senha },
            "Sala privada criada. Compartilhe o código com a outra parte.",
        );
    });

    async function joinRoom(codigo, senha = "") {
        const data = await action("/api/conexao/sala/entrar", { codigo, senha }, `Entrou na sala ${codigo}.`);
        if (data) {
            pendingJoin = null;
            elements.joinBox.hidden = true;
            elements.joinPassword.value = "";
        }
        return data;
    }

    elements.joinRoom.addEventListener("click", async () => {
        const codigo = (elements.roomCode.value || "").trim().toUpperCase();
        if (!codigo) {
            log("Informe o código da sala.", "error");
            return;
        }
        // O código pode ser de uma sala com senha: pedimos a senha (pode ficar vazia).
        pendingJoin = { codigo, nome: codigo };
        elements.joinTitle.textContent = `Entrar na sala ${codigo} (senha, se houver)`;
        elements.joinBox.hidden = false;
        elements.joinPassword.value = "";
        elements.joinPassword.focus();
    });

    elements.rooms.addEventListener("click", event => {
        const botao = event.target.closest(".connection-room-join");
        if (!botao || botao.disabled) return;
        const codigo = botao.getAttribute("data-room-code");
        const nome = botao.getAttribute("data-room-name") || codigo;
        if (botao.getAttribute("data-room-locked") === "1") {
            pendingJoin = { codigo, nome };
            elements.joinTitle.textContent = `Entrar na sala ${nome} 🔒`;
            elements.joinBox.hidden = false;
            elements.joinPassword.value = "";
            elements.joinPassword.focus();
            return;
        }
        joinRoom(codigo, "");
    });

    elements.joinConfirm.addEventListener("click", () => {
        if (!pendingJoin) return;
        joinRoom(pendingJoin.codigo, elements.joinPassword.value || "");
    });

    elements.joinPassword.addEventListener("keydown", event => {
        if (event.key === "Enter" && pendingJoin) {
            event.preventDefault();
            joinRoom(pendingJoin.codigo, elements.joinPassword.value || "");
        } else if (event.key === "Escape") {
            elements.joinCancel.click();
        }
    });

    elements.joinCancel.addEventListener("click", () => {
        pendingJoin = null;
        elements.joinBox.hidden = true;
        elements.joinPassword.value = "";
    });

    elements.leaveRoom.addEventListener("click", async () => {
        const sala = state.sala || {};
        const dono = sala.dono_id && sala.dono_id === state.peer_id;
        if (execucaoAtiva() && !window.confirm("Há uma execução em andamento. Deseja mesmo sair da sala?")) return;
        if (dono && !window.confirm("Você é o dono: encerrar a sala remove os outros participantes dela. Continuar?")) return;
        await action(
            "/api/conexao/sala/sair",
            {},
            dono ? "Sala encerrada. De volta à sala pública." : "De volta à sala pública.",
        );
    });

    elements.peers.addEventListener("click", event => {
        const button = event.target.closest("[data-peer-id]");
        if (!button || button.disabled) return;
        const peerId = button.getAttribute("data-peer-id");
        action("/api/conexao/solicitar", { peer_id: peerId }, "Solicitação de conexão enviada.");
    });

    elements.accept.addEventListener("click", async () => {
        const pedido = state.solicitacao;
        if (!pedido) return;
        await action(
            "/api/conexao/responder",
            { request_id: pedido.request_id, aceitar: true },
            "Conexão aceita.",
        );
    });

    elements.reject.addEventListener("click", async () => {
        const pedido = state.solicitacao;
        if (!pedido) return;
        await action(
            "/api/conexao/responder",
            { request_id: pedido.request_id, aceitar: false },
            "Conexão recusada.",
        );
    });

    elements.chatForm.addEventListener("submit", async event => {
        event.preventDefault();
        const texto = elements.chatInput.value.trim();
        if (!texto) return;
        elements.chatInput.value = "";
        const data = await action("/api/conexao/chat", { texto });
        if (data) {
            elements.chatInput.focus();
        } else {
            elements.chatInput.value = texto;
        }
    });

    async function loadProgramContext() {
        if (!program) return;
        try {
            const response = await fetch("/api/test_spec", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename: program }),
            });
            if (!response.ok) return;
            const spec = await response.json();
            elements.programTitle.textContent = spec.titulo || program;
            const multi = spec.multi_computer || {};
            if (!multi.required) return;
            const papeis = (multi.roles || []).join(", ");
            elements.programInfo.textContent =
                `Conexão necessária entre ${multi.count || 2} participantes` +
                (papeis ? ` · papéis: ${papeis}` : "") +
                ". Depois de conectar, volte ao editor e clique em executar.";
        } catch (error) {
            // Contexto é opcional; a tela continua funcional.
        }
    }

    log("Terminal de conexão pronto.");
    Promise.all([loadNetwork(), loadProgramContext()]).then(() => {
        poll();
        startPolling();
        refreshServers(true);
    });
    setInterval(() => {
        if (state.estado === "desconectado" || !state.estado) refreshServers(true);
    }, 15000);
    render();
})();
