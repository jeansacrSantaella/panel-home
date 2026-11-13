/* Pestaña Red: historial de eventos de la red, paginado y con filtros.
   Usa window.RedPanel (nucleo.js) y pide /api/red/eventos. */
(function () {
  "use strict";
  const R = window.RedPanel;

  // kind -> [título en español, nivel de la lista]
  const KINDS = {
    lan_down: ["Red local caída", "alto"],
    lan_up: ["Red local restablecida", "info"],
    wan_down: ["Internet caído", "alto"],
    wan_up: ["Internet restablecido", "info"],
    dns_down: ["DNS sin respuesta", "medio"],
    dns_up: ["DNS restablecido", "info"],
    new_device: ["Equipo nuevo", "medio"],
    device_online: ["Equipo conectado", "bajo"],
    device_offline: ["Equipo desconectado", "bajo"],
    ip_change: ["Cambió la IP pública", "medio"],
    ip_first: ["IP pública detectada", "info"],
    monitor_gap: ["La sonda estuvo detenida", "bajo"],
  };

  const $ = id => document.getElementById(id);
  const campos = {
    desde: $("red-eventos-desde"),
    hasta: $("red-eventos-hasta"),
    tipo: $("red-eventos-tipo"),
    filas: $("red-eventos-filas"),
  };
  const sub = $("red-eventos-sub");
  const tabla = $("red-eventos-tabla");
  const paginas = $("red-eventos-paginas");

  let pagina = 0;
  let peticion = 0;      // ignora respuestas antiguas si el usuario cambia algo durante la carga
  let primeraVez = true;

  const titulo = kind => (Object.hasOwn(KINDS, kind) ? KINDS[kind][0] : kind);
  const nivel = kind => (Object.hasOwn(KINDS, kind) ? KINDS[kind][1] : "info");

  // Rellena el selector de tipos conservando "Todos los tipos" y la selección actual
  function llenarTipos(kinds) {
    const previo = campos.tipo.value;
    const lista = kinds.slice();
    if (previo && !lista.includes(previo)) lista.push(previo);
    campos.tipo.replaceChildren(R.el("option", "", { value: "", textContent: "Todos los tipos" }));
    for (const kind of lista) {
      campos.tipo.append(R.el("option", "", { value: kind, textContent: titulo(kind) }));
    }
    campos.tipo.value = previo;
  }

  function fila(ev) {
    const li = R.el("li");
    li.dataset.nivel = nivel(ev.kind);

    const texto = R.el("span", "actividad-texto");
    texto.append(R.el("b", "", { textContent: titulo(ev.kind) }), " ",
      R.el("span", "tenue", { textContent: ev.detail || "" }));

    const hora = R.el("time", "", { textContent: R.fecha(ev.ts) });
    hora.title = R.hace(ev.ts);
    if (ev.ts) hora.dateTime = new Date(ev.ts * 1000).toISOString();

    li.append(texto, hora);
    return li;
  }

  function pintar(datos) {
    llenarTipos(datos.kinds || []);
    sub.textContent = `${datos.total} ${datos.total === 1 ? "evento" : "eventos"}`;

    if (!datos.events.length) {
      tabla.replaceChildren(R.el("p", "tenue", { textContent: "No hay eventos con esos filtros." }));
    } else {
      const lista = R.el("ul", "actividad");
      lista.setAttribute("aria-label", "Eventos de la red");
      lista.append(...datos.events.map(fila));
      tabla.replaceChildren(lista);
    }

    R.paginador(paginas, datos.page, datos.pages, nueva => {
      pagina = nueva;
      cargar();
    });
  }

  async function cargar() {
    const id = ++peticion;
    const q = new URLSearchParams({
      from: campos.desde.value,
      to: campos.hasta.value,
      kind: campos.tipo.value,
      page: String(pagina),
      size: campos.filas.value,
    });
    try {
      const datos = await R.api(`/api/red/eventos?${q}`);
      if (id !== peticion) return;
      pagina = datos.page;  // el servidor puede ajustar la página al total
      pintar(datos);
    } catch (e) {
      if (id !== peticion) return;
      sub.textContent = "";
      tabla.replaceChildren(R.el("p", "aviso", { textContent: "No se pudieron cargar los eventos." }));
      paginas.replaceChildren();
    }
  }

  // Primera carga con el primer "red-datos"; después solo si está en la página 0 y sin filtros
  document.addEventListener("red-datos", () => {
    const sinFiltros = !campos.desde.value && !campos.hasta.value && !campos.tipo.value;
    if (!primeraVez && !(pagina === 0 && sinFiltros)) return;
    primeraVez = false;
    cargar();
  });

  // Cualquier cambio de filtro o de filas vuelve a la página 0
  [campos.desde, campos.hasta, campos.tipo, campos.filas].forEach(control => {
    control.addEventListener("change", () => {
      pagina = 0;
      cargar();
    });
  });

  // El formulario no debe recargar la página (Enter en un campo de fecha)
  $("red-eventos-form").addEventListener("submit", e => e.preventDefault());
})();
