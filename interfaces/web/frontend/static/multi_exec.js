(() => {
    "use strict";

    // Execução em par (multicomputador) dentro do editor: envia o convite,
    // carrega o programa de cada lado, coordena preparo/início com o hub e
    // mostra o terminal interativo de altura fixa no lugar das entradas.
    const lib = window.MiniparConexao;
    if (!lib) return;

    const CONEXAO_HANDOFF_KEY = "minipar-conexao-handoff";
    const ENCERRADOS = ["concluido", "erro", "cancelado"];

    document.addEventListener("DOMContentLoaded", () => {
        const el = {
            area: document.getElementById("input-area"),
            terminal: document.getElementById("multi-terminal"),
            status: document.getElementById("multi-terminal-status"),
            output: document.getElementById("multi-terminal-output"),
            form: document.getElementById("multi-terminal-form"),
            input: document.getElementById("multi-terminal-input"),
            cancel: document.getElementById("multi-terminal-cancel"),
            stop: document.getElementById("multi-terminal-stop"),
            close: document.getElementById("multi-terminal-close"),
        };
        if (!el.terminal || !el.output) return;

        let fase = "ocioso"; // ocioso | convidando | preparando | executando | encerrado
        let contexto = null; // { arquivo, papel, parceiro, origem }
        let iniciando = false;
        let paradaAutomatica = false;
        let inicioMs = 0;
        let consoleKey = "";
        let aviso = "";

        function editor() {
            return window.MiniparEditor || null;
        }

        function mostrar(visivel) {
            el.terminal.hidden = !visivel;
            if (el.area) el.area.hidden = visivel;
        }

        function definirStatus(texto, tom = "") {
            el.status.textContent = texto;
            el.status.className = `multi-terminal-status${tom ? ` multi-terminal-${tom}` : ""}`;
        }

        function escapeHtml(value) {
            return String(value ?? "").replace(/[&<>"']/g, character => ({
                "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
            })[character]);
        }

        function escreverConsole(stdout, stderr) {
            const chave = `${stdout.length}|${stderr.length}|${aviso}`;
            if (chave === consoleKey) return;
            consoleKey = chave;
            const perto = el.output.scrollHeight - el.output.scrollTop - el.output.clientHeight < 40;
            el.output.innerHTML = escapeHtml(stdout)
                + (stderr ? `<span class="multi-terminal-stderr">${escapeHtml(stderr)}</span>` : "")
                + (aviso ? `<span class="multi-terminal-aviso">${escapeHtml(aviso)}\n</span>` : "");
            if (perto) el.output.scrollTop = el.output.scrollHeight;
        }

        function botoes() {
            el.cancel.hidden = fase !== "convidando";
            el.stop.hidden = !["preparando", "executando"].includes(fase);
            el.close.hidden = ["preparando", "executando"].includes(fase);
        }

        function limparTerminal() {
            consoleKey = "";
            aviso = "";
            el.output.textContent = "";
            el.input.value = "";
            el.input.disabled = true;
        }

        function fechar() {
            if (["preparando", "executando"].includes(fase)) return;
            fase = "ocioso";
            contexto = null;
            mostrar(false);
            limparTerminal();
            botoes();
        }

        // ------------------------------------------------------ iniciar (convite)
        async function iniciar(arquivo, codigo) {
            const ed = editor();
            const estado = lib.state() || {};
            if (!lib.isRegistered(estado)) {
                try {
                    sessionStorage.setItem(CONEXAO_HANDOFF_KEY, JSON.stringify({
                        file: arquivo, source: codigo, inputs: "",
                    }));
                } catch (error) {
                    // Sem armazenamento, o código volta pelo exemplo.
                }
                if (ed) ed.setStatus("Este programa roda em par — entre em um hub e uma sala para convidar alguém...");
                window.location.href = `/conexao?program=${encodeURIComponent(arquivo)}`;
                return;
            }
            if (["convidando", "preparando", "executando"].includes(fase)) {
                if (ed) ed.setStatus("Já existe uma execução em par em andamento", true);
                return;
            }
            limparTerminal();
            try {
                const data = await lib.post("/api/conexao/execucao/convidar", { filename: arquivo });
                fase = "convidando";
                mostrar(true);
                const n = (data.convite_enviado || {}).destinatarios;
                definirStatus(
                    `Convite enviado${n ? ` a ${n} participante${n > 1 ? "s" : ""}` : ""}. Aguardando o aceite...`,
                    "info",
                );
                aviso = "";
                escreverConsole("", "");
                botoes();
                if (ed) ed.setStatus("Convite de execução enviado");
            } catch (error) {
                if (ed) ed.setStatus(error.message, true);
                fase = "ocioso";
                mostrar(false);
            }
        }

        // ------------------------------------------------------ comecar (aceito)
        async function comecar(multi) {
            const ed = editor();
            if (!ed || !multi || !multi.arquivo) return;
            contexto = multi;
            fase = "preparando";
            iniciando = false;
            paradaAutomatica = false;
            inicioMs = Date.now();
            limparTerminal();
            mostrar(true);
            botoes();
            definirStatus(`Preparando ${multi.arquivo} como ${multi.papel}...`, "info");
            lib.post("/api/conexao/execucao/multi/limpar", {}).catch(() => {});

            let codigo = ed.getCode();
            if (multi.origem !== "iniciador" || ed.getFile() !== multi.arquivo) {
                try {
                    const resposta = await fetch("/api/get_test", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ filename: multi.arquivo }),
                    });
                    const dados = await resposta.json();
                    if (!resposta.ok || typeof dados.code !== "string") {
                        throw new Error(dados.error || "Não foi possível carregar o programa do par.");
                    }
                    codigo = dados.code;
                    ed.setProgram(multi.arquivo, codigo);
                } catch (error) {
                    falhar(error.message);
                    return;
                }
            }
            try {
                await ed.compile();
            } catch (error) {
                // A compilação didática é opcional; o preparo compila de novo.
            }

            let host = "127.0.0.1";
            try {
                const rede = await (await fetch(`/api/conexao/rede?client_id=${encodeURIComponent(lib.clientId())}`)).json();
                if (rede && rede.ip_local) host = rede.ip_local;
            } catch (error) {
                // Mantém o loopback quando a rede não responde.
            }
            try {
                await lib.post("/api/conexao/execucao/preparar", {
                    filename: multi.arquivo,
                    code: codigo,
                    papel: multi.papel,
                    host,
                    timeout: 60,
                    entradas: "",
                });
            } catch (error) {
                falhar(error.message);
                return;
            }
            fase = "executando";
            const parceiro = (multi.parceiro && multi.parceiro.nome) || "o outro lado";
            definirStatus(`${multi.papel} · aguardando ${parceiro} ficar pronto...`, "info");
            ed.setStatus("Execução em par preparada");
        }

        function falhar(mensagem) {
            fase = "encerrado";
            aviso = mensagem;
            definirStatus("Não foi possível executar em par", "erro");
            escreverConsole("", "");
            el.input.disabled = true;
            botoes();
            const ed = editor();
            if (ed) ed.setStatus(mensagem, true);
        }

        // ----------------------------------------------------- orquestração
        async function orquestrar(state) {
            const exec = state.execucao || {};
            const local = state.execucao_local || {};
            const status = String(local.status || "");
            const modo = String(local.modo || "");
            const proc = local.processo || {};
            const parceiro = (contexto && contexto.parceiro && contexto.parceiro.nome) || "o outro lado";

            escreverConsole(proc.stdout || "", proc.stderr || local.erro || "");
            const rodando = Boolean(proc.rodando);
            el.input.disabled = !rodando;
            el.stop.disabled = false;

            if (!local.ativo && fase === "executando" && Date.now() - inicioMs > 5000) {
                encerrar(state, "cancelado");
                return;
            }
            if (status === "preparado" && !iniciando && !paradaAutomatica) {
                const pronto = modo === "escuta" ? Boolean(exec.peer_preparado) : Boolean(exec.peer_pronto);
                if (pronto) {
                    iniciando = true;
                    try {
                        await lib.post("/api/conexao/execucao/iniciar", {});
                    } catch (error) {
                        paradaAutomatica = true;
                        falhar(error.message);
                        return;
                    } finally {
                        iniciando = false;
                    }
                } else {
                    definirStatus(
                        modo === "escuta"
                            ? `${contexto.papel} · aguardando ${parceiro} terminar de preparar...`
                            : `${contexto.papel} · aguardando ${parceiro} abrir a porta...`,
                        "info",
                    );
                }
            }
            if (status === "executando" || rodando) {
                definirStatus(`${contexto.papel} · executando com ${parceiro}`, "ok");
            }
            if (
                !paradaAutomatica
                && local.ativo
                && ["preparando", "preparado", "executando"].includes(status)
                && (exec.parar_solicitado || exec.estado === "erro")
            ) {
                paradaAutomatica = true;
                aviso = exec.erro || exec.motivo_parar || "O outro lado encerrou a execução.";
                try {
                    await lib.post("/api/conexao/execucao/parar", { notificar: false });
                } catch (error) {
                    // O encerramento local segue mesmo sem resposta do servidor.
                }
            }
            if (ENCERRADOS.includes(status) && !rodando) {
                encerrar(state, status);
            }
        }

        function encerrar(state, status) {
            if (fase === "encerrado") return;
            fase = "encerrado";
            const local = state.execucao_local || {};
            const proc = local.processo || {};
            const ok = status === "concluido";
            const codigo = proc.exit_code;
            definirStatus(
                ok ? `Concluído (código ${codigo ?? 0})`
                    : status === "cancelado" ? "Execução encerrada" : `Terminou com erro${codigo != null ? ` (código ${codigo})` : ""}`,
                ok ? "ok" : "erro",
            );
            el.input.disabled = true;
            botoes();
            escreverConsole(proc.stdout || "", proc.stderr || local.erro || "");
            const ed = editor();
            if (ed) {
                const parceiro = (contexto && contexto.parceiro && contexto.parceiro.nome) || "-";
                ed.concluirExecucao({
                    stdout: proc.stdout || "",
                    stderr: proc.stderr || local.erro || aviso || "",
                    exit_code: codigo ?? null,
                    tempo: (Date.now() - inicioMs) / 1000,
                    success: ok,
                    timed_out: false,
                    output_limited: Boolean(proc.output_limited),
                    resumo: `Execução em par · você: ${contexto ? contexto.papel : "-"} · parceiro: ${parceiro}`,
                });
            }
        }

        // ------------------------------------------------------ acompanhamento
        function resultadoConvite(state) {
            const r = state.convite_resultado;
            if (!r) return "O convite foi encerrado.";
            if (r.resultado === "recusado") return `${r.nome || "O participante"} recusou o convite.`;
            if (r.resultado === "todos_recusaram") return "Todos recusaram o convite.";
            if (r.resultado === "expirado") return "O convite expirou sem resposta.";
            if (r.resultado === "todos_sairam") return "Os convidados saíram da sala.";
            return "O convite foi encerrado.";
        }

        lib.subscribe(state => {
            if (state.execucao_multi && !["preparando", "executando"].includes(fase)) {
                comecar(state.execucao_multi);
                return;
            }
            if (fase === "convidando") {
                if (!state.convite_enviado && !state.execucao_multi) {
                    fase = "encerrado";
                    definirStatus(resultadoConvite(state), "erro");
                    botoes();
                }
                return;
            }
            if (["preparando", "executando"].includes(fase) && contexto) {
                orquestrar(state);
            }
        });

        // ---------------------------------------------------------------- ações
        el.cancel.addEventListener("click", async () => {
            try {
                await lib.post("/api/conexao/execucao/convite/cancelar", {});
            } catch (error) {
                // O hub encerra o convite de qualquer forma.
            }
            fase = "ocioso";
            mostrar(false);
            botoes();
            const ed = editor();
            if (ed) ed.setStatus("Convite cancelado");
        });

        el.stop.addEventListener("click", async () => {
            paradaAutomatica = true;
            aviso = "Execução encerrada por você.";
            try {
                await lib.post("/api/conexao/execucao/parar", {
                    motivo: "Execução encerrada pelo usuário.",
                    notificar: true,
                });
            } catch (error) {
                aviso = error.message;
            }
        });

        el.close.addEventListener("click", fechar);

        el.form.addEventListener("submit", async event => {
            event.preventDefault();
            if (el.input.disabled) return;
            const texto = el.input.value;
            el.input.value = "";
            try {
                await lib.post("/api/conexao/execucao/entrada", { texto });
            } catch (error) {
                el.input.value = texto;
                aviso = error.message;
                escreverConsole("", "");
            }
            el.input.focus();
        });

        window.MiniparMulti = { iniciar, fechar, fase: () => fase };
    });
})();
