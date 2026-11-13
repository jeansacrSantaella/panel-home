import {storage} from "../lib/storage.js";

const STORAGE_KEY = "netwatch-dashboard-layout";

// Reordena y expande tarjetas; guarda el orden en el navegador.
export function initLayout(grid, resetButton) {
  const sections = () => [...grid.querySelectorAll("[data-widget]")];

  // Restaura widgets conocidos y deja al final los que añadiste después.
  function restore() {
    let saved;
    try { saved = JSON.parse(storage.get(STORAGE_KEY) || "null"); } catch { saved = null; }
    if (!Array.isArray(saved)) return;
    const all = sections();
    const byId = new Map(all.map(section => [section.dataset.widget, section]));
    const ordered = saved.map(id => byId.get(id)).filter(Boolean);
    all.filter(section => !ordered.includes(section)).forEach(section => ordered.push(section));
    ordered.forEach(section => grid.append(section));
  }

  const save = () => storage.set(STORAGE_KEY, JSON.stringify(sections().map(s => s.dataset.widget)));

  function setButton(section, expanded) {
    const button = section.querySelector(".expand-widget");
    const title = section.querySelector("h2").textContent;
    button.textContent = expanded ? "↙" : "⛶";
    button.title = expanded ? "Restaurar tamaño" : "Expandir a pantalla completa";
    button.setAttribute("aria-label", `${expanded ? "Restaurar" : "Expandir"} sección ${title}`);
    button.setAttribute("aria-pressed", String(expanded));
  }

  function toggleExpanded(section) {
    const current = grid.querySelector(".is-expanded");
    if (current && current !== section) {
      current.classList.remove("is-expanded");
      setButton(current, false);
    }
    const expanded = section.classList.toggle("is-expanded");
    document.body.classList.toggle("widget-expanded", expanded);
    setButton(section, expanded);
  }

  grid.addEventListener("click", e => {
    const button = e.target.closest(".expand-widget");
    if (button) toggleExpanded(button.closest("[data-widget]"));
  });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    const expanded = grid.querySelector(".is-expanded");
    if (!expanded) return;
    toggleExpanded(expanded);
    expanded.querySelector(".expand-widget").focus();
  });

  let dragged = null;
  grid.addEventListener("dragstart", e => {
    const handle = e.target.closest(".drag-handle");
    if (!handle) return;
    dragged = handle.closest("[data-widget]");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragged.dataset.widget);
    dragged.classList.add("dragging");
  });

  grid.addEventListener("dragover", e => {
    if (!dragged) return;
    const target = e.target.closest("[data-widget]");
    if (!target || target === dragged) return;
    e.preventDefault();
    const rect = target.getBoundingClientRect();
    const horizontal = Math.abs(e.clientX - (rect.left + rect.width / 2)) >
      Math.abs(e.clientY - (rect.top + rect.height / 2));
    const after = horizontal
      ? e.clientX > rect.left + rect.width / 2
      : e.clientY > rect.top + rect.height / 2;
    grid.insertBefore(dragged, after ? target.nextElementSibling : target);
  });

  grid.addEventListener("drop", e => {
    if (dragged) e.preventDefault();
  });

  grid.addEventListener("dragend", () => {
    if (!dragged) return;
    dragged.classList.remove("dragging");
    dragged = null;
    save();
  });

  resetButton.addEventListener("click", () => {
    storage.remove(STORAGE_KEY);
    location.reload();
  });

  restore();
}
