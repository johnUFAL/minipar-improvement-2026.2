document.addEventListener("DOMContentLoaded", () => {
    const HISTORY_KEY = "minipar-compiler-history";
    const LAST_KEY = "minipar-compiler-last";
    let history = loadHistory();

    const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    const format = value => Number(value || 0).toFixed(3);

    function loadHistory() {
        try {
            const stored = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
            return Array.isArray(stored) ? stored : [];
        } catch (error) {
            return [];
        }
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function formatDate(value) {
        const date = new Date(Number(value));
        return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
    }

    function runId(item, index) {
        const identifier = item.id ?? item.created_at;
        return identifier === undefined || identifier === null || identifier === ""
            ? `index-${index}`
            : String(identifier);
    }

    function renderSummary() {
        const successes = history.filter(item => item.success).length;
        setText("compiler-total", history.length);
        setText("compiler-success", successes);
        setText("compiler-errors", history.length - successes);
        setText("compiler-last-time", history.length ? `${format(history[0].time)} s` : "—");
        setText("compiler-count", history.length);

        const last = history[0];
        setText("panel-compiler-total", history.length);
        setText("panel-compiler-time", last ? `${format(last.time)} s` : "—");
        setText("panel-compiler-status", last ? (last.success ? "execução concluída" : "terminou com diagnóstico") : "aguardando o editor");
        setText("panel-compiler-file", last ? last.file : "Nenhuma execução ainda");
        setText("panel-compiler-detail", last
            ? `${format(last.time)} s · ${last.optimization || "O0"} · ${formatDate(last.created_at)}`
            : "Execute um programa no editor para começar");
        setText("panel-compiler-summary", last ? (last.success ? "OK" : "erro") : "—");
    }

    function renderList() {
        const list = document.getElementById("compiler-history-list");
        if (!list) return;
        list.innerHTML = history.map((item, index) => `
            <a class="history-row" href="/resultados/${encodeURIComponent(runId(item, index))}">
                <b>${escape(item.file || "programa")}</b>
                <span>${item.success ? '<em class="green-text">Sucesso</em>' : '<em class="red-text">Com erro</em>'}</span>
                <small>${format(item.time)} s · ${formatDate(item.created_at)}</small>
            </a>`).join("");
    }

    function render() {
        history = loadHistory();
        renderSummary();
        const content = document.getElementById("compiler-content");
        const empty = document.getElementById("compiler-empty");
        if (!content || !empty) return;
        if (history.length) {
            empty.hidden = true;
            content.hidden = false;
            renderList();
        } else {
            empty.hidden = false;
            content.hidden = true;
            const list = document.getElementById("compiler-history-list");
            if (list) list.innerHTML = "";
        }
    }

    document.getElementById("compiler-clear")?.addEventListener("click", () => {
        localStorage.removeItem(HISTORY_KEY);
        localStorage.removeItem(LAST_KEY);
        render();
    });

    window.addEventListener("storage", event => {
        if (event.key === HISTORY_KEY) render();
    });

    if (window.location.hash === "#result-detail") {
        const latest = history[0];
        window.location.replace(latest ? `/resultados/${encodeURIComponent(runId(latest, 0))}` : "/resultados");
        return;
    }

    render();
});
