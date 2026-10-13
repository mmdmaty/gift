document.querySelectorAll(".poem-title").forEach((button) => {
    button.addEventListener("click", () => {
        const content = document.getElementById(
            button.getAttribute("aria-controls")
        );

        if (!content) {
            return;
        }

        const isOpen = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!isOpen));
        content.hidden = isOpen;
    });
});

const themeToggle = document.getElementById("themeToggle");

function applyThemeIcon() {
    if (!themeToggle) {
        return;
    }
    const isDark = document.documentElement.classList.contains("dark");
    themeToggle.textContent = isDark ? "🌙" : "☀️";
}

if (themeToggle) {
    applyThemeIcon();

    themeToggle.addEventListener("click", () => {
        const isDark = document.documentElement
            .classList
            .toggle("dark");

        localStorage.setItem("theme", isDark ? "dark" : "light");
        applyThemeIcon();
    });
}
