document.addEventListener("DOMContentLoaded", () => {
    const STORAGE_KEY = "minipar-theme";

    function applyTheme() {
        const light = localStorage.getItem(STORAGE_KEY) === "light";
        document.body.classList.toggle("light-theme", light);
        const toggle = document.getElementById("theme-toggle");
        if (!toggle) return;
        toggle.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#icon-${light ? "moon" : "sun"}"></use></svg><span class="button-label">${light ? "Escuro" : "Claro"}</span>`;
        toggle.setAttribute("aria-label", light ? "Mudar para modo escuro" : "Mudar para modo claro");
    }

    document.getElementById("theme-toggle")?.addEventListener("click", () => {
        const next = document.body.classList.contains("light-theme") ? "dark" : "light";
        localStorage.setItem(STORAGE_KEY, next);
        applyTheme();
    });

    applyTheme();
});
