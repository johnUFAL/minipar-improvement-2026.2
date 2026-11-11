document.addEventListener("DOMContentLoaded", () => {
    const SETTINGS_KEY = "minipar-settings";
    const OPTIMIZATION_KEY = "minipar-optimization";
    const HARDWARE_KEY = "minipar-hardware";
    const LAST_KEY = "minipar-benchmark-last";
    const HISTORY_KEY = "minipar-benchmark-history";
    const HISTORY_LIMIT = 10;
    const TASK_PAGE_SIZE = 15;
    const TASK_PAGE_WINDOW = 5;
    const MAX_ACTIVITIES = 2000;
    const ACTIVITY_PAIRS = [
        { students: "benchmark-students", activities: "benchmark-activities" },
        { students: "settings-students", activities: "settings-activities" },
    ];
    const DEFAULTS = {
        students: 40,
        activities: 4,
        cores: null,
        fractals: 0,
        repetitions: 3,
        optimization: "O0",
    };
    const LABELS = {
        idle: "Executar benchmark",
        running: "Executando…",
        completed: "Executar novamente",
        failed: "Tentar novamente",
    };

    let settings = loadSettings();
    let hardware = null;
    let running = false;
    let benchmarkHistory = [];
    let selectedHistory = 0;
    let taskData = [];
    let taskPage = 0;

    const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
    const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    const format = value => Number(value || 0).toFixed(3);
    const formatPrecise = value => Number(value || 0).toFixed(4);
    const plural = (value, singular, many) => `${value ?? "—"} ${Number(value) === 1 ? singular : many}`;
    const sleep = milliseconds => new Promise(resolve => window.setTimeout(resolve, milliseconds));

    function loadSettings() {
        try {
            const stored = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
            return { ...DEFAULTS, ...(stored && typeof stored === "object" ? stored : {}) };
        } catch (error) {
            return { ...DEFAULTS };
        }
    }

    function saveSettings(next) {
        settings = { ...settings, ...next };
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
        if (settings.optimization) localStorage.setItem(OPTIMIZATION_KEY, settings.optimization);
    }

    function loadLast() {
        try {
            const stored = JSON.parse(localStorage.getItem(LAST_KEY) || "null");
            return stored && stored.result ? stored : null;
        } catch (error) {
            return null;
        }
    }

    function saveLast(payload) {
        try {
            localStorage.setItem(LAST_KEY, JSON.stringify(payload));
        } catch (error) {
            // Resultado grande ou armazenamento indisponível: a tela ainda mostra a execução atual.
        }
    }

    function loadHistory() {
        try {
            const stored = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
            return Array.isArray(stored) ? stored.filter(entry => entry && entry.result) : [];
        } catch (error) {
            return [];
        }
    }

    function saveHistory(entry) {
        const next = [entry, ...loadHistory().filter(item => item.id !== entry.id)].slice(0, HISTORY_LIMIT);
        try {
            localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
        } catch (error) {
            // Histórico é complementar; a medição atual continua visível.
        }
        return next;
    }

    function formatHistoryDate(value) {
        const date = new Date(Number(value));
        return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function setInput(id, value) {
        const input = document.getElementById(id);
        if (input && value !== undefined && value !== null) input.value = String(value);
    }

    function syncPairedRanges() {
        document.querySelectorAll('input[type="range"][data-sync]').forEach(range => {
            const target = document.getElementById(range.dataset.sync);
            if (!target) return;
            const minimum = Number(range.min || 0);
            const maximum = Number(range.max || 100);
            const value = clamp(Number(target.value) || minimum, minimum, maximum);
            range.value = String(value);
        });
    }

    function setActivityField(id, value) {
        setInput(id, value);
        document.querySelectorAll(`input[type="range"][data-sync="${id}"]`).forEach(range => {
            const minimum = Number(range.min || 1);
            const maximum = Number(range.max || MAX_ACTIVITIES);
            range.value = String(clamp(value, minimum, maximum));
        });
    }

    function adjustActivityPair(sourceId) {
        const pair = ACTIVITY_PAIRS.find(item => sourceId === item.students || sourceId === item.activities);
        if (!pair) return;
        const studentsInput = document.getElementById(pair.students);
        const activitiesInput = document.getElementById(pair.activities);
        if (!studentsInput || !activitiesInput) return;
        let students = clamp(Math.trunc(Number(studentsInput.value) || 1), 1, MAX_ACTIVITIES);
        let activities = clamp(Math.trunc(Number(activitiesInput.value) || 1), 1, MAX_ACTIVITIES);
        if (students * activities > MAX_ACTIVITIES) {
            if (sourceId === pair.students) {
                activities = Math.max(1, Math.floor(MAX_ACTIVITIES / students));
            } else {
                students = Math.max(1, Math.floor(MAX_ACTIVITIES / activities));
            }
        }
        setActivityField(pair.students, students);
        setActivityField(pair.activities, activities);
    }

    function fillForm() {
        setInput("benchmark-students", settings.students);
        setInput("benchmark-activities", settings.activities);
        setInput("benchmark-fractals", String(settings.fractals));
        setInput("benchmark-repetitions", settings.repetitions);
        setInput("settings-students", settings.students);
        setInput("settings-activities", settings.activities);
        setInput("settings-fractals", String(settings.fractals));
        setInput("settings-repetitions", settings.repetitions);
        const optimization = document.getElementById("settings-optimization");
        if (optimization) optimization.value = settings.optimization;
        syncPairedRanges();
        ACTIVITY_PAIRS.forEach(pair => adjustActivityPair(pair.students));
    }

    function readNumber(id, fallback) {
        const input = document.getElementById(id);
        if (!input || input.value === "") return fallback;
        const value = Number(input.value);
        return Number.isFinite(value) ? value : fallback;
    }

    function readBenchmarkForm() {
        return {
            alunos: readNumber("benchmark-students", settings.students),
            atividades: readNumber("benchmark-activities", settings.activities),
            nucleos: readNumber("benchmark-cores", hardware ? hardware.max : settings.cores || 1),
            fractais: readNumber("benchmark-fractals", settings.fractals),
            repeticoes: readNumber("benchmark-repetitions", settings.repetitions),
        };
    }

    function readSettingsForm() {
        const range = document.getElementById("settings-cores");
        return {
            students: readNumber("settings-students", settings.students),
            activities: readNumber("settings-activities", settings.activities),
            cores: range ? Number(range.value) : settings.cores,
            fractals: readNumber("settings-fractals", settings.fractals),
            repetitions: readNumber("settings-repetitions", settings.repetitions),
            optimization: document.getElementById("settings-optimization")?.value || settings.optimization,
        };
    }

    function updateCoreControls() {
        const maximum = hardware ? hardware.max : 256;
        const selected = clamp(Number(settings.cores) || maximum, 1, maximum);
        const select = document.getElementById("benchmark-cores");
        if (select && select.tagName === "SELECT") {
            select.innerHTML = Array.from({ length: maximum }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join("");
            select.value = String(selected);
        } else if (select) {
            select.min = "1";
            select.max = String(maximum);
            select.value = String(selected);
        }
        setText("benchmark-cores-value", String(selected));
        const range = document.getElementById("settings-cores");
        if (range) {
            range.min = "1";
            range.max = String(maximum);
            range.value = String(selected);
        }
        setText("settings-cores-value", String(selected));
    }

    function renderHardware() {
        const tag = document.getElementById("benchmark-hardware");
        if (tag) {
            tag.textContent = hardware
                ? `${hardware.logical} lógicos · ${hardware.available} disponíveis`
                : "Hardware indisponível";
        }
        setText("panel-hardware", hardware ? hardware.available : "—");
        setText("hardware-logical", hardware ? hardware.logical : "—");
        setText("hardware-available", hardware ? hardware.available : "—");
        setText("hardware-max", hardware ? hardware.max : "—");
        setText("hardware-status", hardware ? "Detectado" : "Indisponível");
        const status = document.getElementById("hardware-status");
        if (status) status.className = `tag ${hardware ? "tag-success" : "tag-danger"}`;
    }

    async function loadHardware() {
        try {
            const response = await fetch("/api/hardware");
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Falha ao detectar hardware.");
            hardware = {
                logical: Number(data.logical_cores),
                available: Math.max(1, Number(data.available_cores)),
                max: Math.max(1, Math.min(Number(data.available_cores), Number(data.benchmark_max_cores))),
            };
            localStorage.setItem(HARDWARE_KEY, JSON.stringify(hardware));
        } catch (error) {
            try {
                hardware = JSON.parse(localStorage.getItem(HARDWARE_KEY) || "null");
            } catch (parseError) {
                hardware = null;
            }
            const status = document.getElementById("benchmark-status");
            if (status && !hardware) {
                status.textContent = error instanceof Error ? error.message : "Falha ao detectar hardware.";
            }
        }
        renderHardware();
        updateCoreControls();
    }

    function setState(state, message, progress) {
        const value = clamp(Number(progress) || 0, 0, 100);
        const tag = document.getElementById("benchmark-state");
        if (tag) {
            tag.textContent = message;
            tag.className = `tag ${state === "completed" ? "tag-success" : state === "failed" ? "tag-danger" : ""}`;
        }
        const button = document.getElementById("benchmark-run");
        if (button) {
            button.textContent = LABELS[state] || LABELS.idle;
            button.dataset.state = state;
        }
        const bar = document.getElementById("benchmark-progress");
        if (bar) {
            bar.style.width = `${value}%`;
            bar.setAttribute("aria-valuenow", String(value));
        }
        setText("benchmark-progress-value", `${value}%`);
    }

    function summaryMarkup(result) {
        const parameters = result.parameters || {};
        const fractalLabels = {
            0: "Nenhum",
            1: "Mandelbrot",
            2: "Mandelbrot e Sierpinski",
        };
        const fractals = fractalLabels[parameters.fractais] || "—";
        const warnings = Array.isArray(result.warnings) && result.warnings.length
            ? `<ul>${result.warnings.map(message => `<li>${escape(message)}</li>`).join("")}</ul>`
            : "";
        return `
            <div class="benchmark-summary-item"><span>Atividades</span><strong>${parameters.total_atividades ?? "—"}</strong></div>
            <div class="benchmark-summary-item"><span>Núcleos utilizados</span><strong>${parameters.nucleos_utilizados ?? "—"}</strong></div>
            <div class="benchmark-summary-item"><span>Fractais</span><strong>${fractals}</strong></div>
            <div class="benchmark-summary-item"><span>Repetições</span><strong>${parameters.repeticoes ?? "—"}</strong></div>
            <div class="benchmark-summary-item"><span>Tempo sequencial · mediana</span><strong>${format(result.sequential_seconds)} s</strong></div>
            <div class="benchmark-summary-item"><span>Tempo paralelo · mediana</span><strong>${format(result.parallel_seconds)} s</strong></div>
            <div class="benchmark-summary-item"><span>Speedup</span><strong>${format(result.speedup)}×</strong></div>
            <div class="benchmark-summary-item"><span>Eficiência</span><strong>${format(result.efficiency_percent)}%</strong></div>
            ${warnings}`;
    }

    function coreRows(result) {
        return (result.cores || []).map(core => `
            <tr>
                <td>${core.core}</td>
                <td>${core.task_count}</td>
                <td>${formatPrecise(core.busy_seconds)}</td>
                <td>${format(core.utilization_percent)}%</td>
            </tr>`).join("");
    }

    function coreBars(result) {
        return (result.cores || []).map(core => `
            <div class="core-bar-row">
                <span>Núcleo ${core.core}</span>
                <div class="core-bar"><span style="width:${clamp(Number(core.utilization_percent) || 0, 0, 100)}%"></span></div>
                <strong>${format(core.utilization_percent)}%</strong>
            </div>`).join("");
    }

    function taskRow(task) {
        return `
            <tr>
                <td><code>${escape(task.task)}</code></td>
                <td>${task.core}</td>
                <td>${task.units}</td>
                <td>${format(task.median_seconds)}</td>
            </tr>`;
    }

    function renderTaskPages(totalPages) {
        const pages = document.getElementById("benchmark-tasks-pages");
        if (!pages) return;
        const windowStart = Math.min(taskPage, Math.max(0, totalPages - TASK_PAGE_WINDOW));
        const windowEnd = Math.min(totalPages, windowStart + TASK_PAGE_WINDOW);
        pages.innerHTML = Array.from({ length: windowEnd - windowStart }, (_, offset) => {
            const index = windowStart + offset;
            return `
            <button class="pagination-page${index === taskPage ? " active" : ""}" type="button" data-task-page="${index}" aria-label="Ir para a página ${index + 1}"${index === taskPage ? ' aria-current="page"' : ""}>${index + 1}</button>`;
        }).join("");
        pages.querySelectorAll("[data-task-page]").forEach(button => {
            button.addEventListener("click", () => {
                taskPage = Number(button.dataset.taskPage);
                renderTaskPage();
            });
        });
    }

    function renderTaskPage() {
        const table = document.getElementById("benchmark-tasks-result");
        if (!table) return;
        const totalPages = Math.max(1, Math.ceil(taskData.length / TASK_PAGE_SIZE));
        taskPage = clamp(taskPage, 0, totalPages - 1);
        const start = taskPage * TASK_PAGE_SIZE;
        table.innerHTML = taskData.slice(start, start + TASK_PAGE_SIZE).map(taskRow).join("");
        const pagination = document.getElementById("benchmark-tasks-pagination");
        if (pagination) pagination.hidden = totalPages <= 1;
        const previous = document.getElementById("benchmark-tasks-prev");
        const next = document.getElementById("benchmark-tasks-next");
        if (previous) previous.disabled = taskPage <= 0;
        if (next) next.disabled = taskPage >= totalPages - 1;
        setText("benchmark-tasks-page", `Página ${taskPage + 1} de ${totalPages}`);
        renderTaskPages(totalPages);
    }

    function renderPanelBenchmark(last) {
        if (last && last.result) {
            const parameters = last.result.parameters || {};
            setText("panel-benchmark-speedup", `${format(last.result.speedup)}×`);
            setText("panel-benchmark-meta", `${plural(parameters.total_atividades, "atividade", "atividades")} · ${plural(parameters.nucleos_utilizados, "núcleo", "núcleos")}`);
            setText("panel-benchmark-title-row", `${plural(parameters.total_atividades, "atividade", "atividades")} em ${plural(parameters.nucleos_utilizados, "núcleo", "núcleos")}`);
            setText("panel-benchmark-detail", `${plural(parameters.repeticoes, "repetição", "repetições")} · último resultado local`);
            setText("panel-benchmark-summary", `${format(last.result.speedup)}×`);
        } else {
            setText("panel-benchmark-speedup", "—");
            setText("panel-benchmark-meta", "nenhuma medição");
            setText("panel-benchmark-title-row", "Nenhuma medição ainda");
            setText("panel-benchmark-detail", "Configure e execute o benchmark");
            setText("panel-benchmark-summary", "—");
        }
    }

    function renderBenchmarkHistory(activeIndex = selectedHistory) {
        const card = document.getElementById("benchmark-history");
        const list = document.getElementById("benchmark-history-list");
        if (!card || !list) return;
        if (!benchmarkHistory.length) {
            card.hidden = true;
            list.innerHTML = "";
            return;
        }
        card.hidden = false;
        list.innerHTML = benchmarkHistory.map((entry, index) => {
            const result = entry.result || {};
            const parameters = result.parameters || {};
            return `
                <button class="benchmark-history-row${index === activeIndex ? " selected" : ""}" type="button" data-benchmark-history="${index}">
                    <span>
                        <b>${plural(parameters.total_atividades, "atividade", "atividades")} em ${plural(parameters.nucleos_utilizados, "núcleo", "núcleos")}</b>
                        <small>${formatHistoryDate(entry.completed_at)} · ${plural(parameters.repeticoes, "repetição", "repetições")}</small>
                    </span>
                    <strong>${format(result.speedup)}×</strong>
                </button>`;
        }).join("");
        list.querySelectorAll("[data-benchmark-history]").forEach(button => {
            button.addEventListener("click", () => {
                selectedHistory = Number(button.dataset.benchmarkHistory);
                const entry = benchmarkHistory[selectedHistory];
                if (!entry) return;
                renderResult(entry.result, entry.csv_url);
                setState("completed", "Concluído", 100);
                const status = document.getElementById("benchmark-status");
                if (status) status.textContent = "Resultado carregado do histórico local.";
                renderBenchmarkHistory(selectedHistory);
            });
        });
    }

    function renderResult(result, csvUrl) {
        if (!result) return;
        const parameters = result.parameters || {};

        setText("metric-activities", parameters.total_atividades ?? "—");
        setText("metric-sequential", `${format(result.sequential_seconds)} s`);
        setText("metric-parallel", `${format(result.parallel_seconds)} s`);
        setText("metric-speedup", `${format(result.speedup)}×`);

        const summary = document.getElementById("benchmark-summary");
        if (summary) summary.innerHTML = summaryMarkup(result);
        const coresBars = document.getElementById("benchmark-cores-bars");
        if (coresBars) coresBars.innerHTML = coreBars(result);
        const coresTable = document.getElementById("benchmark-cores-result");
        if (coresTable) coresTable.innerHTML = coreRows(result);
        taskData = Array.isArray(result.tasks) ? result.tasks : [];
        taskPage = 0;
        renderTaskPage();

        const csv = document.getElementById("benchmark-csv");
        if (csv) {
            csv.href = csvUrl || "#";
            csv.hidden = !csvUrl;
        }
        const empty = document.getElementById("benchmark-empty");
        if (empty) empty.hidden = true;
        const results = document.getElementById("benchmark-results");
        if (results) results.hidden = false;

        renderPanelBenchmark({ result, csv_url: csvUrl });
    }

    function renderEmptyBenchmark() {
        const empty = document.getElementById("benchmark-empty");
        if (empty) empty.hidden = false;
        const results = document.getElementById("benchmark-results");
        if (results) results.hidden = true;
        taskData = [];
        taskPage = 0;
        renderTaskPage();
        const csv = document.getElementById("benchmark-csv");
        if (csv) csv.hidden = true;
        setText("metric-activities", "—");
        setText("metric-sequential", "—");
        setText("metric-parallel", "—");
        setText("metric-speedup", "—");
    }

    function showSaved(message) {
        const saved = document.getElementById("settings-saved");
        if (saved) saved.innerHTML = `<span class="live-dot"></span> ${escape(message)}`;
    }

    function goToBenchmark() {
        const payload = readBenchmarkForm();
        saveSettings({
            students: payload.alunos,
            activities: payload.atividades,
            cores: payload.nucleos,
            fractals: payload.fractais,
            repetitions: payload.repeticoes,
        });
        window.location.href = "/benchmark?autorun=1";
    }

    async function runBenchmark() {
        if (running) return;
        const status = document.getElementById("benchmark-status");
        const button = document.getElementById("benchmark-run");
        const results = document.getElementById("benchmark-results");
        const empty = document.getElementById("benchmark-empty");
        const payload = readBenchmarkForm();

        running = true;
        if (button) button.disabled = true;
        if (results) results.hidden = true;
        if (empty) empty.hidden = true;
        if (status) status.textContent = "Enfileirando benchmark…";
        setState("running", "Executando", 0);
        saveSettings({
            students: payload.alunos,
            activities: payload.atividades,
            cores: payload.nucleos,
            fractals: payload.fractais,
            repetitions: payload.repeticoes,
        });

        try {
            const response = await fetch("/api/benchmark", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const created = await response.json();
            if (!response.ok) throw new Error(created.error || "Não foi possível iniciar o benchmark.");

            while (true) {
                await sleep(400);
                const pollResponse = await fetch(created.status_url);
                const job = await pollResponse.json();
                if (!pollResponse.ok) throw new Error(job.error || "Falha ao consultar o benchmark.");
                if (status) status.textContent = `${job.message || "Executando"} · ${job.progress ?? 0}%`;
                setState("running", job.state || "Executando", job.progress);
                if (job.status === "failed") throw new Error(job.error || "O benchmark falhou.");
                if (job.status === "completed") {
                    const completedAt = Date.now();
                    const payloadResult = {
                        id: String(completedAt),
                        result: job.result,
                        csv_url: job.csv_url,
                        completed_at: completedAt,
                    };
                    saveLast(payloadResult);
                    benchmarkHistory = saveHistory(payloadResult);
                    selectedHistory = 0;
                    renderBenchmarkHistory();
                    renderResult(job.result, job.csv_url);
                    setState("completed", "Concluído", 100);
                    if (status) status.textContent = "Benchmark concluído.";
                    return;
                }
            }
        } catch (error) {
            setState("failed", "Falhou", 0);
            if (status) status.textContent = error instanceof Error ? error.message : "Falha ao executar benchmark.";
        } finally {
            running = false;
            if (button) {
                button.disabled = false;
                button.textContent = LABELS[button.dataset.state || "idle"] || LABELS.idle;
            }
        }
    }

    async function loadExamples() {
        const select = document.getElementById("dashboard-example");
        if (!select) return;
        try {
            const response = await fetch("/api/tests");
            const data = await response.json();
            select.innerHTML = `<option value="">Escolha um exemplo</option>${(data.tests || []).map(name => `<option value="${escape(name)}">${escape(name)}</option>`).join("")}`;
        } catch (error) {
            select.innerHTML = '<option value="">Exemplos indisponíveis</option>';
        }
    }

    function bindEvents() {
        document.getElementById("panel-run-benchmark")?.addEventListener("click", goToBenchmark);
        document.getElementById("benchmark-run")?.addEventListener("click", runBenchmark);
        document.getElementById("benchmark-tasks-prev")?.addEventListener("click", () => {
            taskPage = Math.max(0, taskPage - 1);
            renderTaskPage();
        });
        document.getElementById("benchmark-tasks-next")?.addEventListener("click", () => {
            const totalPages = Math.max(1, Math.ceil(taskData.length / TASK_PAGE_SIZE));
            taskPage = Math.min(totalPages - 1, taskPage + 1);
            renderTaskPage();
        });

        document.getElementById("benchmark-history-clear")?.addEventListener("click", () => {
            localStorage.removeItem(HISTORY_KEY);
            localStorage.removeItem(LAST_KEY);
            benchmarkHistory = [];
            selectedHistory = 0;
            renderBenchmarkHistory();
            renderEmptyBenchmark();
            setState("idle", "Aguardando", 0);
            const status = document.getElementById("benchmark-status");
            if (status) status.textContent = "Histórico de benchmark limpo.";
        });

        const range = document.getElementById("settings-cores");
        if (range) {
            const syncLabel = () => setText("settings-cores-value", range.value);
            range.addEventListener("input", syncLabel);
            range.addEventListener("change", syncLabel);
        }

        document.querySelectorAll('input[type="range"][data-output]').forEach(element => {
            const output = document.getElementById(element.dataset.output);
            if (!output) return;
            const syncOutput = () => { output.textContent = element.value; };
            element.addEventListener("input", syncOutput);
            element.addEventListener("change", syncOutput);
        });

        document.querySelectorAll('input[type="range"][data-sync]').forEach(element => {
            const target = document.getElementById(element.dataset.sync);
            if (!target) return;
            const fromRange = () => { target.value = element.value; adjustActivityPair(target.id); };
            const fromNumber = () => {
                const minimum = Number(element.min || 0);
                const maximum = Number(element.max || 100);
                element.value = String(clamp(Number(target.value) || minimum, minimum, maximum));
                adjustActivityPair(target.id);
            };
            element.addEventListener("input", fromRange);
            element.addEventListener("change", fromRange);
            target.addEventListener("input", fromNumber);
            target.addEventListener("change", fromNumber);
        });

        document.querySelectorAll(".settings-section-card input[type='range']").forEach(element => {
            element.addEventListener("change", () => showSaved("Alterações não salvas"));
        });

        document.getElementById("save-settings")?.addEventListener("click", () => {
            saveSettings(readSettingsForm());
            showSaved("Configuração salva");
        });

        document.getElementById("restore-settings")?.addEventListener("click", () => {
            const defaults = { ...DEFAULTS, cores: hardware ? hardware.max : null };
            saveSettings(defaults);
            fillForm();
            updateCoreControls();
            showSaved("Padrão restaurado");
        });

        document.getElementById("settings-optimization")?.addEventListener("change", () => {
            showSaved("Alterações não salvas");
        });

        document.querySelectorAll("#settings-students, #settings-activities, #settings-fractals, #settings-repetitions, #settings-cores").forEach(element => {
            element.addEventListener("change", () => showSaved("Alterações não salvas"));
        });

        document.getElementById("dashboard-analyze")?.addEventListener("click", () => {
            const select = document.getElementById("dashboard-example");
            const value = select ? select.value : "";
            if (!value) {
                const status = document.getElementById("benchmark-status");
                if (status) status.textContent = "Escolha um programa antes de analisar.";
                return;
            }
            window.location.href = `/editor?example=${encodeURIComponent(value)}`;
        });
    }

    async function init() {
        fillForm();
        bindEvents();
        await loadHardware();
        fillForm();
        updateCoreControls();
        await loadExamples();

        const last = loadLast();
        benchmarkHistory = loadHistory();
        if (document.getElementById("benchmark-run")) {
            if (!benchmarkHistory.length && last) {
                const entry = {
                    id: String(last.id || last.completed_at || Date.now()),
                    result: last.result,
                    csv_url: last.csv_url,
                    completed_at: Number(last.completed_at || Date.now()),
                };
                benchmarkHistory = saveHistory(entry);
            }
            if (benchmarkHistory.length) {
                selectedHistory = 0;
                renderBenchmarkHistory();
                renderResult(benchmarkHistory[0].result, benchmarkHistory[0].csv_url);
                setState("completed", "Concluído", 100);
                const status = document.getElementById("benchmark-status");
                if (status) status.textContent = "Último benchmark carregado do armazenamento local.";
            } else {
                setState("idle", "Aguardando", 0);
                renderEmptyBenchmark();
            }

            const params = new URLSearchParams(window.location.search);
            if (params.get("autorun") === "1") {
                window.history.replaceState({}, "", "/benchmark");
                await runBenchmark();
            }
        } else if (document.getElementById("panel-run-benchmark")) {
            renderPanelBenchmark(last);
        }
    }

    init();
});
