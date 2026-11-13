import {$} from "./dom.js";

// Conecta los controles `${key}-page-size`, `${key}-prev`, `${key}-next` y `${key}-page-info`.
export class Pager {
  constructor(key, onChange) {
    this.key = key;
    this.page = 0;
    this.size = 10;
    $(`${key}-prev`).addEventListener("click", () => this.#move(-1, onChange));
    $(`${key}-next`).addEventListener("click", () => this.#move(1, onChange));
    $(`${key}-page-size`).addEventListener("change", e => {
      this.size = Number(e.target.value);
      this.page = 0;
      onChange();
    });
  }

  reset() {
    this.page = 0;
  }

  // Conserva una página válida cuando cambia el tamaño de la lista.
  slice(items) {
    const pageCount = Math.ceil(items.length / this.size);
    this.page = Math.min(this.page, Math.max(0, pageCount - 1));
    const start = this.page * this.size;
    const end = Math.min(start + this.size, items.length);
    this.#show(items.length ? start + 1 : 0, end, items.length, end >= items.length);
    return items.slice(start, end);
  }

  // Muestra la página que ya calculó el servidor.
  showServerPage({total, pages}) {
    this.page = pages ? Math.min(this.page, pages - 1) : 0;
    const start = total ? this.page * this.size + 1 : 0;
    const end = Math.min((this.page + 1) * this.size, total);
    this.#show(start, end, total, this.page + 1 >= pages);
  }

  #move(delta, onChange) {
    this.page = Math.max(0, this.page + delta);
    onChange();
  }

  #show(start, end, total, isLast) {
    $(`${this.key}-page-info`).textContent = `${start}–${end} de ${total}`;
    $(`${this.key}-prev`).disabled = this.page === 0;
    $(`${this.key}-next`).disabled = isLast;
  }
}
