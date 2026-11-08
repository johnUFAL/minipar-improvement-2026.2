(function (global) {
    "use strict";

    const CATEGORIES = {
        declaracao: { label: "Declaração" },
        expressao: { label: "Expressão" },
        controle: { label: "Controle" },
        paralelo: { label: "Paralelo" },
    };

    const CATEGORY_BY_TYPE = {
        Program: "declaracao",
        VarDecl: "declaracao",
        AttributeDecl: "declaracao",
        Parameter: "declaracao",
        FuncDecl: "declaracao",
        MethodDecl: "declaracao",
        ClassDecl: "declaracao",
        NumberExpr: "expressao",
        StringExpr: "expressao",
        BoolExpr: "expressao",
        IdentifierExpr: "expressao",
        BinaryExpr: "expressao",
        UnaryExpr: "expressao",
        PropertyAccess: "expressao",
        MethodCall: "expressao",
        FuncCallExpr: "expressao",
        NewExpr: "expressao",
        ThisExpr: "expressao",
        InputExpr: "expressao",
        ListLiteral: "expressao",
        MatrixCreateExpr: "expressao",
        IndexExpr: "expressao",
        SeqBlock: "controle",
        IfStmt: "controle",
        WhileStmt: "controle",
        DoWhileStmt: "controle",
        ForStmt: "controle",
        BreakStmt: "controle",
        ContinueStmt: "controle",
        ReturnStmt: "controle",
        PrintStmt: "controle",
        Assignment: "controle",
        PropertyAssign: "controle",
        IndexAssign: "controle",
        ParBlock: "paralelo",
        ForkStmt: "paralelo",
        JoinStmt: "paralelo",
        SendStmt: "paralelo",
        ReceiveExpr: "paralelo",
        ChannelDecl: "paralelo",
        CChannelExpr: "paralelo",
    };

    const META_FIELDS = new Set([
        "tipo",
        "categoria",
        "line",
        "column",
        "tipo_inferido",
    ]);

    const TOGGLE_EXPANDED = "\u25be";
    const TOGGLE_COLLAPSED = "\u25b8";
    const GRAPH_VARIANTS = {
        detailed: {
            nodeWidth: 250,
            nodeHeight: 32,
            hGap: 112,
            vGap: 58,
            pad: 28,
        },
        compact: {
            nodeWidth: 82,
            nodeHeight: 82,
            hGap: 104,
            vGap: 54,
            pad: 30,
        },
    };

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function asInt(value, fallback) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
    }

    function isNode(value) {
        return Boolean(
            value &&
                typeof value === "object" &&
                !Array.isArray(value) &&
                typeof value.tipo === "string"
        );
    }

    function categoryOf(node) {
        if (!node) return "controle";
        if (typeof node.categoria === "string" && CATEGORIES[node.categoria]) {
            return node.categoria;
        }
        if (node.tipo === "FuncCallExpr" || node.tipo === "MethodCall") {
            const name = node.name || node.method_name;
            if (name === "send" || name === "receive") return "paralelo";
        }
        return CATEGORY_BY_TYPE[node.tipo] || "controle";
    }

    function childEntries(node) {
        const entries = [];
        Object.keys(node).forEach(function (key) {
            if (META_FIELDS.has(key)) return;
            const value = node[key];
            if (isNode(value)) {
                entries.push({ field: key, index: null, node: value });
            } else if (Array.isArray(value)) {
                value.forEach(function (item, index) {
                    if (isNode(item)) {
                        entries.push({ field: key, index: index, node: item });
                    }
                });
            }
        });
        return entries;
    }

    function scalarText(value) {
        if (Array.isArray(value)) {
            return value.map(scalarText).join(", ");
        }
        if (value === true) return "true";
        if (value === false) return "false";
        return String(value);
    }

    function truncate(value, limit) {
        const text = String(value);
        if (text.length <= limit) return text;
        return text.slice(0, Math.max(0, limit - 1)) + "\u2026";
    }

    function summaryEntries(node) {
        const entries = [];
        Object.keys(node).forEach(function (key) {
            if (META_FIELDS.has(key)) return;
            const value = node[key];
            if (value === null || value === undefined || value === "") return;
            if (isNode(value)) return;
            if (Array.isArray(value)) {
                if (!value.length || value.some(isNode)) return;
                entries.push([key, truncate(scalarText(value), 60)]);
                return;
            }
            if (typeof value === "object") return;
            entries.push([key, truncate(scalarText(value), 60)]);
        });
        return entries;
    }

    function detailEntries(node) {
        const entries = [];
        Object.keys(node).forEach(function (key) {
            if (META_FIELDS.has(key)) return;
            const value = node[key];
            if (value === null || value === undefined || value === "") return;
            if (isNode(value)) return;
            if (Array.isArray(value)) {
                if (!value.length || value.some(isNode)) return;
                entries.push([key, scalarText(value)]);
                return;
            }
            if (typeof value === "object") return;
            entries.push([key, scalarText(value)]);
        });
        return entries;
    }

    function searchableText(node) {
        const parts = [node.tipo || "", categoryOf(node)];
        summaryEntries(node).forEach(function (entry) {
            parts.push(entry[0], entry[1]);
        });
        return parts.join(" ").toLowerCase();
    }

    function ownLength(node) {
        const tipo = node.tipo;
        switch (tipo) {
            case "NumberExpr":
                return Math.max(1, String(node.value || "").length);
            case "StringExpr": {
                const value = node.value === null || node.value === undefined
                    ? ""
                    : String(node.value);
                if (/^(['"]).*\1$/.test(value)) return Math.max(1, value.length);
                return Math.max(1, value.length + 2);
            }
            case "BoolExpr":
                return node.value ? 4 : 5;
            case "IdentifierExpr":
                return Math.max(1, String(node.name || "").length);
            case "ThisExpr":
                return 4;
            case "BreakStmt":
                return 5;
            case "ContinueStmt":
                return 8;
            case "ReturnStmt":
                return 6;
            case "PrintStmt":
                return 5;
            case "IfStmt":
                return 2;
            case "WhileStmt":
                return 5;
            case "DoWhileStmt":
                return 2;
            case "ForStmt":
                return 3;
            case "ParBlock":
                return 3;
            case "SeqBlock":
                return 3;
            case "Program":
                return 1;
            case "ForkStmt":
                return 4;
            case "JoinStmt":
                return 4;
            case "ChannelDecl":
                return 9;
            case "CChannelExpr":
                return 9;
            case "SendStmt":
                return 4;
            case "ReceiveExpr":
                return 7;
            case "NewExpr":
                return 3;
            case "InputExpr":
                return 5;
            case "MethodCall":
                return Math.max(1, String(node.method_name || "").length);
            case "FuncCallExpr":
                return Math.max(1, String(node.name || "").length);
            case "PropertyAccess":
            case "PropertyAssign":
                return Math.max(1, String(node.property_name || "").length);
            case "VarDecl":
            case "AttributeDecl":
            case "Parameter":
                return Math.max(1, String(node.name || "").length);
            case "FuncDecl":
            case "MethodDecl":
                return 4;
            case "ClassDecl":
                return 5;
            default:
                break;
        }
        const named = [
            node.name,
            node.property_name,
            node.method_name,
            node.task_name,
            node.class_name,
        ].find(function (value) {
            return typeof value === "string" && value.length > 0;
        });
        return named ? Math.max(1, named.length) : 1;
    }

    function comparePositions(lineA, columnA, lineB, columnB) {
        if (lineA !== lineB) return lineA < lineB ? -1 : 1;
        if (columnA === columnB) return 0;
        return columnA < columnB ? -1 : 1;
    }

    function spanOf(node) {
        const line = asInt(node.line, 1);
        const column = asInt(node.column, 1);
        let startLine = line;
        let startColumn = column;
        let endLine = line;
        let endColumn = column + ownLength(node);

        childEntries(node).forEach(function (entry) {
            const child = spanOf(entry.node);
            if (
                comparePositions(
                    child.line,
                    child.column,
                    startLine,
                    startColumn
                ) < 0
            ) {
                startLine = child.line;
                startColumn = child.column;
            }
            if (
                comparePositions(
                    child.endLine,
                    child.endColumn,
                    endLine,
                    endColumn
                ) > 0
            ) {
                endLine = child.endLine;
                endColumn = child.endColumn;
            }
        });

        return {
            line: startLine,
            column: startColumn,
            endLine: endLine,
            endColumn: endColumn,
        };
    }

    function directChild(node, className) {
        for (let index = 0; index < node.children.length; index += 1) {
            const child = node.children[index];
            if (child.classList && child.classList.contains(className)) {
                return child;
            }
        }
        return null;
    }

    function rowOf(node) {
        return directChild(node, "ast-node-row");
    }

    function setExpanded(node, expanded) {
        node.classList.toggle("is-collapsed", !expanded);
        const row = rowOf(node);
        if (!row) return;
        row.setAttribute("aria-expanded", String(expanded));
        const toggle = row.querySelector(".ast-toggle");
        if (toggle && toggle.tagName === "BUTTON") {
            toggle.textContent = expanded ? TOGGLE_EXPANDED : TOGGLE_COLLAPSED;
            toggle.setAttribute(
                "aria-label",
                (expanded ? "Recolher " : "Expandir ") +
                    (node.dataset.nodeType || "nó")
            );
        }
    }

    function isExpanded(node) {
        return !node.classList.contains("is-collapsed");
    }

    function visibleGraphChildren(item, expandedSet) {
        const list = directChild(item, "ast-children");
        if (!list || !expandedSet.has(item)) return [];
        return Array.prototype.filter.call(list.children, function (child) {
            return child.classList && child.classList.contains("ast-node");
        });
    }

    function compactLabel(node) {
        const names = [
            node.name,
            node.method_name,
            node.property_name,
            node.task_name,
            node.class_name,
        ];
        for (let index = 0; index < names.length; index += 1) {
            if (typeof names[index] === "string" && names[index]) {
                return names[index];
            }
        }
        return node.tipo || "nó";
    }

    function setGraphExpanded(item, state, expanded, refresh) {
        if (expanded) {
            state.graphExpanded.add(item);
        } else {
            state.graphExpanded.delete(item);
        }
        refresh();
    }

    function toggleGraphExpansion(item, state, refresh) {
        setGraphExpanded(
            item,
            state,
            !state.graphExpanded.has(item),
            refresh
        );
    }

    function createGraphCard(item, state, refresh) {
        const node = item.__astNode;
        const row = rowOf(item);
        const children = directChild(item, "ast-children");
        const hasChildren = Boolean(children && children.children.length);
        const compact = state.graphVariant === "compact";
        const expanded = state.graphExpanded.has(item);
        const card = element("div", "ast-graph-node");
        if (compact) card.classList.add("is-compact");
        card.setAttribute("role", "treeitem");
        card.setAttribute(
            "aria-level",
            row ? row.getAttribute("aria-level") : "1"
        );
        card.dataset.nodeType = item.dataset.nodeType;
        card.dataset.category = item.dataset.category;
        card.tabIndex = 0;
        card.setAttribute(
            "aria-selected",
            item.classList.contains("is-selected") ? "true" : "false"
        );
        if (hasChildren) {
            card.setAttribute("aria-expanded", String(expanded));
        }
        if (item.classList.contains("is-selected")) card.classList.add("is-selected");
        if (item.classList.contains("is-match")) card.classList.add("is-match");
        if (item.classList.contains("is-dimmed")) card.classList.add("is-dimmed");
        card.title = item.dataset.nodeType + " · " + item.dataset.searchText;

        if (hasChildren) {
            const toggle = element(
                "button",
                "ast-graph-toggle",
                compact
                    ? (expanded ? "\u2212" : "+")
                    : (expanded ? TOGGLE_EXPANDED : TOGGLE_COLLAPSED)
            );
            toggle.type = "button";
            toggle.tabIndex = -1;
            toggle.setAttribute(
                "aria-label",
                (expanded ? "Recolher " : "Expandir ") +
                    item.dataset.nodeType
            );
            toggle.addEventListener("click", function (event) {
                event.stopPropagation();
                toggleGraphExpansion(item, state, refresh);
            });
            card.appendChild(toggle);
        } else {
            const spacer = element(
                "span",
                "ast-graph-toggle ast-graph-toggle-empty"
            );
            spacer.setAttribute("aria-hidden", "true");
            card.appendChild(spacer);
        }

        if (compact) {
            const label = element(
                "span",
                "ast-compact-label",
                compactLabel(node)
            );
            label.title = node.name
                ? "name: " + node.name
                : item.dataset.nodeType;
            card.appendChild(label);
        } else {
            card.appendChild(
                element("span", "ast-badge", item.dataset.nodeType)
            );

            const summary = element("span", "ast-summary");
            summaryEntries(node).slice(0, 2).forEach(function (entry) {
                const field = element("span", "ast-field");
                field.title = entry[0] + ": " + entry[1];
                field.appendChild(element("b", null, entry[0]));
                field.appendChild(document.createTextNode(": " + entry[1]));
                summary.appendChild(field);
            });
            card.appendChild(summary);

            if (
                item.dataset.category === "expressao" &&
                node.tipo_inferido !== null
            ) {
                const inferred = node.tipo_inferido === undefined
                    ? "unknown"
                    : node.tipo_inferido;
                card.appendChild(
                    element("span", "ast-type", "tipo: " + inferred)
                );
            }

            card.appendChild(
                element(
                    "span",
                    "ast-location",
                    "L" + item.dataset.line + ":C" + item.dataset.column
                )
            );
        }

        card.addEventListener("click", function (event) {
            if (event.target.closest("button.ast-graph-toggle")) return;
            if (compact) {
                state.select(item);
                if (state.showGraphDetails) {
                    state.showGraphDetails(item, card);
                }
                return;
            }
            if (hasChildren) {
                toggleGraphExpansion(item, state, refresh);
            }
            state.select(item);
        });

        card.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (compact) {
                    state.select(item);
                    if (state.showGraphDetails) {
                        state.showGraphDetails(item, card);
                    }
                    return;
                }
                if (hasChildren) {
                    toggleGraphExpansion(item, state, refresh);
                }
                state.select(item);
                return;
            }
            if (event.key === "ArrowRight" && hasChildren && !expanded) {
                event.preventDefault();
                setGraphExpanded(item, state, true, refresh);
                return;
            }
            if (event.key === "ArrowLeft" && hasChildren && expanded) {
                event.preventDefault();
                setGraphExpanded(item, state, false, refresh);
            }
        });

        return card;
    }

    function layoutGraph(item, depth, metrics, expandedSet) {
        const x = metrics.pad + depth * (metrics.nodeWidth + metrics.hGap);
        const children = visibleGraphChildren(item, expandedSet);
        if (!children.length) {
            return {
                width: x + metrics.nodeWidth + metrics.pad,
                height: metrics.nodeHeight,
                root: { x: x, y: 0 },
                nodes: [{ item: item, x: x, y: 0 }],
                edges: [],
            };
        }

        const childLayouts = children.map(function (child) {
            return {
                item: child,
                layout: layoutGraph(child, depth + 1, metrics, expandedSet),
            };
        });
        const childrenHeight = childLayouts.reduce(function (total, entry) {
            return total + entry.layout.height;
        }, 0) + metrics.vGap * (childLayouts.length - 1);
        const height = Math.max(metrics.nodeHeight, childrenHeight);
        const centerY = height / 2;
        const y = centerY - metrics.nodeHeight / 2;
        let cursor = (height - childrenHeight) / 2;
        let width = x + metrics.nodeWidth + metrics.pad;
        const nodes = [{ item: item, x: x, y: y }];
        const edges = [];

        childLayouts.forEach(function (entry) {
            const childLayout = entry.layout;
            childLayout.nodes.forEach(function (childNode) {
                childNode.y += cursor;
            });
            childLayout.edges.forEach(function (edge) {
                edge.y1 += cursor;
                edge.y2 += cursor;
            });
            width = Math.max(width, childLayout.width);
            const childRowElement = rowOf(entry.item);
            const childRow = childRowElement
                ? childRowElement.querySelector(".ast-edge")
                : null;
            edges.push({
                x1: x + metrics.nodeWidth,
                y1: centerY,
                x2: childLayout.root.x,
                y2: childLayout.root.y + cursor + metrics.nodeHeight / 2,
                label: childRow ? childRow.textContent : "",
            });
            edges.push.apply(edges, childLayout.edges);
            nodes.push.apply(nodes, childLayout.nodes);
            cursor += childLayout.height + metrics.vGap;
        });

        return {
            width: width,
            height: height,
            root: { x: x, y: y },
            nodes: nodes,
            edges: edges,
        };
    }

    function expandAncestors(node) {
        let parent = node.parentElement;
        while (parent) {
            if (parent.classList && parent.classList.contains("ast-node")) {
                setExpanded(parent, true);
            }
            if (
                parent.classList &&
                parent.classList.contains("ast-tree")
            ) {
                break;
            }
            parent = parent.parentElement;
        }
    }

    function expandGraphAncestors(node, expandedSet) {
        let parent = node.parentElement;
        while (parent) {
            if (parent.classList && parent.classList.contains("ast-node")) {
                expandedSet.add(parent);
            }
            if (
                parent.classList &&
                parent.classList.contains("ast-tree")
            ) {
                break;
            }
            parent = parent.parentElement;
        }
    }

    function createNode(node, fieldLabel, level, state) {
        const category = categoryOf(node);
        const children = childEntries(node);
        const hasChildren = children.length > 0;
        const expanded = level < state.defaultDepth;

        const item = element("li", "ast-node");
        item.setAttribute("role", "none");
        item.dataset.nodeType = node.tipo || "Desconhecido";
        item.dataset.category = category;
        item.dataset.line = String(asInt(node.line, 1));
        item.dataset.column = String(asInt(node.column, 1));
        item.dataset.searchText = searchableText(node);
        item.__astNode = node;

        state.counts[category] = (state.counts[category] || 0) + 1;
        state.total += 1;
        state.nodeElements.push(item);

        const row = element("div", "ast-node-row");
        row.setAttribute("role", "treeitem");
        row.setAttribute("aria-level", String(level + 1));
        row.setAttribute("aria-selected", "false");
        row.tabIndex = level === 0 ? 0 : -1;
        row.addEventListener("focus", function () {
            if (state.focusedRow && state.focusedRow !== row) {
                state.focusedRow.tabIndex = -1;
            }
            state.focusedRow = row;
            row.tabIndex = 0;
        });

        if (hasChildren) {
            const toggle = element(
                "button",
                "ast-toggle",
                expanded ? TOGGLE_EXPANDED : TOGGLE_COLLAPSED
            );
            toggle.type = "button";
            toggle.tabIndex = -1;
            toggle.setAttribute(
                "aria-label",
                (expanded ? "Recolher " : "Expandir ") + item.dataset.nodeType
            );
            toggle.addEventListener("click", function (event) {
                event.stopPropagation();
                setExpanded(item, !isExpanded(item));
            });
            row.appendChild(toggle);
        } else {
            const spacer = element("span", "ast-toggle ast-toggle-empty");
            spacer.setAttribute("aria-hidden", "true");
            row.appendChild(spacer);
        }

        if (fieldLabel) {
            row.appendChild(element("span", "ast-edge", fieldLabel));
        }

        row.appendChild(
            element("span", "ast-badge", item.dataset.nodeType)
        );

        const summary = element("span", "ast-summary");
        summaryEntries(node).forEach(function (entry) {
            const field = element("span", "ast-field");
            field.title = entry[0] + ": " + entry[1];
            field.appendChild(element("b", null, entry[0]));
            field.appendChild(document.createTextNode(": " + entry[1]));
            summary.appendChild(field);
        });
        row.appendChild(summary);

        if (category === "expressao" && node.tipo_inferido !== null) {
            const inferred = node.tipo_inferido === undefined
                ? "unknown"
                : node.tipo_inferido;
            row.appendChild(
                element("span", "ast-type", "tipo: " + inferred)
            );
        }

        row.appendChild(
            element(
                "span",
                "ast-location",
                "L" + item.dataset.line + ":C" + item.dataset.column
            )
        );

        row.addEventListener("click", function (event) {
            if (event.target.closest("button.ast-toggle")) return;
            if (hasChildren) setExpanded(item, !isExpanded(item));
            state.select(item);
        });

        row.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (hasChildren) setExpanded(item, !isExpanded(item));
                state.select(item);
                return;
            }
            if (event.key === "ArrowRight" && hasChildren) {
                event.preventDefault();
                setExpanded(item, true);
                return;
            }
            if (event.key === "ArrowLeft" && hasChildren) {
                event.preventDefault();
                setExpanded(item, false);
                return;
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                state.moveFocus(row, event.key === "ArrowDown" ? 1 : -1);
            }
        });

        item.appendChild(row);

        if (hasChildren) {
            const list = element("ul", "ast-children");
            list.setAttribute("role", "group");
            children.forEach(function (entry) {
                const label = entry.index === null
                    ? entry.field
                    : entry.field + "[" + entry.index + "]";
                list.appendChild(
                    createNode(entry.node, label, level + 1, state)
                );
            });
            item.appendChild(list);
            if (!expanded) item.classList.add("is-collapsed");
            row.setAttribute("aria-expanded", String(expanded));
        }

        return item;
    }

    function createToolbar(state) {
        const toolbar = element("div", "ast-toolbar");

        const searchGroup = element("div", "ast-toolbar-group ast-search-group");
        const search = element("input", "ast-search");
        search.type = "search";
        search.placeholder = "Buscar tipo ou nome";
        search.setAttribute("aria-label", "Buscar nó por tipo ou nome");
        const searchCount = element("span", "ast-search-count");
        searchCount.setAttribute("aria-live", "polite");
        searchGroup.appendChild(search);
        searchGroup.appendChild(searchCount);

        const modeGroup = element("div", "ast-toolbar-group ast-mode-group");
        const treeMode = element("button", "ast-mode is-active", "Árvore");
        treeMode.type = "button";
        treeMode.dataset.astMode = "tree";
        treeMode.setAttribute("aria-pressed", "true");
        const graphMode = element("button", "ast-mode", "Grafo");
        graphMode.type = "button";
        graphMode.dataset.astMode = "graph";
        graphMode.setAttribute("aria-pressed", "false");
        modeGroup.appendChild(treeMode);
        modeGroup.appendChild(graphMode);

        const variantGroup = element(
            "div",
            "ast-toolbar-group ast-graph-variant"
        );
        const detailedVariant = element(
            "button",
            "ast-mode is-active",
            "Detalhado"
        );
        detailedVariant.type = "button";
        detailedVariant.dataset.astVariant = "detailed";
        detailedVariant.setAttribute("aria-pressed", "true");
        const compactVariant = element("button", "ast-mode", "Compacto");
        compactVariant.type = "button";
        compactVariant.dataset.astVariant = "compact";
        compactVariant.setAttribute("aria-pressed", "false");
        variantGroup.appendChild(detailedVariant);
        variantGroup.appendChild(compactVariant);

        const actions = element("div", "ast-toolbar-group");
        const expand = element("button", "ast-action", "Expandir tudo");
        expand.type = "button";
        expand.dataset.astAction = "expand";
        const collapse = element("button", "ast-action", "Recolher tudo");
        collapse.type = "button";
        collapse.dataset.astAction = "collapse";
        const fit = element("button", "ast-action", "Ajustar à largura");
        fit.type = "button";
        fit.dataset.astAction = "fit";
        actions.appendChild(expand);
        actions.appendChild(collapse);
        actions.appendChild(fit);

        const zoomGroup = element("div", "ast-toolbar-group ast-zoom-group");
        const zoomOut = element("button", "ast-action ast-zoom", "\u2212");
        zoomOut.type = "button";
        zoomOut.dataset.astAction = "zoom-out";
        zoomOut.setAttribute("aria-label", "Diminuir zoom");
        const zoomValue = element("span", "ast-zoom-value", "100%");
        const zoomIn = element("button", "ast-action ast-zoom", "+");
        zoomIn.type = "button";
        zoomIn.dataset.astAction = "zoom-in";
        zoomIn.setAttribute("aria-label", "Aumentar zoom");
        zoomGroup.appendChild(zoomOut);
        zoomGroup.appendChild(zoomValue);
        zoomGroup.appendChild(zoomIn);

        const total = element("span", "ast-total", "0 nós");

        toolbar.appendChild(searchGroup);
        toolbar.appendChild(modeGroup);
        toolbar.appendChild(actions);
        toolbar.appendChild(zoomGroup);
        toolbar.appendChild(total);

        return {
            toolbar: toolbar,
            search: search,
            searchCount: searchCount,
            zoomValue: zoomValue,
            total: total,
            expand: expand,
            collapse: collapse,
            fit: fit,
            zoomIn: zoomIn,
            zoomOut: zoomOut,
            treeMode: treeMode,
            graphMode: graphMode,
            variantGroup: variantGroup,
            detailedVariant: detailedVariant,
            compactVariant: compactVariant,
        };
    }

    function createLegend() {
        const legend = element("div", "ast-legend");
        legend.setAttribute("role", "list");
        legend.setAttribute("aria-label", "Legenda de categorias da AST");
        const counts = {};
        Object.keys(CATEGORIES).forEach(function (category) {
            const item = element("span", "ast-legend-item");
            item.setAttribute("role", "listitem");
            item.dataset.category = category;
            const swatch = element("i", "ast-legend-swatch");
            swatch.setAttribute("aria-hidden", "true");
            item.appendChild(swatch);
            item.appendChild(
                document.createTextNode(CATEGORIES[category].label + " ")
            );
            const count = element("b", null, "0");
            item.appendChild(count);
            legend.appendChild(item);
            counts[category] = count;
        });
        return { legend: legend, counts: counts };
    }

    function mount(container, ast, options) {
        if (!container) return null;
        const settings = options || {};
        container.innerHTML = "";

        const counts = {
            declaracao: 0,
            expressao: 0,
            controle: 0,
            paralelo: 0,
        };
        const state = {
            defaultDepth: Number.isFinite(Number(settings.defaultDepth))
                ? Math.max(0, Math.trunc(Number(settings.defaultDepth)))
                : 0,
            onSelect: typeof settings.onSelect === "function"
                ? settings.onSelect
                : null,
            nodeElements: [],
            matches: [],
            matchIndex: -1,
            selected: null,
            focusedRow: null,
            counts: counts,
            total: 0,
            tree: null,
            viewport: null,
            status: null,
            graphCanvas: null,
            graphCards: null,
            graphExpanded: new Set(),
            graphVariant: "detailed",
            detailPopover: null,
        };

        const view = element("div", "ast-view");
        view.dataset.astMode = "tree";
        const toolbarParts = createToolbar(state);
        const legendParts = createLegend();
        const viewport = element("div", "ast-viewport");
        const tree = element("ul", "ast-tree");
        tree.setAttribute("role", "tree");
        tree.setAttribute("aria-label", "Árvore sintática abstrata");
        const graphCanvas = element("div", "ast-graph");
        graphCanvas.hidden = true;
        graphCanvas.setAttribute("role", "tree");
        graphCanvas.setAttribute("aria-label", "Grafo hierárquico da AST");
        const status = element("div", "ast-status");
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.textContent = "Selecione um nó para destacar o código-fonte.";
        const detailPopover = element("div", "ast-graph-popover");
        detailPopover.hidden = true;
        detailPopover.setAttribute("role", "dialog");
        detailPopover.setAttribute("aria-label", "Detalhes do nó");

        state.tree = tree;
        state.viewport = viewport;
        state.status = status;
        state.graphCanvas = graphCanvas;
        state.detailPopover = detailPopover;

        view.appendChild(toolbarParts.toolbar);
        view.appendChild(legendParts.legend);
        viewport.appendChild(tree);
        viewport.appendChild(graphCanvas);
        const stage = element("div", "ast-stage");
        stage.appendChild(viewport);
        stage.appendChild(toolbarParts.variantGroup);
        view.appendChild(stage);
        view.appendChild(status);
        view.appendChild(detailPopover);
        container.appendChild(view);

        const instance = {
            root: container,
            search: function (query) {
                applySearch(String(query || ""));
            },
            expandAll: function () {
                setAllExpanded(true);
            },
            collapseAll: function () {
                setAllExpanded(false);
            },
            fitToWidth: fitToWidth,
            zoomIn: function () {
                applyZoom(zoom + 0.1);
            },
            zoomOut: function () {
                applyZoom(zoom - 0.1);
            },
            setMode: function (nextMode) {
                setMode(nextMode);
            },
            setGraphVariant: function (nextVariant) {
                setGraphVariant(nextVariant);
            },
            renderGraph: function () {
                renderGraph();
            },
            spanOf: spanOf,
            categoryOf: categoryOf,
        };
        container.__astView = instance;

        state.syncGraphState = function () {
            if (!state.graphCards) return;
            state.graphCards.forEach(function (card, item) {
                card.classList.toggle(
                    "is-selected",
                    item.classList.contains("is-selected")
                );
                card.classList.toggle(
                    "is-match",
                    item.classList.contains("is-match")
                );
                card.classList.toggle(
                    "is-dimmed",
                    item.classList.contains("is-dimmed")
                );
                card.setAttribute(
                    "aria-selected",
                    item.classList.contains("is-selected") ? "true" : "false"
                );
            });
        };

        state.showGraphDetails = function (item, card) {
            showGraphDetails(item, card);
        };

        state.select = function (item) {
            if (state.selected) {
                state.selected.classList.remove("is-selected");
                const previous = rowOf(state.selected);
                if (previous) previous.setAttribute("aria-selected", "false");
            }
            state.selected = item;
            item.classList.add("is-selected");
            const row = rowOf(item);
            if (row) row.setAttribute("aria-selected", "true");
            state.syncGraphState();
            const node = item.__astNode;
            if (node) {
                const inferred = node.tipo_inferido !== null &&
                    node.tipo_inferido !== undefined
                    ? " · tipo " + node.tipo_inferido
                    : "";
                status.textContent =
                    item.dataset.nodeType +
                    " · linha " + item.dataset.line +
                    ", coluna " + item.dataset.column +
                    inferred;
                if (state.onSelect) state.onSelect(node);
            }
        };

        state.moveFocus = function (row, direction) {
            const rows = Array.prototype.filter.call(
                tree.querySelectorAll(".ast-node-row"),
                function (candidate) {
                    return candidate.offsetParent !== null;
                }
            );
            const index = rows.indexOf(row);
            if (index === -1) return;
            const target = rows[index + direction];
            if (target) {
                target.focus();
                target.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
        };

        let zoom = 1;
        let mode = "tree";

        function hideGraphDetails() {
            detailPopover.hidden = true;
            detailPopover.innerHTML = "";
        }

        function showGraphDetails(item, card) {
            const node = item.__astNode;
            if (!node || !card) return;
            detailPopover.innerHTML = "";

            const head = element("div", "ast-graph-popover-head");
            head.dataset.category = item.dataset.category;
            head.appendChild(
                element("span", "ast-badge", item.dataset.nodeType)
            );
            const close = element(
                "button",
                "ast-graph-popover-close",
                "\u00d7"
            );
            close.type = "button";
            close.setAttribute("aria-label", "Fechar detalhes");
            close.addEventListener("click", hideGraphDetails);
            head.appendChild(close);
            detailPopover.appendChild(head);

            const list = element("dl", "ast-graph-popover-list");
            function addDetail(term, value) {
                const row = element("div", "ast-graph-popover-row");
                row.appendChild(element("dt", null, term));
                row.appendChild(element("dd", null, value));
                list.appendChild(row);
            }

            const category = CATEGORIES[item.dataset.category];
            addDetail("Categoria", category ? category.label : item.dataset.category);
            addDetail(
                "Posição",
                "L" + item.dataset.line + ":C" + item.dataset.column
            );
            if (
                node.tipo_inferido !== null &&
                node.tipo_inferido !== undefined
            ) {
                addDetail("Tipo inferido", node.tipo_inferido);
            }
            const children = childEntries(node).length;
            if (children) addDetail("Filhos", children);
            detailEntries(node).forEach(function (entry) {
                addDetail(entry[0], entry[1]);
            });
            detailPopover.appendChild(list);
            detailPopover.hidden = false;
            detailPopover.style.left = "12px";
            detailPopover.style.top = "12px";

            const cardRect = card.getBoundingClientRect();
            const width = detailPopover.offsetWidth;
            const height = detailPopover.offsetHeight;
            let left = cardRect.right + 12;
            if (left + width > window.innerWidth - 12) {
                left = cardRect.left - width - 12;
            }
            left = Math.max(
                12,
                Math.min(left, window.innerWidth - width - 12)
            );
            const top = Math.max(
                12,
                Math.min(cardRect.top, window.innerHeight - height - 12)
            );
            detailPopover.style.left = left + "px";
            detailPopover.style.top = top + "px";
        }

        function applyZoom(value, anchor) {
            const nextZoom = Math.min(1.6, Math.max(0.6, value));
            if (nextZoom === zoom) return;
            const viewportRect = viewport.getBoundingClientRect();
            const viewX = anchor ? anchor.x - viewportRect.left : 0;
            const viewY = anchor ? anchor.y - viewportRect.top : 0;
            const contentX = anchor ? (viewport.scrollLeft + viewX) / zoom : 0;
            const contentY = anchor ? (viewport.scrollTop + viewY) / zoom : 0;
            zoom = nextZoom;
            tree.style.zoom = String(zoom);
            graphCanvas.style.zoom = String(zoom);
            toolbarParts.zoomValue.textContent = Math.round(zoom * 100) + "%";
            if (anchor) {
                viewport.scrollLeft = contentX * zoom - viewX;
                viewport.scrollTop = contentY * zoom - viewY;
            }
        }

        function setMode(nextMode) {
            hideGraphDetails();
            mode = nextMode === "graph" ? "graph" : "tree";
            view.dataset.astMode = mode;
            tree.hidden = mode !== "tree";
            graphCanvas.hidden = mode !== "graph";
            toolbarParts.treeMode.classList.toggle("is-active", mode === "tree");
            toolbarParts.graphMode.classList.toggle("is-active", mode === "graph");
            toolbarParts.treeMode.setAttribute(
                "aria-pressed",
                String(mode === "tree")
            );
            toolbarParts.graphMode.setAttribute(
                "aria-pressed",
                String(mode === "graph")
            );
            viewport.scrollLeft = 0;
            viewport.scrollTop = 0;
            if (mode === "graph") renderGraph();
        }

        function setGraphVariant(nextVariant) {
            state.graphVariant = nextVariant === "compact"
                ? "compact"
                : "detailed";
            const detailed = state.graphVariant === "detailed";
            toolbarParts.detailedVariant.classList.toggle("is-active", detailed);
            toolbarParts.compactVariant.classList.toggle("is-active", !detailed);
            toolbarParts.detailedVariant.setAttribute(
                "aria-pressed",
                String(detailed)
            );
            toolbarParts.compactVariant.setAttribute(
                "aria-pressed",
                String(!detailed)
            );
            hideGraphDetails();
            if (mode === "graph") renderGraph();
        }

        function graphPath(edge, offsetX, offsetY) {
            const x1 = edge.x1 + offsetX;
            const y1 = edge.y1 + offsetY;
            const x2 = edge.x2 + offsetX;
            const y2 = edge.y2 + offsetY;
            const midX = (x1 + x2) / 2;
            return (
                "M " + x1 + " " + y1 +
                " C " + midX + " " + y1 +
                ", " + midX + " " + y2 +
                ", " + x2 + " " + y2
            );
        }

        function renderGraph() {
            if (!tree.firstElementChild || !graphCanvas) return;
            hideGraphDetails();
            const metrics = GRAPH_VARIANTS[state.graphVariant] ||
                GRAPH_VARIANTS.detailed;
            const layout = layoutGraph(
                tree.firstElementChild,
                0,
                metrics,
                state.graphExpanded
            );
            const width = Math.max(layout.width, viewport.clientWidth || 0);
            const offsetX = 0;
            const offsetY = metrics.pad;
            const height = Math.max(
                layout.height + metrics.pad * 2,
                viewport.clientHeight || 0
            );
            graphCanvas.innerHTML = "";
            graphCanvas.style.width = width + "px";
            graphCanvas.style.height = height + "px";

            const svg = document.createElementNS(
                "http://www.w3.org/2000/svg",
                "svg"
            );
            svg.setAttribute("class", "ast-graph-edges");
            svg.setAttribute("width", String(width));
            svg.setAttribute("height", String(height));
            svg.setAttribute("aria-hidden", "true");
            layout.edges.forEach(function (edge) {
                const path = document.createElementNS(
                    "http://www.w3.org/2000/svg",
                    "path"
                );
                path.setAttribute("class", "ast-graph-edge");
                path.setAttribute("d", graphPath(edge, offsetX, offsetY));
                svg.appendChild(path);
            });
            graphCanvas.appendChild(svg);

            layout.edges.forEach(function (edge) {
                if (!edge.label) return;
                const label = element(
                    "span",
                    "ast-graph-edge-label",
                    edge.label
                );
                label.style.left =
                    offsetX + (edge.x1 + edge.x2) / 2 + "px";
                label.style.top =
                    offsetY + (edge.y1 + edge.y2) / 2 + "px";
                graphCanvas.appendChild(label);
            });

            const cards = new Map();
            layout.nodes.forEach(function (position) {
                const card = createGraphCard(
                    position.item,
                    state,
                    renderGraph
                );
                card.style.left = offsetX + position.x + "px";
                card.style.top = offsetY + position.y + "px";
                card.style.width = metrics.nodeWidth + "px";
                card.style.height = metrics.nodeHeight + "px";
                graphCanvas.appendChild(card);
                cards.set(position.item, card);
            });
            state.graphCards = cards;
            state.syncGraphState();
        }

        function fitToWidth() {
            applyZoom(1);
            viewport.scrollLeft = 0;
            viewport.scrollTop = 0;
            const available = viewport.clientWidth - 4;
            const contentElement = mode === "graph" ? graphCanvas : tree;
            const content =
                contentElement.scrollWidth ||
                contentElement.getBoundingClientRect().width;
            if (available > 0 && content > available) {
                applyZoom(Math.max(0.6, available / content));
            }
        }

        function setAllExpanded(expanded) {
            if (mode === "graph") {
                if (expanded) {
                    state.nodeElements.forEach(function (item) {
                        if (directChild(item, "ast-children")) {
                            state.graphExpanded.add(item);
                        }
                    });
                } else {
                    state.graphExpanded.clear();
                }
                renderGraph();
                return;
            }
            state.nodeElements.forEach(function (item) {
                const list = directChild(item, "ast-children");
                if (!list) return;
                if (expanded) {
                    setExpanded(item, true);
                } else {
                    setExpanded(item, item === tree.firstElementChild);
                }
            });
        }

        function applySearch(query) {
            const text = String(query || "").trim().toLowerCase();
            state.matches = [];
            state.matchIndex = -1;
            state.nodeElements.forEach(function (item) {
                item.classList.remove("is-match", "is-dimmed");
            });
            toolbarParts.searchCount.textContent = "";
            if (!text) {
                if (mode === "graph") renderGraph();
                return;
            }
            state.nodeElements.forEach(function (item) {
                if ((item.dataset.searchText || "").includes(text)) {
                    item.classList.add("is-match");
                    state.matches.push(item);
                    if (mode === "graph") {
                        expandGraphAncestors(item, state.graphExpanded);
                    } else {
                        expandAncestors(item);
                    }
                } else {
                    item.classList.add("is-dimmed");
                }
            });
            toolbarParts.searchCount.textContent =
                state.matches.length + " nó(s)";
            if (mode === "graph") renderGraph();
        }

        function cycleMatch(direction) {
            if (!state.matches.length) return;
            state.matchIndex = (
                state.matchIndex + direction + state.matches.length
            ) % state.matches.length;
            const item = state.matches[state.matchIndex];
            if (mode === "graph") {
                expandGraphAncestors(item, state.graphExpanded);
                renderGraph();
                const card = state.graphCards && state.graphCards.get(item);
                if (card) {
                    card.focus({ preventScroll: true });
                    card.scrollIntoView({ block: "nearest", inline: "nearest" });
                }
            } else {
                item.scrollIntoView({ block: "nearest", inline: "nearest" });
                const row = rowOf(item);
                if (row) row.focus({ preventScroll: true });
            }
            state.select(item);
        }

        toolbarParts.search.addEventListener("input", function () {
            applySearch(toolbarParts.search.value);
        });
        toolbarParts.search.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                cycleMatch(event.shiftKey ? -1 : 1);
            } else if (event.key === "Escape") {
                event.preventDefault();
                toolbarParts.search.value = "";
                applySearch("");
                toolbarParts.search.blur();
            }
        });

        toolbarParts.treeMode.addEventListener("click", function () {
            setMode("tree");
        });
        toolbarParts.graphMode.addEventListener("click", function () {
            setMode("graph");
        });
        toolbarParts.detailedVariant.addEventListener("click", function () {
            setGraphVariant("detailed");
        });
        toolbarParts.compactVariant.addEventListener("click", function () {
            setGraphVariant("compact");
        });
        toolbarParts.expand.addEventListener("click", function () {
            setAllExpanded(true);
        });
        toolbarParts.collapse.addEventListener("click", function () {
            setAllExpanded(false);
        });
        toolbarParts.fit.addEventListener("click", fitToWidth);
        toolbarParts.zoomIn.addEventListener("click", function () {
            applyZoom(zoom + 0.1);
        });
        toolbarParts.zoomOut.addEventListener("click", function () {
            applyZoom(zoom - 0.1);
        });

        viewport.addEventListener("wheel", function (event) {
            if (!event.deltaY) return;
            event.preventDefault();
            hideGraphDetails();
            const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
            applyZoom(zoom * factor, {
                x: event.clientX,
                y: event.clientY,
            });
        }, { passive: false });
        viewport.addEventListener("scroll", hideGraphDetails, {
            passive: true,
        });
        view.addEventListener("pointerdown", function (event) {
            if (detailPopover.hidden) return;
            if (
                event.target.closest(
                    ".ast-graph-popover, .ast-graph-node"
                )
            ) {
                return;
            }
            hideGraphDetails();
        });

        let pan = null;
        viewport.addEventListener("pointerdown", function (event) {
            if (event.button !== 0) return;
            hideGraphDetails();
            if (
                event.target.closest &&
                event.target.closest(
                    ".ast-node-row, .ast-graph-node, button, input, label"
                )
            ) {
                return;
            }
            pan = {
                id: event.pointerId,
                x: event.clientX,
                y: event.clientY,
                left: viewport.scrollLeft,
                top: viewport.scrollTop,
            };
            viewport.classList.add("is-panning");
            if (viewport.setPointerCapture) {
                viewport.setPointerCapture(event.pointerId);
            }
        });
        viewport.addEventListener("pointermove", function (event) {
            if (!pan || event.pointerId !== pan.id) return;
            viewport.scrollLeft = pan.left - (event.clientX - pan.x);
            viewport.scrollTop = pan.top - (event.clientY - pan.y);
        });
        function endPan(event) {
            if (!pan || (event && event.pointerId !== pan.id)) return;
            pan = null;
            viewport.classList.remove("is-panning");
            if (
                event &&
                viewport.releasePointerCapture &&
                viewport.hasPointerCapture &&
                viewport.hasPointerCapture(event.pointerId)
            ) {
                viewport.releasePointerCapture(event.pointerId);
            }
        }
        viewport.addEventListener("pointerup", endPan);
        viewport.addEventListener("pointercancel", endPan);

        if (!isNode(ast)) {
            const empty = element("li", "ast-empty", "Nenhuma AST disponível.");
            empty.setAttribute("role", "treeitem");
            tree.appendChild(empty);
            return instance;
        }

        const root = createNode(ast, null, 0, state);
        tree.appendChild(root);

        Object.keys(legendParts.counts).forEach(function (category) {
            legendParts.counts[category].textContent = String(
                counts[category] || 0
            );
        });
        toolbarParts.total.textContent = state.total + " nós";

        return instance;
    }

    global.MiniParAstView = {
        mount: mount,
        spanOf: spanOf,
        categoryOf: categoryOf,
        categories: CATEGORIES,
    };
})(window);
