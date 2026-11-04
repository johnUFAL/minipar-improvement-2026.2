document.addEventListener("DOMContentLoaded", () => {
    const editor = CodeMirror.fromTextArea(document.getElementById("source-editor"), {
        mode: "clike", lineNumbers: true, lineWrapping: true, autoCloseBrackets: true,
    });
    const phaseNames = {code:"Código", tokens:"Tokens", ast:"AST", symbols:"Tabela de símbolos", tac:"TAC", cpp:"C++", execution:"Execução"};
    const phaseOrder = Object.keys(phaseNames);
    const examples = document.getElementById("example-select");
    const content = document.getElementById("phase-content");
    const diagnostics = document.getElementById("diagnostics");
    const status = document.getElementById("status");
    const programInput = document.getElementById("program-input");
    const pages = document.querySelectorAll(".page");
    const navItems = document.querySelectorAll(".nav-item[data-page]");
    const metricState = document.getElementById("metric-state");
    const history = [];
    const defaultOptimization = "O0";
    let optimizationLevel = localStorage.getItem("minipar-optimization") || defaultOptimization;
    let result = null;
    let execution = null;
    let currentPhase = "code";
    let markers = [];

    const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));
    const json = value => `<pre class="json-output">${escape(JSON.stringify(value, null, 2))}</pre>`;
    const output = (title, value) => `<section><h3>${title}</h3><pre class="code-output">${escape(value)}</pre></section>`;
    const explain = {
        tokens: "Veja como o texto foi separado em unidades que o compilador consegue reconhecer.",
        ast: "A árvore sintática preserva a estrutura das expressões, comandos e blocos do programa.",
        symbols: "A tabela registra nomes, tipos e escopos encontrados na análise semântica.",
        tac: "O TAC transforma o programa em instruções simples, antes da geração do C++.",
        cpp: "Este é o código C++ produzido a partir do TAC e usado na execução.",
        execution: "Confira a saída do programa, os erros e o tempo medido pelo ambiente.",
    };
    function setStatus(text, error = false) { status.classList.toggle("error", error); status.innerHTML = `<span></span> ${escape(text)}`; }
    function showPage(pageName) {
        pages.forEach(page => page.classList.toggle("active-page", page.id === `page-${pageName}`));
        navItems.forEach(item => item.classList.toggle("active", item.dataset.page === pageName));
        const pageLabels = { dashboard: "Painel", ide: "Editor MiniPar", results: "Resultados", configuration: "Configurações" };
        document.getElementById("topbar-page").textContent = pageLabels[pageName] || "MiniPar";
        if (pageName === "ide") setTimeout(() => editor.refresh(), 30);
        window.location.hash = pageName;
        if (pageName === "results") renderHistory();
    }
    function renderHistory() {
        const list = document.getElementById("results-list");
        if (!list) return;
        document.getElementById("result-count").textContent = history.length;
        document.getElementById("result-success").textContent = history.filter(item => item.success).length;
        document.getElementById("result-errors").textContent = history.filter(item => !item.success).length;
        document.getElementById("result-time").textContent = history.length ? `${history[0].time.toFixed(3)} s` : "—";
        list.innerHTML = history.length ? history.map((item, index) => `<button class="history-row ${index === 0 ? "selected" : ""}" data-history-index="${index}"><b>${escape(item.file)}</b><span>${item.success ? '<em class="green-text">Sucesso</em>' : '<em class="red-text">Com erro</em>'}</span><small>${item.time.toFixed(3)} s</small></button>`).join("") : "Execute um programa pela IDE para visualizar os resultados.";
        list.querySelectorAll("[data-history-index]").forEach(button => button.addEventListener("click", () => renderResultDetail(history[Number(button.dataset.historyIndex)])));
        if (history.length) renderResultDetail(history[0]);
    }
    function renderResultDetail(item) {
        const detail = document.getElementById("result-detail");
        if (!detail || !item) return;
        detail.innerHTML = `<div class="card-title"><span>${escape(item.file)}</span><span class="${item.success ? "green-text" : "red-text"}">${item.success ? "EXECUÇÃO CONCLUÍDA" : "EXECUÇÃO COM ERRO"}</span></div>
            <div class="result-meta"><span>Tempo <b>${item.time.toFixed(3)} s</b></span><span>Saída <b>código ${item.execution.exit_code ?? "—"}</b></span></div>
            <div class="execution-grid"><div class="execution-box"><h3>STDOUT</h3><pre>${escape(item.execution.stdout || "(sem saída)")}</pre></div><div class="execution-box"><h3>STDERR</h3><pre>${escape(item.execution.stderr || "(sem erros)")}</pre></div></div>
            <button class="btn secondary result-open">Abrir na IDE</button>`;
        detail.querySelector(".result-open").addEventListener("click", () => showPage("ide"));
    }
    function markDiagnostics(items) {
        markers.forEach(marker => marker.clear()); markers = [];
        diagnostics.innerHTML = "";
        items.forEach(item => {
            const line = Math.max(0, Number(item.line || 1) - 1);
            markers.push(editor.addLineClass(line, "background", "cm-error-line"));
            const button = document.createElement("button");
            button.className = "diagnostic";
            button.textContent = `${item.header || item.message} (linha ${line + 1}, coluna ${item.column || 1})`;
            button.onclick = () => { editor.focus(); editor.setCursor(line, Math.max(0, Number(item.column || 1) - 1)); };
            diagnostics.appendChild(button);
        });
    }
    function renderPhase() {
        const index = phaseOrder.indexOf(currentPhase);
        document.getElementById("phase-title").textContent = phaseNames[currentPhase];
        document.getElementById("phase-count").textContent = `${index + 1} de ${phaseOrder.length}`;
        document.querySelectorAll(".step").forEach(step => step.classList.toggle("active", step.dataset.phase === currentPhase));
        if (currentPhase === "code") content.innerHTML = `<div class="phase-placeholder"><strong>Seu ponto de partida</strong><p>Edite o programa à esquerda e compile para liberar as próximas fases.</p></div>`;
        else if (!result) content.innerHTML = `<div class="phase-placeholder"><strong>Compile primeiro</strong><p>Os dados desta fase aparecerão aqui.</p></div>`;
        else if (currentPhase === "tokens") content.innerHTML = `<div class="phase-explainer">${explain.tokens}</div><table class="data-table"><thead><tr><th>Tipo</th><th>Lexema</th><th>Linha</th><th>Coluna</th></tr></thead><tbody>${result.tokens.map(token => `<tr><td>${escape(token.type)}</td><td><code>${escape(token.lexeme)}</code></td><td>${token.line}</td><td>${token.column}</td></tr>`).join("")}</tbody></table>`;
        else if (currentPhase === "ast") content.innerHTML = `<div class="phase-explainer">${explain.ast}</div>${json(result.ast)}`;
        else if (currentPhase === "symbols") content.innerHTML = `<div class="phase-explainer">${explain.symbols}</div>${json(result.tabela_simbolos)}`;
        else if (currentPhase === "tac") content.innerHTML = `<div class="phase-explainer">${explain.tac}</div><div class="tac-toolbar"><span>Nível selecionado: <b>${optimizationLevel}</b></span><button class="btn secondary" id="compare-tac">Comparar antes/depois</button></div>${result.tac ? output("Código intermediário", result.tac) : `<p class="hint">Nenhum TAC foi gerado porque há erros no programa.</p>`}`;
        else if (currentPhase === "cpp") content.innerHTML = `<div class="phase-explainer">${explain.cpp}</div>${result.cpp ? output("Código C++ gerado", result.cpp) : `<p class="hint">Nenhum C++ foi gerado porque há erros no programa.</p>`}`;
        else content.innerHTML = execution ? `<div class="phase-explainer">${explain.execution}</div><div class="execution"><p class="hint">Tempo: ${Number(execution.tempo || 0).toFixed(3)} s · código de saída: ${execution.exit_code ?? "—"}</p><div class="execution-grid"><div class="execution-box"><h3>STDOUT</h3><pre>${escape(execution.stdout)}</pre></div><div class="execution-box"><h3>STDERR</h3><pre>${escape(execution.stderr)}</pre></div></div></div>` : `<div class="phase-placeholder"><strong>Ainda não executado</strong><p>Clique em Executar para ver stdout, stderr e tempo.</p></div>`;
        const compareButton = document.getElementById("compare-tac");
        if (compareButton) compareButton.addEventListener("click", compareTac);
    }
    async function compareTac() {
        if (!result || !result.tac) return;
        const compareButton = document.getElementById("compare-tac");
        if (compareButton) compareButton.disabled = true;
        try {
            const response = await fetch("/api/otimizar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue(), optimization_level: optimizationLevel }) });
            const optimized = await response.json();
            if (!optimized.success) { setStatus("Não foi possível otimizar o TAC", true); return; }
            content.innerHTML = `<div class="phase-explainer">${explain.tac}</div><div class="comparison">${output("TAC antes", optimized.tac)}${output(`TAC depois (${optimizationLevel})`, optimized.tac_optimized)}</div>`;
        } catch (error) { setStatus("Falha ao comparar TAC", true); }
        finally { if (compareButton) compareButton.disabled = false; }
    }
    async function loadExamples() {
        const response = await fetch("/api/tests"); const data = await response.json();
        examples.innerHTML = `<option value="">Escolher um exemplo pronto</option>` + data.tests.map(name => `<option value="${escape(name)}">${escape(name)}</option>`).join("");
        const metric = document.getElementById("metric-tests");
        if (metric) metric.textContent = data.tests.length;
        const exampleCount = document.getElementById("example-count");
        if (exampleCount) exampleCount.textContent = String(data.tests.length).padStart(2, "0");
        const dashboardExample = document.getElementById("dashboard-example");
        if (dashboardExample) dashboardExample.innerHTML = data.tests.map(name => `<option>${escape(name)}</option>`).join("");
        const testList = document.getElementById("test-list");
        if (testList) testList.innerHTML = data.tests.map(name => `<li data-filename="${escape(name)}" tabindex="0">${escape(name.replace(/\.mp$/, ""))}</li>`).join("");
        testList?.querySelectorAll("[data-filename]").forEach(item => {
            item.addEventListener("click", () => loadExample(item.dataset.filename));
            item.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") loadExample(item.dataset.filename); });
        });
    }
    async function loadExample(filename) {
        const response = await fetch("/api/get_test", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ filename }) });
        const data = await response.json();
        editor.setValue(data.code || "");
        document.getElementById("current-file").textContent = filename;
        document.querySelectorAll(".test-list li").forEach(item => item.classList.toggle("active", item.dataset.filename === filename));
        result = null; execution = null; markDiagnostics([]); currentPhase = "code"; renderPhase();
        showPage("ide"); setStatus("Exemplo carregado");
    }
    async function compile() {
        const button = document.getElementById("compile-button"); button.disabled = true; setStatus("Compilando...");
        try {
            const response = await fetch("/api/compilar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue() }) });
            result = await response.json(); execution = null; markDiagnostics(result.diagnosticos || []);
            if (metricState) metricState.textContent = result.success ? "COMPILADO" : "COM ERROS";
            setStatus(result.success ? "Compilação concluída" : "Há erros no programa", !result.success);
            currentPhase = result.success ? "tokens" : "code"; renderPhase();
        } catch (error) { setStatus("Não foi possível conectar ao compilador", true); }
        finally { button.disabled = false; }
    }
    async function run() {
        const button = document.getElementById("run-button"); button.disabled = true; setStatus("Executando...");
        try {
            if (!result) {
                await compile();
                if (!result || !result.success) return;
            }
            const inputs = programInput.value.split(/\r?\n/).filter(line => line.length > 0);
            const response = await fetch("/api/executar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue(), inputs }) });
            execution = await response.json();
            history.unshift({ file: document.getElementById("current-file").textContent, success: Boolean(execution.success), time: Number(execution.tempo || 0), execution });
            renderHistory();
            currentPhase = "execution"; setStatus(execution.success ? "Execução concluída" : "Execução terminou com erro", !execution.success); renderPhase();
        } catch (error) { setStatus("Não foi possível executar", true); }
        finally { button.disabled = false; }
    }
    examples.addEventListener("change", async event => {
        if (!event.target.value) return;
        await loadExample(event.target.value);
    });
    document.getElementById("dashboard-example")?.addEventListener("change", event => loadExample(event.target.value));
    document.getElementById("compile-button").addEventListener("click", compile);
    document.getElementById("editor-compile").addEventListener("click", compile);
    document.getElementById("run-button").addEventListener("click", run);
    editor.getWrapperElement().addEventListener("keydown", event => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            compile();
        }
    });
    document.getElementById("clear-button").addEventListener("click", () => { editor.setValue(""); result = null; execution = null; markDiagnostics([]); currentPhase = "code"; renderPhase(); });
    navItems.forEach(item => item.addEventListener("click", () => showPage(item.dataset.page)));
    document.querySelectorAll("[data-page-target]").forEach(button => button.addEventListener("click", () => showPage(button.dataset.pageTarget)));
    document.querySelectorAll(".step").forEach(step => step.addEventListener("click", async () => {
        currentPhase = step.dataset.phase;
        if (currentPhase === "tac" && result) {
            await compareTac();
        } else renderPhase();
    }));
    function syncOptimization(value) {
        optimizationLevel = value;
        localStorage.setItem("minipar-optimization", value);
        document.getElementById("optimization").value = value;
        document.getElementById("settings-optimization").value = value;
        document.getElementById("dashboard-optimization").textContent = `${value} — ${value === "O0" ? "sem otimização" : "otimização aplicada"}`;
        renderPhase();
    }
    document.getElementById("optimization").value = optimizationLevel;
    document.getElementById("settings-optimization").value = optimizationLevel;
    document.getElementById("optimization").addEventListener("change", event => syncOptimization(event.target.value));
    document.getElementById("settings-optimization").addEventListener("change", event => {
        document.getElementById("settings-saved").innerHTML = '<span class="status-dot"></span> Alterações não salvas';
        optimizationLevel = event.target.value;
    });
    document.getElementById("save-settings").addEventListener("click", () => {
        syncOptimization(document.getElementById("settings-optimization").value);
        document.getElementById("settings-saved").innerHTML = '<span class="status-dot"></span> Configuração salva';
        setStatus("Configurações salvas");
    });
    document.getElementById("restore-settings").addEventListener("click", () => {
        document.getElementById("settings-optimization").value = defaultOptimization;
        syncOptimization(defaultOptimization);
        document.getElementById("settings-saved").innerHTML = '<span class="status-dot"></span> Padrão restaurado';
    });
    document.getElementById("export-results").addEventListener("click", () => {
        const data = JSON.stringify(history, null, 2);
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([data], { type: "application/json" }));
        link.download = "minipar-resultados.json";
        link.click();
        URL.revokeObjectURL(link.href);
    });
    const initialPage = ["results", "configuration", "ide"].includes(window.location.hash.slice(1)) ? window.location.hash.slice(1) : "dashboard";
    loadExamples(); renderPhase(); showPage(initialPage);
});
