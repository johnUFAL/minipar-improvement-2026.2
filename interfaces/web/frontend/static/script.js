document.addEventListener("DOMContentLoaded", () => {
    const editor = CodeMirror.fromTextArea(document.getElementById("source-editor"), {
        mode: "clike", lineNumbers: true, lineWrapping: true, autoCloseBrackets: true,
    });
    function resizeEditorViewport() {
        const lineHeight = parseFloat(getComputedStyle(editor.getWrapperElement()).lineHeight) || 21;
        const lineCount = editor.lineCount();
        const visibleLines = Math.max(20, Math.min(lineCount, 30));
        const height = `${visibleLines * lineHeight + 20}px`;
        editor.setSize(null, height);
        editor.getWrapperElement().style.setProperty("height", height, "important");
    }
    editor.on("change", resizeEditorViewport);
    resizeEditorViewport();
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
    let availableTests = [];
    const defaultOptimization = "O0";
    let optimizationLevel = localStorage.getItem("minipar-optimization") || defaultOptimization;
    let result = null;
    let execution = null;
    let currentPhase = "code";
    let markers = [];
    let columnMarkers = [];
    let runInProgress = false;
    let editorOriginBinding = null;
    let resultOriginBinding = null;
    let astLineMarkers = [];
    let astTextMarkers = [];
    let astReadonlyHighlights = [];

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
    function clamp(value, minimum, maximum) {
        return Math.min(maximum, Math.max(minimum, value));
    }
    function astSpan(node) {
        if (!node) return null;
        if (window.MiniParAstView && window.MiniParAstView.spanOf) {
            return window.MiniParAstView.spanOf(node);
        }
        const line = Math.max(1, Number(node.line || 1));
        const column = Math.max(1, Number(node.column || 1));
        return { line, column, endLine: line, endColumn: column + 1 };
    }
    function clearAstHighlight() {
        astLineMarkers.forEach(marker => editor.removeLineClass(marker, "background", "cm-ast-line"));
        astLineMarkers = [];
        astTextMarkers.forEach(marker => marker.clear());
        astTextMarkers = [];
        astReadonlyHighlights.forEach(element => element.classList.remove("ast-source-highlight"));
        astReadonlyHighlights = [];
    }
    function revealEditorLine(line, ch) {
        if (line < 0 || line >= editor.lineCount()) return;
        const scroll = editor.getScrollInfo();
        const coords = editor.charCoords({ line, ch: ch || 0 }, "local");
        const lineHeight = editor.defaultTextHeight
            ? editor.defaultTextHeight()
            : Math.max(1, parseFloat(getComputedStyle(editor.getWrapperElement()).lineHeight) || 21);
        const scroller = editor.getScrollerElement();
        if (coords.top < scroll.top || coords.top > scroll.top + scroll.clientHeight - lineHeight) {
            scroller.scrollTop = Math.max(0, coords.top - Math.floor(scroll.clientHeight / 2));
        }
        if (coords.left < scroll.left || coords.left > scroll.left + scroll.clientWidth) {
            scroller.scrollLeft = Math.max(0, coords.left - 24);
        }
    }
    function highlightAstNode(node) {
        clearAstHighlight();
        const span = astSpan(node);
        if (!span) return;
        const startLine = clamp(span.line - 1, 0, editor.lineCount() - 1);
        const rawEndLine = clamp(span.endLine - 1, startLine, editor.lineCount() - 1);
        const endLine = Math.min(rawEndLine, startLine + 299);
        const startText = editor.getLine(startLine) || "";
        const endText = editor.getLine(endLine) || "";
        const startCh = clamp(span.column - 1, 0, startText.length);
        let endCh = rawEndLine === endLine
            ? clamp(span.endColumn - 1, 0, endText.length)
            : endText.length;
        if (startLine === endLine && endCh <= startCh) {
            endCh = Math.min(startText.length, startCh + 1);
        }
        for (let line = startLine; line <= endLine; line += 1) {
            astLineMarkers.push(editor.addLineClass(line, "background", "cm-ast-line"));
        }
        if (endLine > startLine || endCh > startCh) {
            astTextMarkers.push(editor.markText(
                { line: startLine, ch: startCh },
                { line: endLine, ch: endCh },
                { className: "cm-ast-token", title: `AST: ${node.tipo || "nó"}` },
            ));
        }
        revealEditorLine(startLine, startCh);
    }
    function highlightReadonlyAstNode(node, root) {
        clearAstHighlight();
        if (!root) return;
        const span = astSpan(node);
        if (!span) return;
        const lines = root.querySelectorAll(".readonly-code-line");
        const lastLine = Math.min(span.endLine, span.line + 299);
        for (let line = span.line; line <= lastLine; line += 1) {
            const target = lines[line - 1];
            if (target) {
                target.classList.add("ast-source-highlight");
                astReadonlyHighlights.push(target);
            }
        }
    }
    function showPage(pageName) {
        pages.forEach(page => page.classList.toggle("active-page", page.id === `page-${pageName}`));
        navItems.forEach(item => item.classList.toggle("active", item.dataset.page === pageName));
        const pageLabels = { dashboard: "Painel", pipeline: "Pipeline MiniPar", ide: "Editor MiniPar", results: "Resultados", "result-detail": "Resultado selecionado", configuration: "Configurações" };
        document.getElementById("topbar-page").textContent = pageLabels[pageName] || "MiniPar";
        document.getElementById("compile-button").hidden = pageName !== "ide";
        if (pageName === "ide") setTimeout(() => editor.refresh(), 30);
        window.location.hash = pageName;
        if (pageName === "results") renderHistory();
    }
    function syncTheme() {
        const light = localStorage.getItem("minipar-theme") === "light";
        document.body.classList.toggle("light-theme", light);
        const toggle = document.getElementById("theme-toggle");
        if (toggle) {
            toggle.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#icon-${light ? "moon" : "sun"}"></use></svg><span class="button-label">${light ? "Escuro" : "Claro"}</span>`;
            toggle.setAttribute("aria-label", light ? "Mudar para modo escuro" : "Mudar para modo claro");
        }
    }
    function renderHistory() {
        const list = document.getElementById("results-list");
        if (!list) return;
        document.getElementById("result-count").textContent = history.length;
        document.getElementById("result-success").textContent = history.filter(item => item.success).length;
        document.getElementById("result-errors").textContent = history.filter(item => !item.success).length;
        document.getElementById("result-time").textContent = history.length ? `${history[0].time.toFixed(3)} s` : "—";
        list.innerHTML = history.length ? history.map((item, index) => `<button class="history-row ${index === 0 ? "selected" : ""}" data-history-index="${index}"><b>${escape(item.file)}</b><span>${item.success ? '<em class="green-text">Sucesso</em>' : '<em class="red-text">Com erro</em>'}</span><small>${item.time.toFixed(3)} s</small></button>`).join("") : "Execute um programa pela IDE para visualizar os resultados.";
        list.querySelectorAll("[data-history-index]").forEach(button => button.addEventListener("click", () => renderResultDetail(history[Number(button.dataset.historyIndex)], true)));
        if (history.length) renderResultDetail(history[0], false);
        renderDashboard();
    }
    function renderDashboard() {
        const historyList = document.getElementById("dashboard-history-list");
        const lastFile = document.getElementById("dashboard-last-file");
        const lastTime = document.getElementById("dashboard-last-time");
        const lastStatus = document.getElementById("dashboard-last-status");
        if (lastFile) lastFile.textContent = history.length ? history[0].file : "Nenhum";
        if (lastTime) lastTime.textContent = history.length ? `${history[0].time.toFixed(3)} s` : "—";
        if (lastStatus) {
            lastStatus.textContent = history.length
                ? (history[0].success ? "Execução concluída" : "Execução com diagnóstico")
                : "Aguardando uma execução";
            lastStatus.className = history.length && !history[0].success ? "danger-text" : "";
        }
        if (!historyList) return;
        historyList.innerHTML = history.length
            ? history.slice(0, 1).map((item, index) => `<button class="dashboard-history-row" data-history-index="${index}"><span><b>${escape(item.file)}</b><small>${item.success ? "Execução concluída" : "Com diagnóstico"}</small></span><strong class="${item.success ? "green-text" : "red-text"}">${item.time.toFixed(3)} s</strong></button>`).join("")
            : '<p class="empty-state">Ainda não há execuções nesta sessão.</p>';
        historyList.querySelectorAll("[data-history-index]").forEach(button => button.addEventListener("click", () => renderResultDetail(history[Number(button.dataset.historyIndex)], true)));
    }
    function renderResultDetail(item, navigate = false) {
        const detail = document.getElementById("result-detail");
        if (!detail || !item) return;
        const errorLines = new Set((item.diagnosticos || []).map(diagnostic => Number(diagnostic.line || 1)));
        const sourceLines = String(item.source || "(código não armazenado)").split("\n").map((line, index) => `<div class="readonly-code-line ${errorLines.has(index + 1) ? "readonly-error-line" : ""}"><span>${index + 1}</span><code>${escape(line) || " "}</code></div>`).join("");
        detail.innerHTML = `<div class="ide-grid result-ide-grid"><article class="editor-panel card readonly-editor-panel"><div class="panel-title"><span><span class="panel-mark"><svg class="icon" aria-hidden="true"><use href="#icon-code"></use></svg></span> Código-fonte</span><small>MINIPAR · SOMENTE LEITURA</small></div><div class="detail-file-label">${escape(item.file)}</div><div class="readonly-code result-source-code" aria-label="Código-fonte somente leitura">${sourceLines}</div><div class="input-area readonly-input"><label>ENTRADAS DO PROGRAMA <span>stdin · preservadas da execução</span></label><pre class="program-input">${escape(item.inputs || "(sem entrada)")}</pre></div></article><article class="phase-panel card result-phase-panel"><div class="panel-title"><span><span class="panel-mark"><svg class="icon" aria-hidden="true"><use href="#icon-layers"></use></svg></span> <b id="result-phase-title">Execução</b></span><small>RESULTADO PRESERVADO</small></div><nav class="phase-nav result-phase-nav" aria-label="Fases do resultado">${phaseOrder.map((phase, index) => `<button type="button" class="step ${phase === "execution" ? "active" : ""}" data-result-phase="${phase}"><span>${String(index + 1).padStart(2, "0")}</span><b>${phaseNames[phase]}</b></button>`).join("")}</nav><div id="result-phase-content" class="phase-content" role="region" aria-live="polite"></div></article></div>`;
        const resultPhaseContent = document.getElementById("result-phase-content");
        const resultPhaseTitle = document.getElementById("result-phase-title");
        const compileResult = item.compileResult || {};
        const renderResultPhase = phase => {
            clearAstHighlight();
            if (resultPhaseTitle) resultPhaseTitle.textContent = phaseNames[phase];
            document.querySelectorAll("[data-result-phase]").forEach(step => step.classList.toggle("active", step.dataset.resultPhase === phase));
            if (!resultPhaseContent) return;
            if (phase === "code") resultPhaseContent.innerHTML = diagnosticsOutput(item.diagnosticos || []) || `<div class="phase-placeholder"><strong>Código-fonte preservado</strong><p>Este programa não pode ser editado nesta tela.</p></div>`;
            else if (phase === "tokens") resultPhaseContent.innerHTML = compileResult.tokens ? `<div class="phase-explainer">${explain.tokens}</div><div class="table-scroll"><table class="data-table"><thead><tr><th>Tipo</th><th>Lexema</th><th>Linha</th><th>Coluna</th></tr></thead><tbody>${compileResult.tokens.map(token => `<tr><td>${escape(token.type)}</td><td><code>${escape(token.lexeme)}</code></td><td>${token.line}</td><td>${token.column}</td></tr>`).join("")}</tbody></table></div>` : `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
            else if (phase === "ast") {
                if (compileResult.ast) {
                    resultPhaseContent.innerHTML = `<div class="phase-explainer">${explain.ast}</div><div id="result-ast-view" class="ast-mount"></div>`;
                    const astHost = resultPhaseContent.querySelector("#result-ast-view");
                    if (astHost) {
                        if (window.MiniParAstView) {
                            const readonlySource = detail.querySelector(".result-source-code");
                            window.MiniParAstView.mount(astHost, compileResult.ast, {
                                onSelect: node => highlightReadonlyAstNode(node, readonlySource),
                            });
                        } else {
                            astHost.innerHTML = json(compileResult.ast);
                        }
                    }
                } else {
                    resultPhaseContent.innerHTML = `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
                }
            }
            else if (phase === "symbols") resultPhaseContent.innerHTML = compileResult.tabela_simbolos ? `<div class="phase-explainer">${explain.symbols}</div>${json(compileResult.tabela_simbolos)}` : `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
            else if (phase === "tac") {
                if (!compileResult.tac) {
                    resultPhaseContent.innerHTML = `<div class="phase-placeholder"><strong>Nenhum TAC foi gerado</strong></div>`;
                } else {
                    const currentLevel = item.optimization || "O0";
                    const defaultCompareLevel = currentLevel === "O1" ? "O2" : "O1";
                    resultPhaseContent.innerHTML = `<div class="phase-explainer">${explain.tac}</div><div class="result-tac-toolbar"><label for="result-compare-level">COMPARAR COM</label><select id="result-compare-level" class="select-control compact">${["O0", "O1", "O2", "O3"].filter(level => level !== currentLevel).map(level => `<option value="${level}" ${level === defaultCompareLevel ? "selected" : ""}>${level}</option>`).join("")}</select><button type="button" class="button button-primary" id="result-compare-tac">Comparar TAC</button></div><div id="result-tac-comparison" class="comparison-placeholder"><p>Escolha um nível para visualizar os dois TACs lado a lado.</p></div>`;
                    document.getElementById("result-compare-tac").addEventListener("click", async () => {
                        const compareLevel = document.getElementById("result-compare-level").value;
                        const compareButton = document.getElementById("result-compare-tac");
                        const comparison = document.getElementById("result-tac-comparison");
                        compareButton.disabled = true;
                        comparison.innerHTML = `<p class="hint">Gerando TACs para comparação...</p>`;
                        try {
                            const [current, compared] = await Promise.all([
                                optimizeForLevel(item.source, currentLevel),
                                optimizeForLevel(item.source, compareLevel),
                            ]);
                            if (!current.success || !compared.success) throw new Error("Falha ao gerar TAC");
                            comparison.innerHTML = `<div class="comparison">${mappedCode(`TAC atual (${currentLevel})`, current.tac_optimized, current.optimized_tac_origin, "tac")}${mappedCode(`TAC comparado (${compareLevel})`, compared.tac_optimized, compared.optimized_tac_origin, "tac")}</div>`;
                            bindOriginHighlights({ scope: resultPhaseContent, source: { type: "readonly", code: item.source, root: detail.querySelector(".result-source-code") } });
                        } catch (error) {
                            comparison.innerHTML = `<p class="hint error">Não foi possível gerar a comparação.</p>`;
                        } finally {
                            compareButton.disabled = false;
                        }
                    });
                }
            }
            else if (phase === "cpp") resultPhaseContent.innerHTML = compileResult.cpp ? `<div class="phase-explainer">${explain.cpp}</div>${mappedCode("Código C++ gerado", compileResult.cpp, compileResult.cpp_origin, "cpp")}` : `<div class="phase-placeholder"><strong>Nenhum C++ foi gerado</strong></div>`;
            else resultPhaseContent.innerHTML = `<div class="phase-explainer">${explain.execution}</div><div class="execution"><p class="hint">Tempo: ${item.time.toFixed(3)} s · código de saída: ${item.execution.exit_code ?? "—"}</p><div class="execution-grid"><div class="execution-box"><h3>STDOUT</h3><pre>${escape(item.execution.stdout || "(sem saída)")}</pre></div><div class="execution-box"><h3>STDERR</h3><pre>${escape(item.execution.stderr || "(sem erros)")}</pre></div></div></div>`;
            bindOriginHighlights({ scope: resultPhaseContent, source: { type: "readonly", code: item.source, root: detail.querySelector(".result-source-code") } });
        };
        document.querySelectorAll("[data-result-phase]").forEach(step => step.addEventListener("click", () => renderResultPhase(step.dataset.resultPhase)));
        renderResultPhase("execution");
        if (navigate) showPage("result-detail");
    }
    function markDiagnostics(items) {
        markers.forEach(marker => editor.removeLineClass(marker, "background", "cm-error-line"));
        markers = [];
        columnMarkers.forEach(marker => marker.clear());
        columnMarkers = [];
        if (diagnostics) diagnostics.innerHTML = "";
        items.forEach(item => {
            const line = Math.max(0, Number(item.line || 1) - 1);
            const column = Math.max(0, Number(item.column || 1) - 1);
            const length = Math.max(1, Number(item.length || 1));
            const lineText = editor.getLine(line) || "";
            markers.push(editor.addLineClass(line, "background", "cm-error-line"));
            if (lineText.length) {
                const start = Math.min(column, lineText.length - 1);
                const end = Math.min(lineText.length, start + length);
                columnMarkers.push(editor.markText(
                    { line, ch: start },
                    { line, ch: end },
                    { className: "cm-error-token", title: item.message || item.header || "" },
                ));
            }
            const button = document.createElement("button");
            button.className = "diagnostic";
            button.textContent = `${item.header || item.message} (linha ${line + 1}, coluna ${item.column || 1})`;
            button.onclick = () => { editor.focus(); editor.setCursor(line, Math.max(0, Number(item.column || 1) - 1)); };
            if (diagnostics) diagnostics.appendChild(button);
        });
    }
    function diagnosticsOutput(items) {
        if (!items.length) return "";
        return `<div class="diagnostics phase-diagnostics" aria-live="polite"><strong>Diagnósticos encontrados</strong>${items.map(item => `<button class="diagnostic" data-line="${Math.max(0, Number(item.line || 1) - 1)}" data-column="${Math.max(0, Number(item.column || 1) - 1)}">${escape(item.header || item.message)} (linha ${item.line || 1}, coluna ${item.column || 1})</button>`).join("")}</div>`;
    }
    function bindPhaseDiagnostics() {
        document.querySelectorAll(".phase-diagnostics .diagnostic").forEach(button => button.addEventListener("click", () => {
            editor.focus();
            editor.setCursor(Number(button.dataset.line), Number(button.dataset.column));
        }));
    }
    function mappedCode(title, value, mappings, language) {
        const sourceByLine = new Map((mappings || []).map(item => [item.generated_line, item.source_line]));
        const lines = String(value || "").split("\n");
        return `<section class="mapped-code" data-mapped-code="${language}"><h3>${title}</h3><div class="mapped-code-lines">${lines.map((line, index) => {
            const generatedLine = index + 1;
            const sourceLine = sourceByLine.get(generatedLine);
            const origin = sourceLine
                ? ` data-source-line="${sourceLine}" data-generated-line="${generatedLine}" tabindex="0" role="button" aria-label="Linha ${generatedLine}, origem na linha ${sourceLine} do MiniPar"`
                : "";
            return `<div class="mapped-code-line"${origin}><span class="mapped-line-number">${generatedLine}</span><code>${escape(line) || " "}</code></div>`;
        }).join("")}</div></section>`;
    }
    function createOriginSource(source) {
        if (source?.type === "readonly") {
            const root = source.root;
            const lines = String(source.code || "").split("\n");
            return {
                highlight(line) {
                    const target = root?.querySelectorAll(".readonly-code-line")[line - 1];
                    if (target) target.classList.add("origin-highlight");
                },
                clear() {
                    root?.querySelectorAll(".readonly-code-line.origin-highlight").forEach(item => item.classList.remove("origin-highlight"));
                },
                text(line) {
                    return lines[line - 1] || "";
                },
            };
        }
        return {
            highlight(line) {
                editor.addLineClass(line - 1, "background", "cm-origin-line");
            },
            clear() {
                for (let index = 0; index < editor.lineCount(); index++) {
                    editor.removeLineClass(index, "background", "cm-origin-line");
                }
            },
            text(line) {
                return editor.getLine(line - 1) || "";
            },
        };
    }
    function bindOriginHighlights(options = {}) {
        const scope = options.scope || document;
        const originSource = createOriginSource(options.source);
        originSource.clear();
        const sourceLines = scope.querySelectorAll(".mapped-code-line[data-source-line]");
        document.querySelectorAll(".tac-origin-popover").forEach(popover => popover.remove());
        const originPopover = scope.querySelector(".mapped-code")
            ? Object.assign(document.createElement("div"), {
                className: "tac-origin-popover",
                role: "status",
                hidden: true,
            })
            : null;
        if (originPopover) document.body.appendChild(originPopover);
        let activeSourceLine = null;
        let popoverSourceLine = null;
        const clear = () => {
            activeSourceLine = null;
            popoverSourceLine = null;
            scope.querySelectorAll(".mapped-code-line.origin-highlight").forEach(item => item.classList.remove("origin-highlight"));
            if (originPopover) originPopover.hidden = true;
            originSource.clear();
        };
        const highlight = (line, event) => {
            const sourceLine = Number(line.dataset.sourceLine);
            if (sourceLine !== activeSourceLine) {
                activeSourceLine = sourceLine;
                scope.querySelectorAll(".mapped-code-line.origin-highlight").forEach(item => item.classList.remove("origin-highlight"));
                scope.querySelectorAll(`.mapped-code-line[data-source-line="${sourceLine}"]`).forEach(item => item.classList.add("origin-highlight"));
                originSource.clear();
                originSource.highlight(sourceLine);
            }
            if (originPopover && line.closest(".mapped-code")) {
                if (popoverSourceLine !== sourceLine) {
                    originPopover.innerHTML = `<strong>Origem: linha ${sourceLine} do MiniPar</strong><code>${escape(originSource.text(sourceLine)) || " "}</code>`;
                    popoverSourceLine = sourceLine;
                }
                originPopover.hidden = false;
                if (event) {
                    moveTacPopover(event, originPopover);
                } else {
                    const rect = line.getBoundingClientRect();
                    moveTacPopover({ clientX: rect.right, clientY: rect.bottom }, originPopover);
                }
            } else if (originPopover) {
                originPopover.hidden = true;
                popoverSourceLine = null;
            }
        };
        const highlightSource = sourceLine => {
            if (sourceLine === activeSourceLine) return;
            if (!scope.querySelector(".mapped-code-line[data-source-line]")) return;
            activeSourceLine = sourceLine;
            popoverSourceLine = null;
            scope.querySelectorAll(".mapped-code-line.origin-highlight").forEach(item => item.classList.remove("origin-highlight"));
            scope.querySelectorAll(`.mapped-code-line[data-source-line="${sourceLine}"]`).forEach(item => item.classList.add("origin-highlight"));
            originSource.clear();
            originSource.highlight(sourceLine);
            if (originPopover) originPopover.hidden = true;
        };
        const binding = { highlightSource, clear };
        if (options.source?.type === "readonly") resultOriginBinding = binding;
        else editorOriginBinding = binding;
        sourceLines.forEach(line => {
            line.addEventListener("focusin", () => highlight(line, null));
            line.addEventListener("focusout", event => {
                if (!line.contains(event.relatedTarget)) clear();
            });
        });
        scope.querySelectorAll(".mapped-code").forEach(panel => {
            panel.addEventListener("pointermove", event => {
                const hoveredLine = event.target.closest?.(".mapped-code-line[data-source-line]");
                if (!hoveredLine || !panel.contains(hoveredLine)) {
                    clear();
                    return;
                }
                highlight(hoveredLine, event);
            });
            panel.addEventListener("pointerleave", clear);
        });
    }
    function bindSourceOriginHighlights() {
        const editorWrapper = editor.getWrapperElement();
        editorWrapper.addEventListener("mousemove", event => {
            if (!editorOriginBinding) return;
            if (!event.target.closest?.(".CodeMirror-line, .CodeMirror-gutters")) {
                editorOriginBinding.clear();
                return;
            }
            const position = editor.coordsChar({ left: event.clientX, top: event.clientY }, "window");
            if (position.line < 0 || position.line >= editor.lineCount()) {
                editorOriginBinding.clear();
                return;
            }
            editorOriginBinding.highlightSource(position.line + 1);
        });
        editorWrapper.addEventListener("mouseleave", () => {
            if (editorOriginBinding) editorOriginBinding.clear();
        });
        const resultDetailElement = document.getElementById("result-detail");
        if (!resultDetailElement) return;
        resultDetailElement.addEventListener("pointermove", event => {
            if (!resultOriginBinding) return;
            const sourceRoot = event.target.closest?.(".result-source-code");
            if (!sourceRoot) return;
            const hoveredLine = event.target.closest?.(".readonly-code-line");
            if (!hoveredLine) {
                resultOriginBinding.clear();
                return;
            }
            const lines = sourceRoot.querySelectorAll(".readonly-code-line");
            const index = Array.prototype.indexOf.call(lines, hoveredLine);
            if (index >= 0) resultOriginBinding.highlightSource(index + 1);
        });
        resultDetailElement.addEventListener("pointerout", event => {
            if (!resultOriginBinding) return;
            const sourceRoot = event.target.closest?.(".result-source-code");
            if (sourceRoot && !sourceRoot.contains(event.relatedTarget)) resultOriginBinding.clear();
        });
    }
    bindSourceOriginHighlights();
    function moveTacPopover(event, popover) {
        const gap = 14;
        const width = popover.offsetWidth || 260;
        const left = Math.min(event.clientX + gap, window.innerWidth - width - gap);
        const top = Math.min(event.clientY + gap, window.innerHeight - popover.offsetHeight - gap);
        popover.style.left = `${Math.max(gap, left)}px`;
        popover.style.top = `${Math.max(gap, top)}px`;
    }
    function renderPhase() {
        const index = phaseOrder.indexOf(currentPhase);
        clearAstHighlight();
        document.getElementById("phase-title").textContent = phaseNames[currentPhase];
        document.getElementById("phase-count").textContent = `${index + 1} de ${phaseOrder.length}`;
        document.querySelectorAll(".step").forEach(step => {
            const active = step.dataset.phase === currentPhase;
            step.classList.toggle("active", active);
            step.setAttribute("aria-current", active ? "step" : "false");
        });
        if (currentPhase === "code") content.innerHTML = `${result ? diagnosticsOutput(result.diagnosticos || []) : ""}<div class="phase-placeholder"><strong>Seu ponto de partida</strong><p>Edite o programa à esquerda e compile para liberar as próximas fases.</p></div>`;
        else if (!result) content.innerHTML = `<div class="phase-placeholder"><strong>Compile primeiro</strong><p>Os dados desta fase aparecerão aqui.</p></div>`;
        else if (currentPhase === "tokens") content.innerHTML = `<div class="phase-explainer">${explain.tokens}</div><div class="table-scroll"><table class="data-table"><thead><tr><th>Tipo</th><th>Lexema</th><th>Linha</th><th>Coluna</th></tr></thead><tbody>${result.tokens.map(token => `<tr><td>${escape(token.type)}</td><td><code>${escape(token.lexeme)}</code></td><td>${token.line}</td><td>${token.column}</td></tr>`).join("")}</tbody></table></div>`;
        else if (currentPhase === "ast") content.innerHTML = `<div class="phase-explainer">${explain.ast}</div><div id="ast-phase-view" class="ast-mount"></div>`;
        else if (currentPhase === "symbols") content.innerHTML = `<div class="phase-explainer">${explain.symbols}</div>${json(result.tabela_simbolos)}`;
        else if (currentPhase === "tac") content.innerHTML = `<div class="phase-explainer">${explain.tac}</div><div class="tac-toolbar"><span>Nível selecionado: <b>${optimizationLevel}</b></span><button class="btn secondary" id="compare-tac">Comparar antes/depois</button></div>${result.tac ? mappedCode("Código intermediário", result.tac, result.tac_origin, "tac") : `<p class="hint">Nenhum TAC foi gerado porque há erros no programa.</p>`}`;
        else if (currentPhase === "cpp") content.innerHTML = `<div class="phase-explainer">${explain.cpp}</div>${result.cpp ? mappedCode("Código C++ gerado", result.cpp, result.cpp_origin, "cpp") : `<p class="hint">Nenhum C++ foi gerado porque há erros no programa.</p>`}`;
        else content.innerHTML = execution ? `<div class="phase-explainer">${explain.execution}</div><div class="execution"><p class="hint">Tempo: ${Number(execution.tempo || 0).toFixed(3)} s · código de saída: ${execution.exit_code ?? "—"}</p><div class="execution-grid"><div class="execution-box"><h3>STDOUT</h3><pre>${escape(execution.stdout)}</pre></div><div class="execution-box"><h3>STDERR</h3><pre>${escape(execution.stderr)}</pre></div></div></div>` : `<div class="phase-placeholder"><strong>Ainda não executado</strong><p>Clique em Executar para ver stdout, stderr e tempo.</p></div>`;
        if (currentPhase === "ast" && result && result.ast) {
            const astHost = document.getElementById("ast-phase-view");
            if (astHost) {
                if (window.MiniParAstView) {
                    window.MiniParAstView.mount(astHost, result.ast, {
                        onSelect: node => highlightAstNode(node),
                    });
                } else {
                    astHost.innerHTML = json(result.ast);
                }
            }
        }
        const compareButton = document.getElementById("compare-tac");
        if (compareButton) compareButton.addEventListener("click", compareTac);
        bindOriginHighlights({ scope: content, source: { type: "editor" } });
        bindPhaseDiagnostics();
    }
    async function compareTac() {
        if (!result || !result.tac) return;
        const compareButton = document.getElementById("compare-tac");
        if (compareButton) compareButton.disabled = true;
        try {
            const response = await fetch("/api/otimizar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue(), optimization_level: optimizationLevel }) });
            const optimized = await response.json();
            if (!optimized.success) { setStatus("Não foi possível otimizar o TAC", true); return; }
            content.innerHTML = `<div class="phase-explainer">${explain.tac}</div><div class="comparison">${mappedCode("TAC antes", optimized.tac, optimized.tac_origin, "tac")}${mappedCode(`TAC depois (${optimizationLevel})`, optimized.tac_optimized, optimized.optimized_tac_origin, "tac")}</div>`;
            bindOriginHighlights({ scope: content, source: { type: "editor" } });
        } catch (error) { setStatus("Falha ao comparar TAC", true); }
        finally { if (compareButton) compareButton.disabled = false; }
    }
    async function optimizeForLevel(code, level) {
        const response = await fetch("/api/otimizar", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ code, optimization_level: level }),
        });
        if (!response.ok) throw new Error("Falha na otimização");
        return response.json();
    }
    async function loadExamples() {
        const response = await fetch("/api/tests"); const data = await response.json();
        availableTests = data.tests;
        examples.innerHTML = `<option value="">Escolher um exemplo pronto</option>` + data.tests.map(name => `<option value="${escape(name)}">${escape(name)}</option>`).join("");
        const metric = document.getElementById("metric-tests");
        if (metric) metric.textContent = data.tests.length;
        const dashboardExample = document.getElementById("dashboard-example");
        if (dashboardExample) dashboardExample.innerHTML = data.tests.map(name => `<option>${escape(name)}</option>`).join("");
    }
    async function loadExample(filename) {
        const response = await fetch("/api/get_test", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ filename }) });
        const data = await response.json();
        editor.setValue(data.code || "");
        document.getElementById("current-file").textContent = filename;
        result = null; execution = null; markDiagnostics([]); currentPhase = "code"; renderPhase();
        showPage("ide"); setStatus("Exemplo carregado");
    }
    async function compile() {
        const button = document.getElementById("compile-button") || document.getElementById("editor-compile"); button.disabled = true; setStatus("Compilando...");
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
        if (runInProgress) return;
        runInProgress = true;
        const buttons = [document.getElementById("compile-button"), document.getElementById("editor-compile")].filter(Boolean);
        buttons.forEach(button => button.disabled = true);
        setStatus("Compilando e executando...");
        try {
            const compileResponse = await fetch("/api/compilar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue() }) });
            result = await compileResponse.json();
            execution = null;
            markDiagnostics(result.diagnosticos || []);
            if (!result.success) { currentPhase = "code"; setStatus("Há erros no programa", true); renderPhase(); return; }
            const inputs = programInput.value.split(/\r?\n/).filter(line => line.length > 0);
            const response = await fetch("/api/executar", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ code: editor.getValue(), inputs }) });
            execution = await response.json();
            history.unshift({ file: document.getElementById("current-file").textContent, source: editor.getValue(), inputs: programInput.value, diagnosticos: result.diagnosticos || [], compileResult: result, optimization: optimizationLevel, success: Boolean(execution.success), time: Number(execution.tempo || 0), execution });
            renderHistory();
            renderDashboard();
            currentPhase = "execution"; setStatus(execution.success ? "Execução concluída" : "Execução terminou com erro", !execution.success); renderPhase();
        } catch (error) { setStatus("Não foi possível executar", true); }
        finally {
            runInProgress = false;
            buttons.forEach(button => button.disabled = false);
        }
    }
    async function loadBenchmarkHardware() {
        const hardware = document.getElementById("benchmark-hardware");
        const coreSelect = document.getElementById("benchmark-cores");
        try {
            const response = await fetch("/api/hardware");
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Falha ao detectar hardware");
            const available = Math.max(1, Number(data.available_cores));
            const benchmarkMax = Math.max(
                1,
                Math.min(available, Number(data.benchmark_max_cores)),
            );
            hardware.textContent = `${data.logical_cores} lógicos · ${available} disponíveis`;
            coreSelect.innerHTML = Array.from(
                { length: benchmarkMax },
                (_, index) => `<option value="${index + 1}">${index + 1}</option>`,
            ).join("");
            coreSelect.value = String(benchmarkMax);
        } catch (error) {
            hardware.textContent = "Hardware indisponível";
            document.getElementById("benchmark-status").textContent =
                error instanceof Error ? error.message : "Falha ao detectar hardware";
        }
    }
    function renderBenchmarkResult(result, csvUrl) {
        const summary = document.getElementById("benchmark-summary");
        const results = document.getElementById("benchmark-results");
        const parameters = result.parameters;
        const format = value => Number(value).toFixed(3);
        const warnings = result.warnings.length
            ? `<ul>${result.warnings.map(message => `<li>${escape(message)}</li>`).join("")}</ul>`
            : "";
        summary.innerHTML = `
            <div class="benchmark-summary-item"><span>Atividades</span><strong>${parameters.total_atividades}</strong></div>
            <div class="benchmark-summary-item"><span>Tempo sequencial · mediana</span><strong>${format(result.sequential_seconds)} s</strong></div>
            <div class="benchmark-summary-item"><span>Tempo paralelo · mediana</span><strong>${format(result.parallel_seconds)} s</strong></div>
            <div class="benchmark-summary-item"><span>Speedup</span><strong>${format(result.speedup)}×</strong></div>
            <div class="benchmark-summary-item"><span>Eficiência</span><strong>${format(result.efficiency_percent)}%</strong></div>
            ${warnings}`;
        document.getElementById("benchmark-cores-result").innerHTML =
            result.cores.map(core => `
                <tr>
                    <td>${core.core}</td>
                    <td>${core.task_count}</td>
                    <td>${format(core.busy_seconds)}</td>
                    <td>${format(core.utilization_percent)}%</td>
                </tr>`).join("");
        const csvLink = document.getElementById("benchmark-csv");
        csvLink.href = csvUrl;
        csvLink.hidden = false;
        results.hidden = false;
    }
    async function runBenchmark() {
        const button = document.getElementById("benchmark-run");
        const status = document.getElementById("benchmark-status");
        const results = document.getElementById("benchmark-results");
        button.disabled = true;
        results.hidden = true;
        status.textContent = "Enfileirando benchmark…";
        try {
            const payload = {
                alunos: Number(document.getElementById("benchmark-students").value),
                atividades: Number(document.getElementById("benchmark-activities").value),
                nucleos: Number(document.getElementById("benchmark-cores").value),
                fractais: Number(document.getElementById("benchmark-fractals").value),
                repeticoes: Number(document.getElementById("benchmark-repetitions").value),
            };
            const response = await fetch("/api/benchmark", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload),
            });
            const created = await response.json();
            if (!response.ok) throw new Error(created.error || "Não foi possível iniciar o benchmark.");
            while (true) {
                await new Promise(resolve => window.setTimeout(resolve, 300));
                const pollResponse = await fetch(created.status_url);
                const job = await pollResponse.json();
                if (!pollResponse.ok) throw new Error(job.error || "Falha ao consultar o benchmark.");
                status.textContent = `${job.message} · ${job.progress}%`;
                if (job.status === "failed") throw new Error(job.error || "O benchmark falhou.");
                if (job.status === "completed") {
                    renderBenchmarkResult(job.result, job.csv_url);
                    status.textContent = "Benchmark concluído.";
                    return;
                }
            }
        } catch (error) {
            status.textContent = error instanceof Error ? error.message : "Falha ao executar benchmark.";
        } finally {
            button.disabled = false;
        }
    }
    editor.on("change", () => {
        if (!result && !execution && !markers.length) return;
        result = null;
        execution = null;
        markDiagnostics([]);
        currentPhase = "code";
        if (!runInProgress) setStatus("Código alterado — pronto para executar");
        renderPhase();
    });
    examples.addEventListener("change", async event => {
        if (!event.target.value) return;
        await loadExample(event.target.value);
    });
    document.getElementById("dashboard-analyze")?.addEventListener("click", async () => {
        const selectedExample = document.getElementById("dashboard-example").value;
        if (!selectedExample) {
            setStatus("Escolha um programa antes de analisar", true);
            return;
        }
        await loadExample(selectedExample);
    });
    document.getElementById("benchmark-run").addEventListener("click", runBenchmark);
    document.getElementById("compile-button").addEventListener("click", run);
    document.getElementById("editor-compile").addEventListener("click", run);
    editor.getWrapperElement().addEventListener("keydown", event => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            run();
        }
    });
    document.getElementById("clear-button").addEventListener("click", () => {
        editor.setValue("");
        programInput.value = "";
        examples.value = "";
        document.getElementById("current-file").textContent = "ide_temp.minipar";
        result = null;
        execution = null;
        markDiagnostics([]);
        currentPhase = "code";
        syncOptimization(localStorage.getItem("minipar-optimization") || defaultOptimization);
        renderPhase();
        setStatus("Editor limpo");
    });
    navItems.forEach(item => item.addEventListener("click", () => showPage(item.dataset.page)));
    document.querySelectorAll("[data-page-target]").forEach(button => button.addEventListener("click", () => showPage(button.dataset.pageTarget)));
    document.querySelectorAll(".step").forEach(step => step.addEventListener("click", async () => {
        currentPhase = step.dataset.phase;
        renderPhase();
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
    document.getElementById("back-to-results").addEventListener("click", () => showPage("results"));
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
        localStorage.setItem("minipar-theme", document.body.classList.contains("light-theme") ? "dark" : "light");
        syncTheme();
    });
    const initialPage = ["results", "result-detail", "configuration", "ide", "pipeline"].includes(window.location.hash.slice(1)) ? window.location.hash.slice(1) : "dashboard";
    loadExamples(); loadBenchmarkHardware(); renderPhase(); renderDashboard(); syncTheme(); showPage(initialPage);
});
