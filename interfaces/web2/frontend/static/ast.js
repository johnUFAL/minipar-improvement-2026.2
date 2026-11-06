/* Renderizador didático da AST do MiniPar em SVG puro.
   Sem dependências externas: layout, zoom, pan, recolhimento, tooltips e
   exportação para SVG/PNG são implementados aqui. */
(function (global) {
    "use strict";

    const META = new Set(["tipo", "line", "column", "tipo_inferido"]);
    const NODE_H = 42;
    const NODE_GAP_X = 18;
    const LEVEL_GAP_Y = 74;
    const PADDING = 40;

    const COLORS = {
        block: { fill: "#eef2ff", stroke: "#6366f1", text: "#312e81" },
        decl: { fill: "#f0fdfa", stroke: "#0d9488", text: "#115e59" },
        stmt: { fill: "#fffbeb", stroke: "#d97706", text: "#92400e" },
        expr: { fill: "#eff6ff", stroke: "#2563eb", text: "#1e40af" },
        literal: { fill: "#f0fdf4", stroke: "#16a34a", text: "#166534" },
        ident: { fill: "#faf5ff", stroke: "#9333ea", text: "#6b21a8" },
    };

    const LABELS = {
        Program: () => "Programa",
        SeqBlock: () => "SEQ",
        ParBlock: () => "PAR",
        NumberExpr: (n) => String(n.value),
        StringExpr: (n) => '"' + truncate(String(n.value), 18) + '"',
        CharExpr: (n) => "'" + String(n.value) + "'",
        BoolExpr: (n) => String(n.value),
        IdentifierExpr: (n) => n.name,
        ThisExpr: () => "this",
        BinaryExpr: (n) => n.op,
        UnaryExpr: (n) => n.op,
        VarDecl: (n) => "var " + n.name,
        AttributeDecl: (n) => "atributo " + n.name,
        Assignment: (n) => n.name + " =",
        PropertyAssign: (n) => "." + n.property_name + " =",
        PrintStmt: () => "print",
        IfStmt: () => "if",
        WhileStmt: () => "while",
        DoWhileStmt: () => "do-while",
        ForStmt: (n) => (n.iterator_name ? "for " + n.iterator_name : "for"),
        BreakStmt: () => "break",
        ContinueStmt: () => "continue",
        ReturnStmt: () => "return",
        ClassDecl: (n) => "class " + n.name,
        ChannelDecl: (n) => "canal " + n.name,
        ForkStmt: (n) => "fork " + n.task_name,
        JoinStmt: (n) => "join " + (n.task_names || []).join(", "),
        Parameter: (n) => n.name + ": " + n.type,
        FuncDecl: (n) => "func " + n.name + "()",
        MethodDecl: (n) => "método " + n.name + "()",
        MethodCall: (n) => "." + n.method_name + "()",
        FuncCallExpr: (n) => n.name + "()",
        PropertyAccess: (n) => "." + n.property_name,
        NewExpr: (n) => "new " + n.class_name,
        CChannelExpr: () => "c_channel",
        SendStmt: () => "send",
        ReceiveExpr: () => "receive",
        InputExpr: () => "input",
        ListLiteral: () => "[ lista ]",
        MatrixCreateExpr: () => "matrix",
        IndexExpr: () => "índice [ ]",
        IndexAssign: () => "índice [ ] =",
    };

    const DETAILS = {
        NumberExpr: () => "número",
        StringExpr: () => "string",
        CharExpr: () => "char",
        BoolExpr: () => "bool",
        IdentifierExpr: () => "identificador",
        BinaryExpr: () => "operação binária",
        UnaryExpr: () => "operação unária",
        VarDecl: (n) => (n.type && n.type !== "var" ? "tipo " + n.type : ""),
        AttributeDecl: (n) => (n.type && n.type !== "var" ? "tipo " + n.type : ""),
        Assignment: () => "atribuição",
        PrintStmt: () => "saída",
        IfStmt: () => "decisão",
        WhileStmt: () => "repetição",
        ForStmt: () => "repetição",
        ReturnStmt: () => "retorno",
        ClassDecl: (n) => (n.superclass ? "extends " + n.superclass : "classe"),
        FuncDecl: (n) => (n.return_type ? "retorna " + n.return_type : "função"),
        MethodDecl: (n) => (n.return_type ? "retorna " + n.return_type : "método"),
        ForkStmt: (n) => (n.target_kind ? "em " + n.target_kind : "tarefa paralela"),
        JoinStmt: () => "sincronização",
        ChannelDecl: (n) => n.first_host + " ↔ " + n.second_host,
    };

    function truncate(text, size) {
        return text.length > size ? text.slice(0, size - 1) + "…" : text;
    }

    function classify(tipo) {
        if (tipo === "Program" || /Block$/.test(tipo)) return "block";
        if (/Decl$/.test(tipo) || tipo === "Parameter") return "decl";
        if (/Stmt$/.test(tipo)) return "stmt";
        if (/Literal$/.test(tipo)) return "literal";
        if (/Number|String|Char|Bool/.test(tipo) && /Expr$/.test(tipo)) return "literal";
        if (tipo === "IdentifierExpr" || tipo === "ThisExpr") return "ident";
        return "expr";
    }

    function isNode(value) {
        return (
            value &&
            typeof value === "object" &&
            !Array.isArray(value) &&
            typeof value.tipo === "string"
        );
    }

    function scalarDetail(value) {
        const parts = [];
        for (const [key, raw] of Object.entries(value)) {
            if (META.has(key) || raw === null || raw === undefined) continue;
            if (typeof raw === "object") continue;
            if (key === "name" || key === "op" || key === "value") continue;
            if (raw === "" || raw === "var" || raw === false) continue;
            parts.push(key + ": " + raw);
        }
        return parts.slice(0, 2).join(" · ");
    }

    let nextId = 1;

    function buildNode(value) {
        const tipo = value.tipo;
        const kind = classify(tipo);
        const labelFn = LABELS[tipo] || (() => tipo);
        const detailFn = DETAILS[tipo] || (() => "");
        let label = "";
        let detail = "";
        try {
            label = String(labelFn(value));
        } catch (error) {
            label = tipo;
        }
        try {
            detail = String(detailFn(value) || scalarDetail(value));
        } catch (error) {
            detail = "";
        }
        label = truncate(label, 30);
        detail = truncate(detail, 34);

        const children = [];
        for (const [key, raw] of Object.entries(value)) {
            if (META.has(key)) continue;
            if (isNode(raw)) {
                children.push(buildNode(raw));
            } else if (Array.isArray(raw)) {
                for (const item of raw) {
                    if (isNode(item)) children.push(buildNode(item));
                }
            }
        }

        const width = Math.max(
            86,
            Math.min(250, Math.max(label.length * 7.6, detail.length * 5.8) + 28)
        );

        return {
            id: nextId++,
            tipo,
            kind,
            label,
            detail,
            width,
            children,
            collapsed: false,
            x: 0,
            y: 0,
            subtreeWidth: 0,
            meta: {
                line: value.line,
                column: value.column,
                inferred: value.tipo_inferido,
            },
        };
    }

    function computeWidths(node) {
        if (node.collapsed || node.children.length === 0) {
            node.subtreeWidth = node.width;
            return node.subtreeWidth;
        }
        let total = 0;
        for (const child of node.children) {
            total += computeWidths(child);
        }
        total += NODE_GAP_X * (node.children.length - 1);
        node.subtreeWidth = Math.max(node.width, total);
        return node.subtreeWidth;
    }

    function position(node, left, depth) {
        node.y = depth * (NODE_H + LEVEL_GAP_Y);
        node.x = left + node.subtreeWidth / 2;
        if (node.collapsed || node.children.length === 0) return;

        let childrenWidth = 0;
        for (const child of node.children) {
            childrenWidth += child.subtreeWidth;
        }
        childrenWidth += NODE_GAP_X * (node.children.length - 1);

        let cursor = left + (node.subtreeWidth - childrenWidth) / 2;
        for (const child of node.children) {
            position(child, cursor, depth + 1);
            cursor += child.subtreeWidth + NODE_GAP_X;
        }
    }

    function visibleNodes(root) {
        const nodes = [];
        const edges = [];
        (function walk(node) {
            nodes.push(node);
            if (!node.collapsed) {
                for (const child of node.children) {
                    edges.push([node, child]);
                    walk(child);
                }
            }
        })(root);
        return { nodes, edges };
    }

    function bounds(nodes) {
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const node of nodes) {
            minX = Math.min(minX, node.x - node.width / 2);
            maxX = Math.max(maxX, node.x + node.width / 2);
            minY = Math.min(minY, node.y);
            maxY = Math.max(maxY, node.y + NODE_H);
        }
        return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
    }

    function svgEl(name, attrs) {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        if (attrs) {
            for (const [key, value] of Object.entries(attrs)) {
                element.setAttribute(key, String(value));
            }
        }
        return element;
    }

    function createRenderer(container, tooltip) {
        const state = {
            root: null,
            scale: 1,
            tx: 0,
            ty: 0,
            svg: null,
            viewport: null,
            bounds: null,
            dragging: false,
            dragStart: null,
            expandedSnapshot: null,
        };

        function clear() {
            container.innerHTML = "";
            tooltip.classList.add("hidden");
            state.svg = null;
            state.viewport = null;
            state.root = null;
        }

        function showPlaceholder(message) {
            clear();
            const box = document.createElement("div");
            box.className = "placeholder";
            box.innerHTML = "<strong>Nada para mostrar</strong><span></span>";
            box.querySelector("span").textContent = message;
            container.appendChild(box);
        }

        function renderTree(root) {
            state.root = root;
            nextId = 1;
            computeWidths(root);
            position(root, 0, 0);
            draw();
        }

        function draw(refit) {
            if (!state.root) return;
            const { nodes, edges } = visibleNodes(state.root);
            const box = bounds(nodes);
            state.bounds = box;

            const width = Math.max(320, container.clientWidth || 800);
            const height = Math.max(280, container.clientHeight || 420);

            const svg = svgEl("svg", {
                width: "100%",
                height: "100%",
                viewBox: `0 0 ${width} ${height}`,
                preserveAspectRatio: "xMidYMid meet",
            });
            const viewport = svgEl("g", { class: "ast-viewport" });

            for (const [parent, child] of edges) {
                const x1 = parent.x;
                const y1 = parent.y + NODE_H;
                const x2 = child.x;
                const y2 = child.y;
                const midY = (y1 + y2) / 2;
                const path = svgEl("path", {
                    class: "ast-edge",
                    d: `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`,
                });
                viewport.appendChild(path);
            }

            for (const node of nodes) {
                viewport.appendChild(drawNode(node));
            }

            svg.appendChild(viewport);
            container.innerHTML = "";
            container.appendChild(svg);
            state.svg = svg;
            state.viewport = viewport;
            applyTransform();
            if (refit !== false) fit(false);
        }

        function drawNode(node) {
            const palette = COLORS[node.kind] || COLORS.expr;
            const group = svgEl("g", {
                class: "ast-node",
                "data-id": node.id,
                transform: `translate(${node.x - node.width / 2}, ${node.y})`,
            });

            const rect = svgEl("rect", {
                width: node.width,
                height: NODE_H,
                rx: 10,
                ry: 10,
                fill: palette.fill,
                stroke: palette.stroke,
            });
            group.appendChild(rect);

            const hasDetail = Boolean(node.detail);
            const labelY = hasDetail ? 18 : 26;
            const label = svgEl("text", {
                x: node.width / 2,
                y: labelY,
                "text-anchor": "middle",
                fill: palette.text,
            });
            label.textContent = node.label;
            group.appendChild(label);

            if (hasDetail) {
                const detail = svgEl("text", {
                    x: node.width / 2,
                    y: 32,
                    "text-anchor": "middle",
                    fill: palette.text,
                    class: "node-detail",
                });
                detail.textContent = node.detail;
                group.appendChild(detail);
            }

            if (node.collapsed && node.children.length > 0) {
                const badge = svgEl("g", {
                    transform: `translate(${node.width - 4}, ${-4})`,
                });
                badge.appendChild(
                    svgEl("circle", {
                        r: 9,
                        fill: palette.stroke,
                        stroke: "#ffffff",
                        "stroke-width": 1.5,
                    })
                );
                const text = svgEl("text", {
                    x: 0,
                    y: 3.4,
                    "text-anchor": "middle",
                    fill: "#ffffff",
                    class: "ast-badge",
                });
                text.textContent = String(node.children.length);
                badge.appendChild(text);
                group.appendChild(badge);
            }

            group.addEventListener("click", (event) => {
                event.stopPropagation();
                if (node.children.length === 0) return;
                node.collapsed = !node.collapsed;
                computeWidths(state.root);
                position(state.root, 0, 0);
                draw(false);
            });

            group.addEventListener("mouseenter", (event) => showTooltip(node, event));
            group.addEventListener("mousemove", (event) => moveTooltip(event));
            group.addEventListener("mouseleave", () => tooltip.classList.add("hidden"));

            return group;
        }

        function showTooltip(node, event) {
            const parts = [
                `<strong>${escapeHtml(node.tipo)}</strong>`,
                `Linha ${node.meta.line ?? "?"}, coluna ${node.meta.column ?? "?"}`,
            ];
            if (node.meta.inferred) {
                parts.push(`Tipo inferido: <strong>${escapeHtml(node.meta.inferred)}</strong>`);
            }
            if (node.children.length) {
                parts.push(`${node.children.length} filho(s) — clique para recolher/expandir`);
            }
            tooltip.innerHTML = parts.join("<br>");
            tooltip.classList.remove("hidden");
            moveTooltip(event);
        }

        function moveTooltip(event) {
            const rect = container.getBoundingClientRect();
            const x = event.clientX - rect.left + 14;
            const y = event.clientY - rect.top + 14;
            tooltip.style.left = Math.min(x, rect.width - 300) + "px";
            tooltip.style.top = Math.min(y, rect.height - 90) + "px";
        }

        function applyTransform() {
            if (!state.viewport) return;
            state.viewport.setAttribute(
                "transform",
                `translate(${state.tx}, ${state.ty}) scale(${state.scale})`
            );
        }

        function fit(animate) {
            if (!state.bounds) return;
            const width = Math.max(320, container.clientWidth || 800);
            const height = Math.max(280, container.clientHeight || 420);
            const box = state.bounds;
            const scale = Math.min(
                (width - PADDING * 2) / Math.max(1, box.width),
                (height - PADDING * 2) / Math.max(1, box.height),
                1.35
            );
            state.scale = Math.max(0.15, scale);
            state.tx = width / 2 - ((box.minX + box.maxX) / 2) * state.scale;
            state.ty = PADDING - box.minY * state.scale;
            if (state.ty < 10) state.ty = 10;
            applyTransform();
        }

        function zoomBy(factor, centerX, centerY) {
            if (!state.viewport) return;
            const width = Math.max(320, container.clientWidth || 800);
            const height = Math.max(280, container.clientHeight || 420);
            const cx = centerX === undefined ? width / 2 : centerX;
            const cy = centerY === undefined ? height / 2 : centerY;
            const next = Math.min(3.5, Math.max(0.12, state.scale * factor));
            const ratio = next / state.scale;
            state.tx = cx - (cx - state.tx) * ratio;
            state.ty = cy - (cy - state.ty) * ratio;
            state.scale = next;
            applyTransform();
        }

        function setAllCollapsed(collapsed) {
            if (!state.root) return;
            (function walk(node, depth) {
                if (node.children.length > 0) {
                    node.collapsed = collapsed && depth > 0;
                }
                for (const child of node.children) walk(child, depth + 1);
            })(state.root, 0);
            computeWidths(state.root);
            position(state.root, 0, 0);
            draw(false);
        }

        function expandAll() {
            if (!state.root) return;
            (function walk(node) {
                node.collapsed = false;
                for (const child of node.children) walk(child);
            })(state.root);
            computeWidths(state.root);
            position(state.root, 0, 0);
            draw(false);
        }

        function exportSvg() {
            if (!state.svg || !state.bounds) return null;
            const box = state.bounds;
            const clone = state.svg.cloneNode(true);
            clone.setAttribute(
                "viewBox",
                `${box.minX - 30} ${box.minY - 30} ${box.width + 60} ${box.height + 60}`
            );
            clone.setAttribute("width", String(box.width + 60));
            clone.setAttribute("height", String(box.height + 60));
            const viewportClone = clone.querySelector(".ast-viewport");
            if (viewportClone) {
                viewportClone.setAttribute("transform", "translate(0,0) scale(1)");
            }

            const background = svgEl("rect", {
                x: box.minX - 30,
                y: box.minY - 30,
                width: box.width + 60,
                height: box.height + 60,
                fill: "#ffffff",
            });
            clone.insertBefore(background, clone.firstChild);

            return new XMLSerializer().serializeToString(clone);
        }

        function bindInteractions() {
            container.addEventListener(
                "wheel",
                (event) => {
                    if (!state.svg) return;
                    event.preventDefault();
                    const rect = container.getBoundingClientRect();
                    const factor = event.deltaY < 0 ? 1.12 : 0.89;
                    zoomBy(factor, event.clientX - rect.left, event.clientY - rect.top);
                },
                { passive: false }
            );

            container.addEventListener("pointerdown", (event) => {
                if (!state.svg) return;
                if (event.target.closest(".ast-node")) return;
                state.dragging = true;
                state.dragStart = {
                    x: event.clientX,
                    y: event.clientY,
                    tx: state.tx,
                    ty: state.ty,
                };
                container.classList.add("dragging");
                container.setPointerCapture(event.pointerId);
            });

            container.addEventListener("pointermove", (event) => {
                if (!state.dragging || !state.dragStart) return;
                state.tx = state.dragStart.tx + (event.clientX - state.dragStart.x);
                state.ty = state.dragStart.ty + (event.clientY - state.dragStart.y);
                applyTransform();
            });

            const stop = (event) => {
                state.dragging = false;
                state.dragStart = null;
                container.classList.remove("dragging");
                if (event.pointerId !== undefined) {
                    try {
                        container.releasePointerCapture(event.pointerId);
                    } catch (error) {
                        /* ignore */
                    }
                }
            };
            container.addEventListener("pointerup", stop);
            container.addEventListener("pointercancel", stop);

            window.addEventListener("resize", () => {
                if (state.root) draw(true);
            });
        }

        bindInteractions();

        return {
            show: renderTree,
            clear,
            showPlaceholder,
            fit: () => fit(true),
            zoomIn: () => zoomBy(1.2),
            zoomOut: () => zoomBy(0.84),
            expandAll,
            collapseAll: () => setAllCollapsed(true),
            exportSvg,
            hasTree: () => Boolean(state.root),
        };
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    global.MiniParAST = {
        buildNode,
        createRenderer,
    };
})(window);
