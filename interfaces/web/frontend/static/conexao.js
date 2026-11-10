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
        execution: document.getElementById("connection-execution"),
        execStatus: document.getElementById("connection-exec-status"),
        execWarning: document.getElementById("connection-exec-warning"),
        execRole: document.getElementById("connection-exec-role"),
        execHost: document.getElementById("connection-exec-host"),
        execPort: document.getElementById("connection-exec-port"),
        execTimeout: document.getElementById("connection-exec-timeout"),
        execInputs: document.getElementById("connection-exec-inputs"),
        execPrepare: document.getElementById("connection-exec-prepare"),
        execStart: document.getElementById("connection-exec-start"),
        execStop: document.getElementById("connection-exec-stop"),
        execState: document.getElementById("connection-exec-state"),
        execOutput: document.getElementById("connection-exec-output"),
        execError: document.getElementById("connection-exec-error"),
        execHint: document.getElementById("connection-exec-hint"),
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
    let executionHandoff = null;
    let execStarting = false;
    let execStopRequested = false;
    let freeSuggestedPort = "";
    let hubAtivo = false;
    let serverSignature = "";

    function readConexaoHandoff() {
        try {
            const raw = sessionStorage.getItem(CONEXAO_HANDOFF_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            return null;
        }
    }

    executionHandoff = readConexaoHandoff();

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
                '<li class="connection-empty">Nenhum servidor salvo. Inicie um hub local ou conecte a um endereço.</li>';
            return;
        }
        elements.serverList.innerHTML = lista.map(item => {
            const host = escapeHtml(item.host || "");
            const porta = Number(item.porta) || 0;
            const nome = escapeHtml(item.nome || item.host || "Servidor");
            const ativo = Boolean(item.ativo);
            const local = item.local ? " · local" : "";
            return `<li class="connection-server ${ativo ? "connection-server-online" : "connection-server-offline"}">
                <button type="button" class="connection-server-pick" data-host="${host}" data-port="${porta}" title="Usar este servidor">
                    <span class="connection-server-name">${nome}</span>
                    <small>${host}:${porta}${local} · ${ativo ? "disponível" : "sem resposta"}</small>
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
        });
    }

    function applyState(data) {
        if (data && typeof data === "object" && "estado" in data) {
            state = { ...state, ...data };
        }
        applyEvents(data && data.eventos);
        render();
    }

    let execAutoBlocked = false;

    function isAutoExecution() {
        return Boolean(programSpec && programSpec.multi_computer && programSpec.multi_computer.auto_execution);
    }

    function roleMode(papel) {
        const multi = (programSpec && programSpec.multi_computer) || {};
        const modes = multi.role_modes || {};
        if (modes[papel]) return modes[papel];
        const canal = (multi.channels || [])[0] || {};
        if (canal.conecta === papel) return "conecta";
        if (canal.escuta === papel) return "escuta";
        return "";
    }

    function handoffMatchesProgram() {
        if (!executionHandoff || typeof executionHandoff.source !== "string") return false;
        if (!program) return true;
        return !executionHandoff.file || executionHandoff.file === program;
    }

    function renderExecution() {
        if (!elements.execution) return;
        if (!programSpec || !programSpec.multi_computer) {
            elements.execution.hidden = true;
            return;
        }
        const multi = programSpec.multi_computer;
        const auto = Boolean(multi.auto_execution);
        elements.execution.hidden = false;
        elements.execWarning.hidden = auto;
        if (!auto) {
            elements.execWarning.textContent = multi.instrucoes || "Execução automática indisponível para este programa.";
            elements.execPrepare.disabled = true;
            elements.execStart.disabled = true;
            elements.execStop.disabled = true;
            elements.execStatus.textContent = "MANUAL";
            elements.execHint.textContent = "Use um par com canal declarativo, como t01_multiterminal.";
            return;
        }

        const connected = state.estado === "conectado";
        const exec = state.execucao || {};
        const local = state.execucao_local || {};
        const status = String(local.status || "");
        const papel = elements.execRole.value || exec.papel || "";
        const modo = roleMode(papel);
        const locked = ["preparando", "preparado", "executando", "parando"].includes(status);
        const preparado = Boolean(local.compilado) && status === "preparado";
        const active = Boolean(local.ativo);
        const podeIniciar = preparado
            && !execStarting
            && !execAutoBlocked
            && (modo === "escuta" ? Boolean(exec.peer_preparado) : Boolean(exec.peer_pronto));
        const podeParar = active && ["preparando", "preparado", "executando"].includes(status);

        elements.execRole.disabled = locked || !connected;
        elements.execHost.disabled = locked || !connected || modo !== "escuta";
        elements.execPort.disabled = locked || !connected || modo !== "escuta";
        elements.execTimeout.disabled = locked;
        elements.execInputs.disabled = locked;
        elements.execPrepare.disabled = !connected || locked;
        elements.execStart.disabled = !connected || !podeIniciar;
        elements.execStop.disabled = !connected || !podeParar;

        const protocolo = String(exec.estado || "");
        elements.execStatus.textContent = connected
            ? (status || protocolo || "OCIOSO").toUpperCase()
            : "DESCONECTADO";
        elements.execHint.textContent = modo === "escuta"
            ? "Este lado abre a porta e avisa quando estiver pronto."
            : "Este lado aguarda a porta do outro lado para iniciar.";

        const proc = local.processo || {};
        elements.execState.textContent = [
            `Papel: ${papel || "-"} (${modo || "-"})`,
            `Parceiro: ${(exec.peer && exec.peer.papel) || "-"} (${(exec.peer && exec.peer.modo) || "-"})`,
            `Porta: ${local.porta || exec.porta || "-"}`,
            `Peer preparado: ${exec.peer_preparado ? "sim" : "não"}`,
            `Peer pronto: ${exec.peer_pronto ? "sim" : "não"}`,
            `Processo: ${proc.rodando ? "em execução" : active ? "encerrado" : "não iniciado"}`,
        ].join("\n");
        elements.execOutput.textContent = proc.stdout || "";
        elements.execError.textContent = proc.stderr || local.erro || exec.erro || "";

        if (connected && preparado && !execStarting && !execAutoBlocked) {
            const deveIniciar = modo === "escuta"
                ? Boolean(exec.peer_preparado)
                : Boolean(exec.peer_pronto);
            if (deveIniciar) startExecution(true);
        }
        if (!execStopRequested && active
            && ["preparando", "preparado", "executando"].includes(status)
            && (exec.parar_solicitado || exec.estado === "erro")) {
            execStopRequested = true;
            stopExecution(false);
        }
    }

    async function prepareExecution() {
        if (!isAutoExecution()) return;
        const multi = programSpec.multi_computer;
        const canal = (multi.channels || [])[0];
        const papel = elements.execRole.value;
        if (!canal || !papel) {
            log("Escolha um papel para preparar a execução.", "error");
            return;
        }
        const payload = {
            filename: program,
            papel,
            canal: {
                nome: canal.nome,
                conecta: canal.conecta,
                escuta: canal.escuta,
            },
            host: (elements.execHost.value || "").trim(),
            porta: elements.execPort.value ? Number(elements.execPort.value) : null,
            entradas: elements.execInputs.value || "",
            timeout: Number(elements.execTimeout.value) || 60,
        };
        if (handoffMatchesProgram()) payload.code = executionHandoff.source;
        execAutoBlocked = false;
        execStopRequested = false;
        elements.execPrepare.disabled = true;
        const data = await action("/api/conexao/execucao/preparar", payload);
        if (!data) {
            elements.execPrepare.disabled = false;
            return;
        }
        const local = data.execucao_local || {};
        if (local.erro) {
            log(local.erro, "error");
        } else {
            log("Execução preparada; aguardando o outro lado.", "ok");
        }
    }

    async function startExecution(auto = false) {
        if (execStarting || (auto && execAutoBlocked)) return;
        execStarting = true;
        try {
            const data = await requestJson("/api/conexao/execucao/iniciar", {});
            applyState(data);
            log(auto ? "Execução iniciada automaticamente." : "Execução iniciada.", "ok");
        } catch (error) {
            if (auto) {
                execAutoBlocked = true;
                log(`Não foi possível iniciar automaticamente: ${error.message}`, "error");
            } else {
                log(error.message, "error");
            }
        } finally {
            execStarting = false;
        }
    }

    async function stopExecution(notificar = true) {
        try {
            const data = await requestJson("/api/conexao/execucao/parar", {
                motivo: notificar ? "Execução encerrada pelo usuário." : "Execução encerrada pelo parceiro.",
                notificar,
            });
            applyState(data);
            if (notificar) log("Execução encerrada.", "ok");
        } catch (error) {
            if (notificar) log(error.message, "error");
        }
    }

    function render() {
        const connected = state.estado === "conectado";
        const registered = state.estado === "registrado" || connected;
        const partner = state.conectado_com;

        elements.status.textContent = connected
            ? `CONECTADO${partner ? ` · ${partner.nome}` : ""}`
            : registered ? "NO HUB" : "DESCONECTADO";
        elements.status.classList.toggle("connection-status-online", connected);
        elements.status.classList.toggle("connection-status-hub", registered && !connected);

        elements.disconnect.hidden = !((state.hub) || registered);

        const sala = state.sala;
        elements.room.textContent = sala
            ? `${sala.nome} [${sala.codigo}] · ${sala.lotacao}${sala.maximo ? `/${sala.maximo}` : ""}`
            : "Sem sala";

        renderPeers();
        renderRequest();
        renderChat(connected, partner);
        renderExecution();
    }

    function renderPeers() {
        const peers = Array.isArray(state.peers) ? state.peers : [];
        if (!peers.length) {
            elements.peers.innerHTML = '<li class="connection-empty">Nenhum participante disponível nesta sala.</li>';
            return;
        }
        const connected = state.estado === "conectado";
        elements.peers.innerHTML = peers.map(peer => {
            const busy = peer.estado === "conectado";
            const disabled = busy || connected;
            return `<li class="connection-peer">
                <span class="connection-peer-name"><b>${escapeHtml(peer.nome)}</b><small>${escapeHtml(peer.id)}${busy ? " · ocupado" : ""}</small></span>
                <button type="button" class="button button-outline connection-peer-connect" data-peer-id="${escapeHtml(peer.id)}" ${disabled ? "disabled" : ""}>Conectar</button>
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
        elements.requestText.textContent = `${pedido.nome || "Participante"} (${pedido.de || "?"}) quer se conectar com você.`;
    }

    function renderChat(connected, partner) {
        elements.chatInput.disabled = !connected;
        elements.chatSend.disabled = !connected;
        elements.chatState.textContent = connected
            ? `conversando com ${partner ? partner.nome : "parceiro"}`
            : "aguardando conexão";

        const mensagens = Array.isArray(state.chat) ? state.chat : [];
        const signature = mensagens.map(item => `${item.hora}-${item.proprio ? 1 : 0}-${item.texto}`).join("|");
        if (signature !== lastChatSignature) {
            lastChatSignature = signature;
            if (!mensagens.length) {
                elements.chat.innerHTML = '<p class="connection-empty">O chat fica disponível após o aceite dos dois lados.</p>';
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

    elements.serverList.addEventListener("click", async event => {
        const remover = event.target.closest("[data-host][data-port].connection-server-remove");
        if (remover) {
            forgetServer(remover.getAttribute("data-host"), remover.getAttribute("data-port"));
            serverSignature = "";
            await refreshServers();
            return;
        }
        const escolher = event.target.closest("[data-host][data-port].connection-server-pick");
        if (!escolher) return;
        elements.host.value = escolher.getAttribute("data-host") || "";
        elements.port.value = escolher.getAttribute("data-port") || "";
        log(`Servidor selecionado: ${elements.host.value}:${elements.port.value}.`);
    });

    elements.connect.addEventListener("click", async () => {
        const host = (elements.host.value || "").trim();
        const porta = Number(elements.port.value) || 5010;
        const nome = (elements.name.value || "").trim();
        if (!nome) {
            log("Informe o nome deste participante.", "error");
            return;
        }
        sessionStorage.setItem(CLIENT_NAME_KEY, nome);
        const data = await action(
            "/api/conexao/conectar",
            { host, porta, nome },
            `Conectado ao hub ${host}:${porta}.`,
        );
        if (data) {
            rememberServer(host, porta, host);
            await refreshServers();
            startPolling();
        }
    });

    elements.disconnect.addEventListener("click", async () => {
        const data = await action("/api/conexao/desligar", {}, "Desligado do hub.");
        if (data) {
            state = {
                estado: "desconectado",
                peers: [],
                chat: [],
                solicitacao: null,
                sala: null,
                conectado_com: null,
                hub: null,
            };
            render();
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

    elements.joinRoom.addEventListener("click", async () => {
        const codigo = (elements.roomCode.value || "").trim().toUpperCase();
        const senha = elements.joinPassword.value || "";
        if (!codigo) {
            log("Informe o código da sala.", "error");
            return;
        }
        await action("/api/conexao/sala/entrar", { codigo, senha }, `Entrou na sala ${codigo}.`);
    });

    elements.leaveRoom.addEventListener("click", async () => {
        await action("/api/conexao/sala/sair", {}, "De volta à sala pública.");
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

    elements.execPrepare.addEventListener("click", () => {
        prepareExecution();
    });

    elements.execStart.addEventListener("click", () => {
        startExecution(false);
    });

    elements.execStop.addEventListener("click", () => {
        execStopRequested = true;
        stopExecution(true);
    });

    elements.execRole.addEventListener("change", () => {
        if (roleMode(elements.execRole.value) === "escuta"
            && !elements.execPort.value
            && freeSuggestedPort) {
            elements.execPort.value = freeSuggestedPort;
        }
        renderExecution();
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
            programSpec = spec;
            elements.programTitle.textContent = spec.titulo || program;
            const multi = spec.multi_computer || {};
            if (!multi.required) return;

            const papeis = (multi.roles || []).join(", ");
            const execucao = multi.auto_execution
                ? "Execução automática disponível."
                : "Execução automática indisponível.";
            elements.programInfo.textContent =
                `Conexão necessária entre ${multi.count || 2} participantes` +
                (papeis ? ` · papéis: ${papeis}` : "") +
                `. ${execucao}`;

            const roles = Array.isArray(multi.roles) ? multi.roles : [];
            elements.execRole.innerHTML = roles.map(papel => (
                `<option value="${escapeHtml(papel)}">${escapeHtml(papel)} (${escapeHtml(roleMode(papel))})</option>`
            )).join("");
            let indice = 0;
            if (/servidor|server|_2\b/i.test(program)) {
                indice = Math.min(1, Math.max(0, roles.length - 1));
            }
            const papelPadrao = roles[indice] || "";
            if (papelPadrao) elements.execRole.value = papelPadrao;
            if (handoffMatchesProgram()) {
                elements.execInputs.value = executionHandoff.inputs || "";
            }

            try {
                const redeResponse = await fetch("/api/conexao/rede");
                if (redeResponse.ok) {
                    const rede = await redeResponse.json();
                    if (rede.ip_local) elements.execHost.value = rede.ip_local;
                    if (rede.porta_livre) {
                        freeSuggestedPort = String(rede.porta_livre);
                        if (roleMode(papelPadrao) === "escuta") {
                            elements.execPort.value = freeSuggestedPort;
                        }
                    }
                }
            } catch (error) {
                // O host manual continua disponível se a rede não responder.
            }
            renderExecution();
        } catch (error) {
            // Contexto é opcional; a tela continua funcional.
        }
    }

    log("Terminal de conexão pronto.");
    Promise.all([loadNetwork(), loadProgramContext()]).then(() => {
        poll();
        startPolling();
    });
})();
