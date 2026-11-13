/* Inicio: notas de lo último en casa (junto al reloj).
   Lee /api/eventos?limite=40 y muestra hasta 4 notas recientes en #inicio-notas.
   Clases usadas:
   - inicio-nota: contenedor de cada píldora
   - inicio-nota-ico: círculo contenedor del icono SVG
   - inicio-nota-titulo: texto principal en negrita
   - inicio-nota-sub: subtítulo tenue
*/
(function () {
  "use strict";

  const CADA_EVENTOS = 30000;
  let timerEventos = null;

  // Íconos SVG fijos para las fuentes de eventos
  const ICONOS_FUENTE = {
    camaras: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 10 5-3v10l-5-3v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v3Z"/></svg>',
    red: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 1 7.54 16.6l-1.42-1.42A8 8 0 1 0 12 20v2a10 10 0 0 1 0-20Zm0 6a4 4 0 1 1-4 4 4 4 0 0 1 4-4Z"/></svg>',
    luces: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7ZM9 21h6v1H9v-1Z"/></svg>',
    sistema: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm1 15h-2v-2h2Zm0-4h-2V7h2Z"/></svg>'
  };

  const TIPOS_IGNORADOS = new Set([
    "equipo_conectado",
    "equipo_desconectado",
    "luz_encendida",
    "luz_apagada",
    "pausa_monitor",
    "ip_publica",
    "fuente_ok"
  ]);

  function obtenerIconoFuente(fuente) {
    if (Object.prototype.hasOwnProperty.call(ICONOS_FUENTE, fuente)) {
      return ICONOS_FUENTE[fuente];
    }
    return ICONOS_FUENTE.sistema;
  }

  function obtenerClaseNivel(nivel) {
    if (nivel === "alto") return "nivel-alto";
    if (nivel === "medio") return "nivel-medio";
    if (nivel === "bajo") return "nivel-bajo";
    return "nivel-info";
  }

  function destinoPorFuente(fuente, tipo) {
    if (tipo === "movimiento" || fuente === "camaras") return "#capturas";
    if (fuente === "red") return "#red";
    if (fuente === "luces") return "#luces";
    return "#resumen";
  }

  async function cargarNotas() {
    const contenedor = document.getElementById("inicio-notas");
    if (!contenedor) return;

    try {
      const datos = await window.InicioPanel.api("/api/eventos?limite=40");
      const eventos = (datos && datos.eventos) || [];

      // Filtrar tipos de poca importancia
      const filtrados = eventos.filter(ev => !TIPOS_IGNORADOS.has(ev.tipo));

      // Seleccionar hasta 4 más recientes de distinto tipo
      const elegidos = [];
      const tiposVistos = new Set();
      for (const ev of filtrados) {
        if (!tiposVistos.has(ev.tipo)) {
          tiposVistos.add(ev.tipo);
          elegidos.push(ev);
          if (elegidos.length >= 4) break;
        }
      }

      contenedor.innerHTML = "";

      if (elegidos.length === 0) {
        const nota = window.InicioPanel.el("div", "inicio-nota");
        const ico = window.InicioPanel.el("div", "inicio-nota-ico nivel-info");
        ico.innerHTML = ICONOS_FUENTE.sistema;
        const texto = window.InicioPanel.el("div");
        const titulo = window.InicioPanel.el("div", "inicio-nota-titulo", { textContent: "Todo tranquilo" });
        const sub = window.InicioPanel.el("div", "inicio-nota-sub", { textContent: "sin novedades recientes" });

        texto.appendChild(titulo);
        texto.appendChild(sub);
        nota.appendChild(ico);
        nota.appendChild(texto);
        contenedor.appendChild(nota);
        return;
      }

      for (const ev of elegidos) {
        const nota = window.InicioPanel.el("div", "inicio-nota");
        nota.addEventListener("click", () => {
          window.location.hash = destinoPorFuente(ev.fuente, ev.tipo);
        });

        const claseNivel = obtenerClaseNivel(ev.nivel);
        const ico = window.InicioPanel.el("div", `inicio-nota-ico ${claseNivel}`);
        ico.innerHTML = obtenerIconoFuente(ev.fuente);

        let textoTitulo = ev.titulo || "";
        if (ev.tipo === "movimiento") {
          textoTitulo = `Movimiento en ${ev.detalle || "cámara"}`;
        }

        let detalleRecortado = (ev.detalle || "").trim();
        if (detalleRecortado.length > 40) {
          detalleRecortado = detalleRecortado.substring(0, 40) + "…";
        }
        const textoSub = `${detalleRecortado} · ${window.InicioPanel.hace(ev.ts)}`;

        const textoDiv = window.InicioPanel.el("div");
        const tituloEl = window.InicioPanel.el("div", "inicio-nota-titulo", { textContent: textoTitulo });
        const subEl = window.InicioPanel.el("div", "inicio-nota-sub", { textContent: textoSub });

        textoDiv.appendChild(tituloEl);
        textoDiv.appendChild(subEl);
        nota.appendChild(ico);
        nota.appendChild(textoDiv);
        contenedor.appendChild(nota);
      }
    } catch (_) {
      // Silenciar errores de red puntuales en notas
    }
  }

  function detener() {
    clearInterval(timerEventos);
    timerEventos = null;
  }

  document.addEventListener("pestana", e => {
    detener();
    if (e.detail !== "inicio") return;
    cargarNotas();
    timerEventos = setInterval(cargarNotas, CADA_EVENTOS);
  });
})();
