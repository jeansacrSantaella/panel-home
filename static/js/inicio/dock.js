/* Dock inferior de acciones rápidas para la pestaña Inicio.
   Clases usadas:
   - #inicio-dock: contenedor principal
   - .inicio-dock-item: cada píldora de acción rápida
   - .inicio-dock-icono: contenedor circular del ícono
   - .inicio-dock-textos: contenedor para título y subtítulo
   - .inicio-dock-titulo: texto principal
   - .inicio-dock-sub: texto secundario
*/
(function () {
  "use strict";

  // Íconos SVG fijos para las píldoras del dock
  const ICONO_LUCES = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>';
  const ICONO_CAMARAS = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/></svg>';
  const ICONO_INTERNET = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.94 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>';
  const ICONO_RUTINA = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg>';

  let dockEl = null;
  let estadoLuces = null;
  let estadoPanel = null;
  let estadoClima = null;

  function renderizar() {
    if (!dockEl) return;
    dockEl.innerHTML = "";

    // 1. Luces
    let lucesTitulo = "Luces apagadas";
    let lucesSub = "Toque para encender";
    let encendidasTotal = 0;
    if (estadoLuces && estadoLuces.luces) {
      const encendidas = estadoLuces.luces.filter(l => l.encendida);
      encendidasTotal = encendidas.length;
      if (encendidasTotal > 0) {
        lucesTitulo = `${encendidasTotal} ${encendidasTotal === 1 ? 'luz encendida' : 'luces encendidas'}`;
        lucesSub = "Toque para apagar todas";
      }
    }
    const itemLuces = crearPildora(ICONO_LUCES, lucesTitulo, lucesSub, async () => {
      try {
        if (encendidasTotal > 0) {
          await InicioPanel.api("/api/luces/todas", { method: "POST", body: { encendida: false } });
        } else {
          const confirmar = window.confirm("¿Seguro que deseas encender todas las luces?");
          if (!confirmar) return;
          await InicioPanel.api("/api/luces/todas", { method: "POST", body: { encendida: true } });
        }
        if (typeof InicioPanel.recargarLuces === "function") {
          await InicioPanel.recargarLuces();
        }
      } catch (err) {
        console.error("Error al alternar luces desde el dock", err);
      }
    });

    // 2. Cámaras
    let camTitulo = "Cámaras";
    let camSub = "Sin datos";
    if (estadoPanel && estadoPanel.camaras) {
      const totalCam = estadoPanel.camaras.length;
      const activas = estadoPanel.camaras.filter(c => c.estado === "ok" || c.estado === "activo" || c.conectada !== false).length;
      camTitulo = `Cámaras ${activas}/${totalCam}`;
      
      let ultimoMovTs = 0;
      if (estadoPanel.ultimo_movimiento) {
        for (const cid in estadoPanel.ultimo_movimiento) {
          const ts = estadoPanel.ultimo_movimiento[cid];
          if (ts > ultimoMovTs) ultimoMovTs = ts;
        }
      }
      camSub = ultimoMovTs ? InicioPanel.hace(ultimoMovTs) : "sin novedades";
    }
    const itemCamaras = crearPildora(ICONO_CAMARAS, camTitulo, camSub, () => {
      location.hash = "#capturas";
    });

    // 3. Internet
    let netTitulo = "Internet";
    let netSub = "Sin datos de red";
    if (estadoPanel) {
      if (estadoPanel.red === null) {
        netSub = "Sin datos de red";
      } else if (estadoPanel.red && estadoPanel.red.checks && estadoPanel.red.checks.wan && estadoPanel.red.checks.wan.down_since) {
        netTitulo = "Internet caído";
        netSub = InicioPanel.hace(estadoPanel.red.checks.wan.down_since);
      } else {
        netTitulo = "Internet ok";
        let msStr = "";
        if (estadoPanel.red && estadoPanel.red.series && estadoPanel.red.series.length > 0) {
          const ultimaSerie = estadoPanel.red.series[estadoPanel.red.series.length - 1];
          if (ultimaSerie && typeof ultimaSerie.valor === "number") {
            msStr = ` · ${Math.round(ultimaSerie.valor)} ms`;
          }
        }
        netSub = `Conectado${msStr}`;
      }
    }
    const itemInternet = crearPildora(ICONO_INTERNET, netTitulo, netSub, () => {
      location.hash = "#red";
    });

    // 4. Clima (oculto si no está configurado)
    let itemClima = null;
    if (estadoClima && estadoClima.configurado && estadoClima.actual) {
      const temp = `${Math.round(estadoClima.actual.temp)}°`;
      const desc = estadoClima.actual.descripcion || "Clima actual";
      const iconoClimaStr = InicioPanel.iconoClima(estadoClima.actual.icono || "sol", estadoClima.actual.es_dia !== false);
      itemClima = crearPildoraConSvgCustom(iconoClimaStr, temp, desc, () => {
        location.hash = "#clima";
      });
    }

    // 5. Rutina
    let rutinaTitulo = "Rutinas";
    let rutinaSub = "Sin rutinas";
    let rutinaActiva = null;
    if (estadoLuces && estadoLuces.rutinas && estadoLuces.rutinas.length > 0) {
      rutinaActiva = estadoLuces.rutinas[0];
      rutinaTitulo = rutinaActiva.nombre || "Rutina";
      rutinaSub = rutinaActiva.descripcion || "Toque para ejecutar";
    }
    const itemRutina = crearPildora(ICONO_RUTINA, rutinaTitulo, rutinaSub, async () => {
      if (!rutinaActiva) return;
      try {
        const res = await InicioPanel.api(`/api/rutinas/${rutinaActiva.id}/ejecutar`, { method: "POST" });
        const aviso = (res && res.resultado) || (res && res.mensaje) || "Rutina ejecutada";
        mostrarAvisoBreve(aviso);
      } catch (err) {
        console.error("Error al ejecutar rutina", err);
        mostrarAvisoBreve("Error al ejecutar rutina");
      }
    });

    dockEl.appendChild(itemLuces);
    dockEl.appendChild(itemCamaras);
    dockEl.appendChild(itemInternet);
    if (itemClima) dockEl.appendChild(itemClima);
    dockEl.appendChild(itemRutina);
  }

  function crearPildora(svgString, titulo, sub, onClick) {
    const btn = InicioPanel.el("button", "inicio-dock-item");
    btn.type = "button";
    
    const iconoDiv = InicioPanel.el("div", "inicio-dock-icono");
    iconoDiv.innerHTML = svgString;
    btn.appendChild(iconoDiv);

    const textosDiv = InicioPanel.el("div", "inicio-dock-textos");
    const titEl = InicioPanel.el("div", "inicio-dock-titulo", { textContent: titulo });
    const subEl = InicioPanel.el("div", "inicio-dock-sub", { textContent: sub });
    textosDiv.appendChild(titEl);
    textosDiv.appendChild(subEl);
    btn.appendChild(textosDiv);

    if (typeof onClick === "function") {
      btn.addEventListener("click", onClick);
    }
    return btn;
  }

  function crearPildoraConSvgCustom(svgHtml, titulo, sub, onClick) {
    const btn = InicioPanel.el("button", "inicio-dock-item");
    btn.type = "button";
    
    const iconoDiv = InicioPanel.el("div", "inicio-dock-icono");
    iconoDiv.innerHTML = svgHtml;
    btn.appendChild(iconoDiv);

    const textosDiv = InicioPanel.el("div", "inicio-dock-textos");
    const titEl = InicioPanel.el("div", "inicio-dock-titulo", { textContent: titulo });
    const subEl = InicioPanel.el("div", "inicio-dock-sub", { textContent: sub });
    textosDiv.appendChild(titEl);
    textosDiv.appendChild(subEl);
    btn.appendChild(textosDiv);

    if (typeof onClick === "function") {
      btn.addEventListener("click", onClick);
    }
    return btn;
  }

  function mostrarAvisoBreve(texto) {
    let aviso = document.getElementById("inicio-aviso-breve");
    if (!aviso) {
      aviso = InicioPanel.el("div", "inicio-aviso-breve", { id: "inicio-aviso-breve" });
      document.body.appendChild(aviso);
    }
    aviso.textContent = texto;
    aviso.classList.add("visible");
    setTimeout(() => {
      aviso.classList.remove("visible");
    }, 3000);
  }

  document.addEventListener("inicio-luces", e => {
    estadoLuces = e.detail;
    renderizar();
  });

  document.addEventListener("inicio-clima", e => {
    estadoClima = e.detail;
    renderizar();
  });

  document.addEventListener("panel", e => {
    estadoPanel = e.detail;
    renderizar();
  });

  document.addEventListener("pestana", e => {
    if (e.detail === "inicio") {
      const u = InicioPanel.ultimo();
      if (u) {
        estadoLuces = u.luces;
        estadoClima = u.clima;
        estadoPanel = u.panel;
      }
      renderizar();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      dockEl = document.getElementById("inicio-dock");
      renderizar();
    });
  } else {
    dockEl = document.getElementById("inicio-dock");
    renderizar();
  }
})();
