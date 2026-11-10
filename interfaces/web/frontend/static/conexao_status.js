(() => {
    "use strict";

    // Biblioteca compartilhada: descreve o estado da conexão (hub/sala/parceiro)
    // com o mesmo texto e a mesma cor em todas as páginas e mantém um único
    // polling do estado quando a página não tem o seu próprio.
    if (window.MiniparConexao) return;

    const CLIENT_KEY = "minipar-conexao-client";
    const ONLINE_KEY = "minipar-conexao-online";
    const PUBLICA = "publica";
    const POLL_INTERVAL = 1000;

    const listeners = new Set();
    let current = null;
    let timer = null;
    let polling = false;
    let fechaRef = null;

    function storageGet(key) {
        try {
            return sessionStorage.getItem(key) || "";
        } catch (error) {
            return "";
        }
    }

    function storageSet(key, value) {
        try {
            sessionStorage.setItem(key, value);
        } catch (error) {
            // Armazenamento indisponível: o estado segue funcionando sem memória.
        }
    }

    function clientId() {
        return storageGet(CLIENT_KEY);
    }

    function salaTexto(sala) {
        if (!sala || sala.codigo === PUBLICA) return "Sala pública";
        const maximo = sala.maximo ? `/${sala.maximo}` : "";
        return `${sala.com_senha ? "🔒 " : ""}${sala.nome} (${sala.lotacao}${maximo})`;
    }

    function salaCurta(sala) {
        if (!sala || sala.codigo === PUBLICA) return "Sala pública";
        return `${sala.com_senha ? "🔒 " : ""}${sala.nome}`;
    }

    function isRegistered(state) {
        return Boolean(state) && ["registrado", "conectado"].includes(state.estado);
    }

    function describe(state) {
        const atual = state || {};
        const registered = isRegistered(atual);
        const connected = atual.estado === "conectado";
        const perdida = !registered && storageGet(ONLINE_KEY) === "1";
        const sala = atual.sala;
        const publica = !sala || sala.codigo === PUBLICA;
        const dono = Boolean(sala && atual.peer_id && sala.dono_id === atual.peer_id);
        const local = atual.execucao_local || {};
        const parceiro = atual.conectado_com;
        const hub = atual.hub ? `${atual.hub.host}:${atual.hub.porta}` : "hub";

        let texto;
        let curto;
        let tom;
        if (perdida) {
            texto = "CONEXÃO PERDIDA · o hub não está respondendo";
            curto = "Conexão perdida";
            tom = "lost";
        } else if (!registered) {
            texto = "DESCONECTADO · escolha um hub na rede";
            curto = "Sem hub";
            tom = "off";
        } else if (connected) {
            texto = `CONECTADO${parceiro ? ` · ${parceiro.nome}` : ""} · Hub ${hub} · ${salaTexto(sala)}`;
            curto = `Conectado${parceiro ? ` a ${parceiro.nome}` : ""} · ${salaCurta(sala)}`;
            tom = "online";
        } else {
            texto = `NO HUB · Hub ${hub} · ${salaTexto(sala)}`;
            if (!publica && sala.lotacao < (sala.maximo || 2)) texto += " · aguardando participante";
            curto = `No hub ${atual.hub ? atual.hub.host : ""} · ${salaCurta(sala)}`.replace("  ", " ");
            tom = "hub";
        }
        if (registered && !publica && dono) texto += " · você é o dono";
        const executando = registered && local.ativo && local.status === "executando";
        if (executando) {
            texto += " · executando";
            curto += " · executando";
        }

        let restante = null;
        if (registered && sala && sala.fecha_em != null) {
            if (!fechaRef || fechaRef.codigo !== sala.codigo || fechaRef.base !== sala.fecha_em) {
                fechaRef = { codigo: sala.codigo, base: sala.fecha_em, t: Date.now() };
            }
            restante = Math.max(0, fechaRef.base - Math.floor((Date.now() - fechaRef.t) / 1000));
            tom = "warn";
            curto = `Sala fecha em ${restante}s`;
        } else {
            fechaRef = null;
        }
        return { texto, curto, tom, restante, registered, connected, perdida, publica, dono };
    }

    function markLeft() {
        storageSet(ONLINE_KEY, "0");
    }

    function publish(state) {
        if (!state || typeof state !== "object" || state.success === false) return;
        current = state;
        if (isRegistered(state)) storageSet(ONLINE_KEY, "1");
        listeners.forEach(listener => {
            try {
                listener(state);
            } catch (error) {
                // Um ouvinte com defeito não pode derrubar os demais.
            }
        });
    }

    function subscribe(listener) {
        listeners.add(listener);
        if (current) listener(current);
        return () => listeners.delete(listener);
    }

    async function refresh() {
        const id = clientId();
        if (!id) {
            publish({ estado: "desconectado", peers: [], chat: [], convites: [] });
            return;
        }
        if (polling) return;
        polling = true;
        try {
            const response = await fetch(`/api/conexao/estado?client_id=${encodeURIComponent(id)}`);
            if (response.ok) publish(await response.json());
        } catch (error) {
            // Servidor indisponível: mantém o último estado conhecido.
        } finally {
            polling = false;
        }
    }

    function start() {
        if (timer) return;
        refresh();
        timer = setInterval(refresh, POLL_INTERVAL);
    }

    async function post(path, payload) {
        const response = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ client_id: clientId(), ...(payload || {}) }),
        });
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = { success: false, error: "Resposta inválida do servidor." };
        }
        if (!response.ok || data.success === false) {
            throw new Error(data.error || "Falha na operação.");
        }
        publish(data);
        return data;
    }

    window.MiniparConexao = {
        clientId,
        describe,
        isRegistered,
        markLeft,
        publish,
        subscribe,
        refresh,
        start,
        post,
        state: () => current,
    };
})();
