import {storage} from "../lib/storage.js";

const STORAGE_KEY = "netwatch-dashboard-theme";

// Si no guardaste una preferencia, sigue el tema del sistema.
export function initTheme(button) {
  const apply = (theme, persist) => {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark";
    button.querySelector(".label").textContent = dark ? "Activar modo claro" : "Activar modo nocturno";
    button.setAttribute("aria-pressed", String(dark));
    if (persist) storage.set(STORAGE_KEY, theme);
  };

  const saved = storage.get(STORAGE_KEY);
  const system = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  apply(saved === "light" || saved === "dark" ? saved : system, false);

  button.addEventListener("click", () => {
    apply(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
  });
}
