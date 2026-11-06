/* Segunda interface Web do MiniPar 2026.2 — lógica da página didática. */
(function () {
    "use strict";

    const DEFAULT_PROGRAM = `# Bem-vindo ao MiniPar Didático!
# Clique nas abas para ver cada fase do compilador.

seq {
    var largura = 4;
    var altura = 3;
    var area = largura * altura;
    print("Area:", area);

    if (area > 10) {
        print("Sala grande");
    } else {
        print("Sala pequena");
    }
}
`;

    const state = {
        analysis: null,
        lastCode: null,
        loading: false,
        pending: null,
        astRenderer: null,
        diagnosticLines: new Set(),
        activeTab: "tokens",
    };

    const $ = (selector) => document.querySelector(selector);
    const editor = $("#editor");
    const lineNumbers = $("#line-numbers");
    const diagnosticsBox = $("#diagnostics");
    const statusText = $("#status-text");
    const cursorPos = $("#cursor-pos");

    const KEYWORDS = new Set([
        "SEQ", "PAR", "fork", "join", "em", "core", "host", "c_channel",
        "class", "extends", "new", "self", "def", "func", "return", "var",
        "print", "input", "if", "elif", "else", "while", "for", "in",
        "break", "continue", "and", "or", "not", "true", "false",
        "bool", "int", "float", "string", "char", "list", "void",
    ]);

    const TAC_KEYWORDS = new Set([
        "if", "goto", "print", "call", "param", "ret", "fork", "join",
        "par_begin", "par_end", "endfunc", "func", "WHILE", "ENDWHILE",
        "IF", "ENDIF", "ELSE", "ELSEIF", "source", "var", "const",
    ]);

    const CXX_KEYWORDS = new Set([
        "int", "double", "float", "bool", "char", "void", "long", "short",
        "unsigned", "signed", "auto", "const", "constexpr", "static",
        "class", "struct", "public", "private", "protected", "using",
        "namespace", "std", "string", "vector", "if", "else", "while",
        "for", "return", "true", "false", "nullptr", "include", "define",
        "template", "typename", "inline", "virtual", "override", "new",
        "delete", "this", "break", "continue", "switch", "case", "default",
    ]);

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function setStatus(text, kind) {
        statusText.textContent = text;
        statusText.className = "status-text" + (kind ? " " + kind : "");
    }

    function setActiveTab(name) {
        state.activeTab = name;
        document.querySelectorAll(".tab").forEach((tab) => {
            tab.classList.toggle("active", tab.dataset.tab === name);
        });
        document.querySelectorAll(".panel").forEach((panel) => {
            panel.classList.toggle("active", panel.id === "panel-" + name);
        });
    }

    /* ------------------------------ Editor ------------------------------ */
    function updateLineNumbers() {
        const total = editor.value.split("\n").length;
        let html = "";
        for (let index = 1; index <= total; index += 1) {
            const isError = state.diagnosticLines.has(index);
            html += `<span class="ln${isError ? " error" : ""}" data-line="${index}">${index}</span>`;
        }
        lineNumbers.innerHTML = html;
        syncScroll();
    }

    function syncScroll() {
        lineNumbers.scrollTop = editor.scrollTop;
    }

    function updateCursor() {
        const position = editor.selectionStart;
        const before = editor.value.slice(0, position);
        const lines = before.split("\n");
        const line = lines.length;
        const column = lines[lines.length - 1].length + 1;
        cursorPos.textContent = `Ln ${line}, Col ${column}`;
    }

    function invalidateAnalysis() {
        state.analysis = null;
        state.lastCode = null;
        state.diagnosticLines = new Set();
        updateLineNumbers();
    }

    function focusLine(line, column) {
        const lines = editor.value.split("\n");
        let offset = 0;
        for (let index = 0; index < Math.min(line - 1, lines.length); index += 1) {
            offset += lines[index].length + 1;
        }
        const target = offset + Math.max(0, (column || 1) - 1);
        editor.focus();
        editor.setSelectionRange(target, target);
        const lineHeight = parseFloat(getComputedStyle(editor).lineHeight) || 22;
        editor.scrollTop = Math.max(0, (line - 2) * lineHeight);
        syncScroll();
        updateCursor();
    }

    /* --------------------------- Diagnostics ---------------------------- */
    function renderDiagnostics(diagnostics, success) {
        state.diagnosticLines = new Set(
            (diagnostics || []).filter((item) => item.line).map((item) => item.line)
        );
        updateLineNumbers();

        if (!diagnostics || diagnostics.length === 0) {
            diagnosticsBox.classList.add("hidden");
            diagnosticsBox.innerHTML = "";
            return;
        }

        diagnosticsBox.classList.remove("hidden");
        diagnosticsBox.innerHTML = diagnostics
            .map((item) => {
                const location = `Linha ${item.line ?? "?"}, coluna ${item.column ?? "?"}`;
                const severity = item.severity === "warning" ? "Aviso" : "Erro";
                return `<div class="diagnostic-item" data-line="${item.line || 1}" data-column="${item.column || 1}">
                    <span class="diagnostic-loc">${escapeHtml(location)}</span>
                    <span><strong>${severity}:</strong> ${escapeHtml(item.message)}</span>
                </div>`;
            })
            .join("");

        diagnosticsBox.querySelectorAll(".diagnostic-item").forEach((item) => {
            item.addEventListener("click", () => {
                focusLine(Number(item.dataset.line), Number(item.dataset.column));
            });
        });

        if (!success) {
            setStatus(`${diagnostics.length} diagnóstico(s). Clique para ir à linha.`, "error");
        }
    }

    /* ----------------------------- Analysis ----------------------------- */
    async function ensureAnalysis(force) {
        const code = editor.value;
        if (!force && state.analysis && state.lastCode === code) {
            return state.analysis;
        }
        if (state.loading && state.pending) {
            return state.pending;
        }

        state.loading = true;
        setStatus("Analisando o programa…", "busy");
        state.pending = (async () => {
            try {
                const response = await fetch("/api/analisar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code }),
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Falha ao analisar o programa.");
                }
                state.analysis = data;
                state.lastCode = code;
                renderDiagnostics(data.diagnosticos, data.success);
                if (data.success) {
                    const tokenCount = data.tokens.length;
                    setStatus(`Análise concluída: ${tokenCount} tokens, TAC e C++ gerados.`, "ok");
                }
                return data;
            } catch (error) {
                state.analysis = null;
                setStatus(error.message, "error");
                return null;
            } finally {
                state.loading = false;
                state.pending = null;
            }
        })();
        return state.pending;
    }

    /* ------------------------------ Tokens ------------------------------ */
    function tokenClass(token) {
        const type = token.type;
        if (
            [
                "SEQ", "PAR", "FORK", "JOIN", "EM", "CORE", "HOST", "C_CHANNEL",
                "CLASS", "EXTENDS", "NEW", "SELF", "DEF", "VAR", "RETURN",
                "PRINT", "INPUT", "IF", "ELIF", "ELSE", "WHILE", "FOR", "IN",
                "BREAK", "CONTINUE", "AND", "OR", "NOT", "TYPE",
            ].includes(type)
        ) {
            return "keyword";
        }
        if (type === "IDENTIFIER" && ["seq", "par"].includes(String(token.lexeme))) {
            return "keyword";
        }
        if (type.includes("LITERAL")) return "literal";
        if (type === "IDENTIFIER") return "identifier";
        if (["NEWLINE", "INDENT", "DEDENT", "END_OF_FILE"].includes(type)) {
            return "structure";
        }
        return "operator";
    }

    function renderTokens() {
        const data = state.analysis;
        if (!data) return;
        const filter = ($("#tokens-filter").value || "").toLowerCase();
        const tokens = data.tokens.filter(
            (token) =>
                !filter ||
                token.type.toLowerCase().includes(filter) ||
                String(token.lexeme).toLowerCase().includes(filter)
        );
        $("#tokens-summary").textContent =
            `${data.tokens.length} token(s) no total · ${tokens.length} exibido(s).`;

        const body = $("#tokens-body");
        if (tokens.length === 0) {
            body.innerHTML = '<tr class="empty-row"><td colspan="6">Nenhum token corresponde ao filtro.</td></tr>';
            return;
        }
        body.innerHTML = tokens
            .map((token, index) => {
                const value = token.value === null || token.value === undefined ? "" : String(token.value);
                return `<tr>
                    <td class="mono">${index + 1}</td>
                    <td><span class="token-type ${tokenClass(token)}">${escapeHtml(token.type)}</span></td>
                    <td class="lexeme-cell">${escapeHtml(token.lexeme)}</td>
                    <td class="mono">${token.line}</td>
                    <td class="mono">${token.column}</td>
                    <td class="mono">${escapeHtml(value)}</td>
                </tr>`;
            })
            .join("");
    }

    /* -------------------------------- AST ------------------------------- */
    function renderAst() {
        const data = state.analysis;
        if (!data || !data.ast) return;
        const renderer = state.astRenderer;
        if (!renderer) return;
        if (!data.ast.tipo) {
            renderer.showPlaceholder("A AST não pôde ser construída.");
            return;
        }
        const root = window.MiniParAST.buildNode(data.ast);
        renderer.show(root);
    }

    /* ----------------------------- Semantica ---------------------------- */
    function renderSemantica() {
        const data = state.analysis;
        if (!data) return;
        const container = $("#semantica-content");
        const scopes = (data.tabela_simbolos && data.tabela_simbolos.scopes) || [];
        const totalSymbols = scopes.reduce((total, scope) => total + scope.symbols.length, 0);
        $("#semantica-summary").textContent =
            `${scopes.length} escopo(s) · ${totalSymbols} símbolo(s) · ${data.diagnosticos.length} diagnóstico(s).`;

        const parts = [];

        if (data.diagnosticos.length === 0) {
            parts.push(
                '<div class="diagnostic-card ok"><strong>Sem erros semânticos.</strong> Os tipos e escopos estão consistentes.</div>'
            );
        } else {
            parts.push(
                '<div class="diagnostics-list">' +
                    data.diagnosticos
                        .map(
                            (item) =>
                                `<div class="diagnostic-card"><strong>Linha ${item.line ?? "?"}:</strong> ${escapeHtml(item.message)}</div>`
                        )
                        .join("") +
                    "</div>"
            );
        }

        for (const scope of scopes) {
            if (!scope.symbols || scope.symbols.length === 0) continue;
            const rows = scope.symbols
                .map(
                    (symbol) => `<tr>
                        <td class="mono"><strong>${escapeHtml(symbol.name)}</strong></td>
                        <td>${escapeHtml(symbol.category || "")}</td>
                        <td><span class="type-chip">${escapeHtml(symbol.type || "?")}</span></td>
                        <td class="mono">${symbol.line ?? ""}</td>
                        <td class="mono">${escapeHtml(symbol.scope || "")}</td>
                    </tr>`
                )
                .join("");
            parts.push(`<div class="scope-card">
                <header><span>Escopo: ${escapeHtml(scope.path || scope.name)}</span><span>${scope.symbols.length} símbolo(s)</span></header>
                <table class="data-table">
                    <thead><tr><th>Nome</th><th>Categoria</th><th>Tipo</th><th>Linha</th><th>Escopo</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`);
        }

        if (totalSymbols === 0) {
            parts.push('<div class="empty-note">Nenhum símbolo declarado neste programa.</div>');
        }

        container.innerHTML = parts.join("");
    }

    /* -------------------------------- TAC ------------------------------- */
    function renderTac() {
        const data = state.analysis;
        if (!data) return;
        const lines = (data.tac || "").split("\n");
        const instructionCount = lines.filter((line) => line.trim() && !line.trim().startsWith("#")).length;
        $("#tac-summary").textContent = `${instructionCount} instrução(ões) de três endereços.`;
        $("#tac-code").innerHTML = data.tac
            ? highlightCode(data.tac, "tac")
            : '<span class="placeholder-text">O TAC não foi gerado.</span>';
    }

    /* -------------------------------- C++ ------------------------------- */
    function renderCpp() {
        const data = state.analysis;
        if (!data) return;
        const lines = (data.cpp || "").split("\n").length;
        $("#cpp-summary").textContent = `${lines} linha(s) de C++17 gerado.`;
        $("#cpp-code").innerHTML = data.cpp
            ? highlightCode(data.cpp, "cpp")
            : '<span class="placeholder-text">O código C++ não foi gerado.</span>';
    }

    function highlightCode(text, language) {
        const lines = text.split("\n");
        return lines
            .map((line, index) => {
                const number = `<span class="ln">${index + 1}</span>`;
                return `<span class="code-line">${number}${highlightLine(line, language)}</span>`;
            })
            .join("");
    }

    function highlightLine(line, language) {
        const trimmed = line.trimStart();
        if (language === "tac" && trimmed.startsWith("#")) {
            return `<span class="com">${escapeHtml(line)}</span>`;
        }
        if (language === "cpp" && trimmed.startsWith("//")) {
            return `<span class="com">${escapeHtml(line)}</span>`;
        }

        let output = "";
        let index = 0;
        while (index < line.length) {
            const char = line[index];
            if (char === '"' || char === "'") {
                const quote = char;
                let end = index + 1;
                while (end < line.length) {
                    if (line[end] === "\\") {
                        end += 2;
                        continue;
                    }
                    if (line[end] === quote) {
                        end += 1;
                        break;
                    }
                    end += 1;
                }
                output += `<span class="str">${escapeHtml(line.slice(index, end))}</span>`;
                index = end;
            } else if (/[0-9]/.test(char) && (index === 0 || !/[\w.]/.test(line[index - 1]))) {
                let end = index + 1;
                while (end < line.length && /[0-9a-fA-FxX._]/.test(line[end])) end += 1;
                output += `<span class="num">${escapeHtml(line.slice(index, end))}</span>`;
                index = end;
            } else if (/[A-Za-z_]/.test(char)) {
                let end = index + 1;
                while (end < line.length && /[A-Za-z0-9_]/.test(line[end])) end += 1;
                const word = line.slice(index, end);
                const set = language === "tac" ? TAC_KEYWORDS : CXX_KEYWORDS;
                if (set.has(word)) {
                    const css = language === "cpp" && /^(int|double|float|bool|char|void|long|string|vector|auto|std)$/.test(word) ? "type" : "kw";
                    output += `<span class="${css}">${escapeHtml(word)}</span>`;
                } else if (language === "cpp" && /^(std::int64_t|int64_t|size_t)$/.test(word)) {
                    output += `<span class="type">${escapeHtml(word)}</span>`;
                } else {
                    output += escapeHtml(word);
                }
                index = end;
            } else {
                output += escapeHtml(char);
                index += 1;
            }
        }
        return output;
    }

    /* ----------------------------- Compile ------------------------------ */
    async function doCompile() {
        const data = await ensureAnalysis();
        if (!data || !data.success) {
            $("#compilar-status").textContent =
                "Corrija os erros de análise antes de compilar.";
            $("#compilar-status").className = "action-status error";
            return;
        }
        const button = $("#btn-compilar");
        button.disabled = true;
        $("#compilar-status").textContent = "Compilando com g++…";
        $("#compilar-status").className = "action-status";
        try {
            const response = await fetch("/api/compilar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: editor.value, optimization: "O2" }),
            });
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.stderr || "Falha ao compilar.");
            }
            const link = document.createElement("a");
            link.href = result.download_url;
            link.download = result.filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            const size = result.size ? ` (${(result.size / 1024).toFixed(0)} KB)` : "";
            $("#compilar-status").textContent =
                `Executável gerado${size}. O download foi iniciado.`;
            $("#compilar-status").className = "action-status ok";
        } catch (error) {
            $("#compilar-status").textContent = error.message;
            $("#compilar-status").className = "action-status error";
        } finally {
            button.disabled = false;
        }
    }

    /* ----------------------------- Execute ------------------------------ */
    async function doExecute() {
        const data = await ensureAnalysis();
        if (!data || !data.success) {
            $("#run-stdout").innerHTML =
                '<span class="placeholder-text">Corrija os erros antes de executar.</span>';
            return;
        }
        const button = $("#btn-executar");
        button.disabled = true;
        $("#run-meta").textContent = "compilando e executando…";
        $("#run-stdout").textContent = "";
        $("#run-stderr").classList.add("hidden");
        try {
            const response = await fetch("/api/executar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: editor.value,
                    input: $("#stdin").value,
                    optimization: "O2",
                }),
            });
            const result = await response.json();
            $("#run-stdout").textContent = result.stdout || "(sem saída em stdout)";
            if (result.stderr) {
                $("#run-stderr").textContent = result.stderr;
                $("#run-stderr").classList.remove("hidden");
            } else {
                $("#run-stderr").classList.add("hidden");
            }
            const exit = result.exit_code === null ? "—" : result.exit_code;
            const time = result.tempo !== undefined ? result.tempo : "—";
            $("#run-meta").textContent = `código de saída ${exit} · ${time}s`;
            if (!result.success) {
                $("#run-meta").textContent += " · execução com erro";
            }
        } catch (error) {
            $("#run-stdout").textContent = "";
            $("#run-stderr").textContent = error.message;
            $("#run-stderr").classList.remove("hidden");
        } finally {
            button.disabled = false;
        }
    }

    /* ------------------------------- ARM -------------------------------- */
    async function doGenerateArm() {
        const button = $("#btn-gerar-arm");
        button.disabled = true;
        $("#arm-status").textContent =
            "Compilando o Teste 11 e gerando os arquivos .arm (pode levar alguns segundos)…";
        $("#arm-status").className = "action-status";
        try {
            const response = await fetch("/api/gerar_arm", { method: "POST" });
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.stderr || "Falha ao gerar o Assembly.");
            }
            $("#arm-status").textContent = "Três arquivos .arm gerados com sucesso.";
            $("#arm-status").className = "action-status ok";
            $("#arm-files").innerHTML = result.files
                .map(
                    (file) => `<div class="arm-card">
                        <header>
                            <span>${escapeHtml(file.name)}</span>
                            <a href="${file.download_url}" download>baixar .arm</a>
                        </header>
                        <pre>${escapeHtml(file.content)}</pre>
                    </div>`
                )
                .join("");
        } catch (error) {
            $("#arm-status").textContent = error.message;
            $("#arm-status").className = "action-status error";
        } finally {
            button.disabled = false;
        }
    }

    /* ---------------------------- Examples ------------------------------ */
    async function loadExamples() {
        try {
            const response = await fetch("/api/exemplos");
            const data = await response.json();
            const select = $("#exemplo-select");
            for (const example of data.exemplos || []) {
                const option = document.createElement("option");
                option.value = example.name;
                option.textContent = example.title;
                select.appendChild(option);
            }
        } catch (error) {
            /* silencioso: exemplos são um extra */
        }
    }

    async function loadExample(name) {
        try {
            const response = await fetch("/api/exemplo/" + encodeURIComponent(name));
            const data = await response.json();
            if (!data.success) return;
            editor.value = data.code;
            invalidateAnalysis();
            setStatus(`Exemplo carregado: ${name}`, "ok");
            await refreshActiveTab();
        } catch (error) {
            setStatus("Não foi possível carregar o exemplo.", "error");
        }
    }

    /* ------------------------------ Tabs -------------------------------- */
    async function refreshActiveTab() {
        const name = state.activeTab;
        if (name === "compilar") {
            await ensureAnalysis();
            return;
        }
        if (name === "executar") {
            await ensureAnalysis();
            return;
        }
        if (name === "arm") return;
        const data = await ensureAnalysis();
        if (!data) return;
        renderPanel(name);
    }

    function renderPanel(name) {
        if (name === "tokens") renderTokens();
        else if (name === "ast") renderAst();
        else if (name === "semantica") renderSemantica();
        else if (name === "tac") renderTac();
        else if (name === "cpp") renderCpp();
    }

    function bindTabs() {
        document.querySelectorAll(".tab").forEach((tab) => {
            tab.addEventListener("click", async () => {
                const name = tab.dataset.tab;
                setActiveTab(name);
                if (name === "compilar") {
                    await doCompile();
                } else if (name === "executar") {
                    await doExecute();
                } else if (name === "arm") {
                    /* aguarda o botão "Gerar os três .arm" */
                } else {
                    const data = await ensureAnalysis();
                    if (data) renderPanel(name);
                }
            });
        });
    }

    /* --------------------------- AST exports ---------------------------- */
    function downloadBlob(content, filename, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    function exportAstSvg() {
        if (!state.astRenderer || !state.astRenderer.hasTree()) {
            setStatus("Gere a AST antes de exportar.", "error");
            return;
        }
        const svg = state.astRenderer.exportSvg();
        if (!svg) return;
        downloadBlob(svg, "ast-minipar.svg", "image/svg+xml;charset=utf-8");
    }

    function exportAstPng() {
        if (!state.astRenderer || !state.astRenderer.hasTree()) {
            setStatus("Gere a AST antes de exportar.", "error");
            return;
        }
        const svg = state.astRenderer.exportSvg();
        if (!svg) return;
        const match = svg.match(/width="(\d+(?:\.\d+)?)"[^>]*height="(\d+(?:\.\d+)?)"/);
        const width = match ? Math.max(600, parseFloat(match[1])) : 1200;
        const height = match ? Math.max(400, parseFloat(match[2])) : 800;
        const image = new Image();
        const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        image.onload = () => {
            const scale = 2;
            const canvas = document.createElement("canvas");
            canvas.width = width * scale;
            canvas.height = height * scale;
            const context = canvas.getContext("2d");
            context.fillStyle = "#ffffff";
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            canvas.toBlob((png) => {
                if (png) {
                    const link = document.createElement("a");
                    link.href = URL.createObjectURL(png);
                    link.download = "ast-minipar.png";
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                }
            }, "image/png");
        };
        image.onerror = () => {
            URL.revokeObjectURL(url);
            setStatus("Não foi possível exportar a AST como PNG.", "error");
        };
        image.src = url;
    }

    /* ------------------------------ Init -------------------------------- */
    function bindEvents() {
        editor.addEventListener("input", () => {
            invalidateAnalysis();
            updateLineNumbers();
            setStatus("Programa alterado. Clique em uma aba para analisar.", "");
        });
        editor.addEventListener("scroll", syncScroll);
        editor.addEventListener("keyup", updateCursor);
        editor.addEventListener("click", updateCursor);
        editor.addEventListener("keydown", (event) => {
            if (event.key === "Tab") {
                event.preventDefault();
                const start = editor.selectionStart;
                const end = editor.selectionEnd;
                editor.value = editor.value.slice(0, start) + "    " + editor.value.slice(end);
                editor.selectionStart = editor.selectionEnd = start + 4;
                invalidateAnalysis();
                updateLineNumbers();
            }
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                refreshActiveTab();
            }
        });

        $("#exemplo-select").addEventListener("change", (event) => {
            if (event.target.value) loadExample(event.target.value);
        });

        $("#btn-limpar").addEventListener("click", () => {
            editor.value = "";
            invalidateAnalysis();
            updateLineNumbers();
            setStatus("Editor limpo.", "");
            editor.focus();
        });

        $("#tokens-filter").addEventListener("input", renderTokens);

        $("#ast-zoom-in").addEventListener("click", () => state.astRenderer && state.astRenderer.zoomIn());
        $("#ast-zoom-out").addEventListener("click", () => state.astRenderer && state.astRenderer.zoomOut());
        $("#ast-fit").addEventListener("click", () => state.astRenderer && state.astRenderer.fit());
        $("#ast-expand").addEventListener("click", () => state.astRenderer && state.astRenderer.expandAll());
        $("#ast-collapse").addEventListener("click", () => state.astRenderer && state.astRenderer.collapseAll());
        $("#ast-export-svg").addEventListener("click", exportAstSvg);
        $("#ast-export-png").addEventListener("click", exportAstPng);

        $("#btn-compilar").addEventListener("click", doCompile);
        $("#btn-executar").addEventListener("click", doExecute);
        $("#btn-gerar-arm").addEventListener("click", doGenerateArm);

        $("#tac-copy").addEventListener("click", () => {
            if (state.analysis && state.analysis.tac) {
                navigator.clipboard.writeText(state.analysis.tac);
                setStatus("TAC copiado.", "ok");
            }
        });
        $("#cpp-copy").addEventListener("click", () => {
            if (state.analysis && state.analysis.cpp) {
                navigator.clipboard.writeText(state.analysis.cpp);
                setStatus("Código C++ copiado.", "ok");
            }
        });
        $("#cpp-download").addEventListener("click", () => {
            if (state.analysis && state.analysis.cpp) {
                downloadBlob(state.analysis.cpp, "programa.cpp", "text/x-c++src;charset=utf-8");
            }
        });
    }

    function init() {
        state.astRenderer = window.MiniParAST.createRenderer(
            $("#ast-canvas"),
            $("#ast-tooltip")
        );
        bindTabs();
        bindEvents();
        loadExamples();
        editor.value = DEFAULT_PROGRAM;
        updateLineNumbers();
        updateCursor();
        setStatus("Pronto. Clique em uma aba para analisar.", "");

        const params = new URLSearchParams(window.location.search);
        const requested = params.get("tab") || (window.location.hash || "").replace("#", "");
        const autorun = params.get("run") === "1";
        const allowed = ["tokens", "ast", "semantica", "tac", "cpp", "arm", "compilar", "executar"];
        if (allowed.includes(requested)) {
            setActiveTab(requested);
            if (requested === "compilar") {
                ensureAnalysis().then(() => {
                    if (autorun) doCompile();
                });
            } else if (requested === "executar") {
                ensureAnalysis().then(() => {
                    if (autorun) doExecute();
                });
            } else if (requested === "arm") {
                if (autorun) doGenerateArm();
            } else {
                ensureAnalysis().then((data) => {
                    if (data) renderPanel(requested);
                });
            }
        } else {
            ensureAnalysis().then((data) => {
                if (data) renderTokens();
            });
        }
    }

    document.addEventListener("DOMContentLoaded", init);
})();
