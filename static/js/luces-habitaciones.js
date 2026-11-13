/* Lista de habitaciones en la pestaña Luces.
   Muestra el estado de cada habitación y permite encender/apagar todas sus luces. */
(function () {
  "use strict";
  const ROOT = document.querySelector("#luces-habitaciones");
  if (!ROOT) return;

  const LISTA = ROOT.querySelector(".habitaciones-lista");
  const SUB = document.querySelector("#luces-habitaciones-sub");
  const SIN_HAB = "Sin habitación";

  const P = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">';
  const ICONOS = {
    sala: P + '<path d="M5 11V8a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v3M3 13a2 2 0 0 1 4 0v2h10v-2a2 2 0 0 1 4 0v5H3ZM6 18v2M18 18v2"/></svg>',
    cocina: P + '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 21V3c-2 1.5-3 4-3 7v3h3"/></svg>',
    cuarto: P + '<path d="M3 18V7M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5M7 11.5h.01"/></svg>',
    bano: P + '<path d="M12 3s6 6.2 6 10.5a6 6 0 0 1-12 0C6 9.200 12 3 12 3Z"/></svg>',
    estudio: P + '<path d="M3 8h18v3H3ZM5 11v9M19 11v9M9 11v4h6v-4"/></svg>',
    otro: P + '<path d="M3 11.5 12 4l9 7.5M5.5 10v10h13V10M10 20v-5h4v5"/></svg>',
  };
  const FOCO = P + '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.600 1-2.100A6 6 0 0 0 12 3Z"/></svg>';

  let visible = false;

  function el(tag, clase, props) {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (props) {
      for (const k in props) {
        if (k === "textContent") e.textContent = props[k];
        else if (k === "disabled") e.disabled = props[k];
        else e.setAttribute(k, props[k]);
      }
    }
    return e;
  }

  async function api(url, body) {
    const opts = { credentials: "same-origin" };
    if (body) {
      opts.method = "POST";
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error();
    return res.json();
  }

  function tipo(nombre) {
    const n = nombre.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    if (/sala|living|comedor/.test(n)) return "sala";
    if (/cocina/.test(n)) return "cocina";
    if (/cuarto|recamara|dormitorio|habitacion|alcoba/.test(n)) return "cuarto";
    if (/bano|aseo/.test(n)) return "bano";
    if (/estudio|oficina|trabajo/.test(n)) return "estudio";
    return "otro";
  }

  async function alternar(h, btn) {
    btn.disabled = true;
    try {
      await api("/api/luces/habitacion", { habitacion: h.habitacion, encendida: h.encendidos === 0 });
    } catch (_) {}
    // avisa a luces.js (y a esta lista) para repintar
    document.dispatchEvent(new CustomEvent("luces-recargar"));
  }

  function fila(h) {
    const sin = h.habitacion === SIN_HAB;
    const t = sin ? "otro" : tipo(h.habitacion);
    const li = el("li", "inicio-fila");

    const principal = el("button", "inicio-fila-boton", {
      type: "button",
      "aria-label": `Ver ${h.habitacion}`
    });
    if (sin) principal.disabled = true;
    else {
      principal.addEventListener("click", () => {
        const nombre = h.habitacion;
        let target;
        if (window.CSS && CSS.escape) {
          target = document.querySelector('#luces-lista .luces-grupo[data-habitacion="' + CSS.escape(nombre) + '"]');
        } else {
          target = Array.from(document.querySelectorAll('#luces-lista .luces-grupo')).find(g => g.dataset.habitacion === nombre);
        }
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    const ico = el("span", `inicio-ico inicio-ico-${t}`);
    ico.innerHTML = ICONOS[t];
    principal.appendChild(ico);
    principal.appendChild(el("span", "inicio-fila-nombre", { textContent: h.habitacion }));

    if (h.en_linea < h.total) {
      principal.appendChild(el("span", "inicio-fila-aviso", { textContent: "sin respuesta" }));
    }
    li.appendChild(principal);

    const ins = el("button", "inicio-insignia" + (h.encendidos > 0 ? " activo" : ""), {
      type: "button"
    });
    const f = el("span", "inicio-insignia-ico");
    f.innerHTML = FOCO;
    ins.appendChild(f);
    ins.appendChild(el("span", "inicio-insignia-num", { textContent: String(h.encendidos) }));

    if (sin) {
      ins.disabled = true;
      ins.setAttribute("aria-label", `${h.encendidos} de ${h.total} encendidos`);
    } else {
      ins.setAttribute("aria-label", `${h.encendidos} de ${h.total} encendidos. ${h.encendidos > 0 ? "Apagar" : "Encender"} ${h.habitacion}`);
      ins.setAttribute("aria-pressed", h.encendidos > 0 ? "true" : "false");
      ins.addEventListener("click", () => alternar(h, ins));
    }
    li.appendChild(ins);
    return li;
  }

  function pintar(data) {
    const hs = data.habitaciones || [];
    if (hs.length === 0) {
      LISTA.replaceChildren(el("li", "inicio-lista-vacio", { textContent: "Sin habitaciones todavía" }));
      if (SUB) SUB.textContent = "";
      return;
    }

    let conLuz = 0;
    let totalHab = 0;
    const fragmento = document.createDocumentFragment();

    hs.forEach(h => {
      if (h.habitacion !== SIN_HAB) {
        totalHab++;
        if (h.encendidos > 0) conLuz++;
      }
      fragmento.appendChild(fila(h));
    });

    LISTA.replaceChildren(fragmento);
    if (SUB) SUB.textContent = totalHab > 0 ? `${conLuz} de ${totalHab} con luz` : "";
  }

  async function cargar() {
    if (!visible) return;
    try {
      const data = await api("/api/luces/habitaciones");
      pintar(data);
    } catch (_) {}
  }

  document.addEventListener("pestana", e => {
    visible = e.detail === "luces";
    if (visible) cargar();
  });

  document.addEventListener("luces-recargar", () => {
    cargar();
  });

  setInterval(() => {
    if (visible) cargar();
  }, 10000);
})();
