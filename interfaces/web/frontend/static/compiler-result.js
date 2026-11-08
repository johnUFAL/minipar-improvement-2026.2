document.addEventListener("DOMContentLoaded", () => {
    const HISTORY_KEY = "minipar-compiler-history";
    const detail = document.getElementById("result-detail");
    if (!detail) return;

    const phaseNames = {
        code: "Código",
        tokens: "Tokens",
        ast: "AST",
        symbols: "Tabela de símbolos",
        tac: "TAC",
        cpp: "C++",
        execution: "Execução",
    };
    const phaseOrder = Object.keys(phaseNames);
    const explain = {
        tokens: "Veja como o texto foi separado em unidades que o compilador consegue reconhecer.",
        ast: "A árvore sintática preserva a estrutura das expressões, comandos e blocos do programa.",
        symbols: "A tabela registra nomes, tipos e escopos encontrados na análise semântica.",
        tac: "O TAC transforma o programa em instruções simples, antes da geração do C++.",
        cpp: "Este é o código C++ produzido a partir do TAC e usado na execução.",
        execution: "Confira a saída do programa, os erros e o tempo medido pelo ambiente.",
    };

    let astReadonlyHighlights = [];
    let resultOriginBinding = null;

    const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    const format = value => Number(value || 0).toFixed(3);
    const json = value => `<pre class="json-output">${escape(JSON.stringify(value, null, 2))}</pre>`;

    function loadHistory() {
        try {
            const stored = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
            return Array.isArray(stored) ? stored : [];
        } catch (error) {
            return [];
        }
    }

    function formatDate(value) {
        const date = new Date(Number(value));
        return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
    }

    function entryId(item, index) {
        const identifier = item.id ?? item.created_at;
        return identifier === undefined || identifier === null || identifier === ""
            ? `index-${index}`
            : String(identifier);
    }

    function findEntry(runId) {
        const history = loadHistory();
        if (!runId || runId === "latest") return history[0] || null;
        if (runId.startsWith("index-")) {
            return history[Number(runId.slice("index-".length))] || null;
        }
        return history.find((item, index) => entryId(item, index) === runId) || null;
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
        astReadonlyHighlights.forEach(element => element.classList.remove("ast-source-highlight"));
        astReadonlyHighlights = [];
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

    function diagnosticsOutput(items) {
        if (!Array.isArray(items) || !items.length) return "";
        return `<div class="diagnostics phase-diagnostics" aria-live="polite"><strong>Diagnósticos encontrados</strong>${items.map(item => `<button class="diagnostic" data-line="${Math.max(0, Number(item.line || 1) - 1)}" data-column="${Math.max(0, Number(item.column || 1) - 1)}">${escape(item.header || item.message)} (linha ${item.line || 1}, coluna ${item.column || 1})</button>`).join("")}</div>`;
    }

    function bindPhaseDiagnostics() {
        const sourceRoot = detail.querySelector(".result-source-code");
        document.querySelectorAll(".phase-diagnostics .diagnostic").forEach(button => {
            button.addEventListener("click", () => {
                const target = sourceRoot?.querySelectorAll(".readonly-code-line")[Number(button.dataset.line)];
                if (!target) return;
                target.scrollIntoView({ block: "center" });
                target.classList.add("origin-highlight");
                window.setTimeout(() => target.classList.remove("origin-highlight"), 1200);
            });
        });
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

    function moveTacPopover(event, popover) {
        const gap = 14;
        const width = popover.offsetWidth || 260;
        const left = Math.min(event.clientX + gap, window.innerWidth - width - gap);
        const top = Math.min(event.clientY + gap, window.innerHeight - popover.offsetHeight - gap);
        popover.style.left = `${Math.max(gap, left)}px`;
        popover.style.top = `${Math.max(gap, top)}px`;
    }

    function bindOriginHighlights(options = {}) {
        const scope = options.scope || document;
        const originSource = createOriginSource(options.source || {});
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
        resultOriginBinding = binding;
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
        detail.addEventListener("pointermove", event => {
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
        detail.addEventListener("pointerout", event => {
            if (!resultOriginBinding) return;
            const sourceRoot = event.target.closest?.(".result-source-code");
            if (sourceRoot && !sourceRoot.contains(event.relatedTarget)) resultOriginBinding.clear();
        });
    }

    async function optimizeForLevel(code, level) {
        const response = await fetch("/api/otimizar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code, optimization_level: level }),
        });
        if (!response.ok) throw new Error("Falha na otimização");
        return response.json();
    }

    function renderMissing() {
        detail.innerHTML = `
            <div class="results-empty">
                <strong>Resultado não encontrado</strong>
                <p>Este histórico fica salvo apenas neste navegador. Volte e selecione uma execução disponível.</p>
                <a class="button button-outline" href="/resultados">Voltar ao histórico</a>
            </div>`;
    }

    function renderDetail(item) {
        const diagnostics = item.diagnosticos || item.compileResult?.diagnosticos || [];
        const errorLines = new Set(diagnostics.map(diagnostic => Number(diagnostic.line || 1)));
        const sourceLines = String(item.source || "(código não armazenado)").split("\n").map((line, index) => `<div class="readonly-code-line ${errorLines.has(index + 1) ? "readonly-error-line" : ""}"><span>${index + 1}</span><code>${escape(line) || " "}</code></div>`).join("");
        detail.innerHTML = `<div class="ide-grid result-ide-grid"><article class="editor-panel card readonly-editor-panel"><div class="panel-title"><span><span class="panel-mark"><svg class="icon" aria-hidden="true"><use href="#icon-code"></use></svg></span> Código-fonte</span><small>MINIPAR · SOMENTE LEITURA</small></div><div class="detail-file-label">${escape(item.file)}</div><div class="readonly-code result-source-code" aria-label="Código-fonte somente leitura">${sourceLines}</div><div class="input-area readonly-input"><label>ENTRADAS DO PROGRAMA <span>stdin · preservadas da execução</span></label><pre class="program-input">${escape(item.inputs || "(sem entrada)")}</pre></div></article><article class="phase-panel card result-phase-panel"><div class="panel-title"><span><span class="panel-mark"><svg class="icon" aria-hidden="true"><use href="#icon-layers"></use></svg></span> <b id="result-phase-title">Execução</b></span><small>RESULTADO PRESERVADO</small></div><nav class="phase-nav result-phase-nav" aria-label="Fases do resultado">${phaseOrder.map((phase, index) => `<button type="button" class="step ${phase === "execution" ? "active" : ""}" data-result-phase="${phase}"><span>${String(index + 1).padStart(2, "0")}</span><b>${phaseNames[phase]}</b></button>`).join("")}</nav><div id="result-phase-content" class="phase-content" role="region" aria-live="polite"></div></article></div>`;

        const resultPhaseContent = document.getElementById("result-phase-content");
        const resultPhaseTitle = document.getElementById("result-phase-title");
        const compileResult = item.compileResult || {};
        const execution = item.execution || null;
        const sourceRoot = detail.querySelector(".result-source-code");

        const renderResultPhase = phase => {
            clearAstHighlight();
            if (resultPhaseTitle) resultPhaseTitle.textContent = phaseNames[phase];
            document.querySelectorAll("[data-result-phase]").forEach(step => step.classList.toggle("active", step.dataset.resultPhase === phase));
            if (!resultPhaseContent) return;
            if (phase === "code") {
                resultPhaseContent.innerHTML = diagnosticsOutput(diagnostics) || `<div class="phase-placeholder"><strong>Código-fonte preservado</strong><p>Este programa não pode ser editado nesta tela.</p></div>`;
            } else if (phase === "tokens") {
                resultPhaseContent.innerHTML = compileResult.tokens?.length ? `<div class="phase-explainer">${explain.tokens}</div><div class="table-scroll"><table class="data-table"><thead><tr><th>Tipo</th><th>Lexema</th><th>Linha</th><th>Coluna</th></tr></thead><tbody>${compileResult.tokens.map(token => `<tr><td>${escape(token.type)}</td><td><code>${escape(token.lexeme)}</code></td><td>${token.line}</td><td>${token.column}</td></tr>`).join("")}</tbody></table></div>` : `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
            } else if (phase === "ast") {
                if (compileResult.ast) {
                    resultPhaseContent.innerHTML = `<div class="phase-explainer">${explain.ast}</div><div id="result-ast-view" class="ast-mount"></div>`;
                    const astHost = resultPhaseContent.querySelector("#result-ast-view");
                    if (astHost) {
                        if (window.MiniParAstView) {
                            window.MiniParAstView.mount(astHost, compileResult.ast, {
                                onSelect: node => highlightReadonlyAstNode(node, sourceRoot),
                            });
                        } else {
                            astHost.innerHTML = json(compileResult.ast);
                        }
                    }
                } else {
                    resultPhaseContent.innerHTML = `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
                }
            } else if (phase === "symbols") {
                resultPhaseContent.innerHTML = compileResult.tabela_simbolos ? `<div class="phase-explainer">${explain.symbols}</div>${json(compileResult.tabela_simbolos)}` : `<div class="phase-placeholder"><strong>Dados não armazenados</strong></div>`;
            } else if (phase === "tac") {
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
                            bindOriginHighlights({ scope: resultPhaseContent, source: { type: "readonly", code: item.source, root: sourceRoot } });
                        } catch (error) {
                            comparison.innerHTML = `<p class="hint error">Não foi possível gerar a comparação.</p>`;
                        } finally {
                            compareButton.disabled = false;
                        }
                    });
                }
            } else if (phase === "cpp") {
                const cpp = compileResult.cpp || item.cpp || "";
                resultPhaseContent.innerHTML = cpp ? `<div class="phase-explainer">${explain.cpp}</div>${mappedCode("Código C++ gerado", cpp, compileResult.cpp_origin, "cpp")}` : `<div class="phase-placeholder"><strong>Nenhum C++ foi gerado</strong></div>`;
            } else if (execution) {
                resultPhaseContent.innerHTML = `<div class="phase-explainer">${explain.execution}</div><div class="execution"><p class="hint">Tempo: ${format(item.time)} s · código de saída: ${execution.exit_code ?? "—"}</p><div class="execution-grid"><div class="execution-box"><h3>STDOUT</h3><pre>${escape(execution.stdout || "(sem saída)")}</pre></div><div class="execution-box"><h3>STDERR</h3><pre>${escape(execution.stderr || "(sem erros)")}</pre></div></div></div>`;
            } else {
                resultPhaseContent.innerHTML = `<div class="phase-placeholder"><strong>Ainda não executado</strong><p>Esta compilação terminou com diagnóstico e não gerou saída.</p></div>`;
            }
            bindOriginHighlights({ scope: resultPhaseContent, source: { type: "readonly", code: item.source, root: sourceRoot } });
            bindPhaseDiagnostics();
        };

        document.querySelectorAll("[data-result-phase]").forEach(step => step.addEventListener("click", () => renderResultPhase(step.dataset.resultPhase)));
        renderResultPhase("execution");
        document.title = `${item.file || "Resultado"} — MiniPar 2026.2`;
    }

    bindSourceOriginHighlights();

    const requested = String(detail.dataset.runId || "");
    const item = findEntry(requested);
    if (item) {
        renderDetail(item);
        if (requested === "latest") {
            const history = loadHistory();
            const index = history.indexOf(item);
            window.history.replaceState({}, "", `/resultados/${encodeURIComponent(entryId(item, index))}`);
        }
    } else {
        renderMissing();
    }
});
