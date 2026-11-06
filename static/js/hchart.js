/**
 * hchart.js — Librería ligera de gráficos en HTML/CSS puro (sin canvas, sin SVG).
 * Expone window.HChart para barras, columnas, cinta, dona, chispa, radial y formatoBytes.
 */
(function (global) {
  "use strict";

  // Estilos CSS inyectados automáticamente con prefijo hc-
  // :where() deja la especificidad en 0 para que la página pueda redefinir las variables
  const CSS = `
:where(.hc) {
  --hc-fondo: Canvas;
  --hc-acento: #3b82f6;
  --hc-ok: #22c55e;
  --hc-alerta: #f59e0b;
  --hc-mal: #ef4444;
  --hc-vacio: rgba(127,127,127,.18);
  --hc-texto: inherit;
  --hc-tenue: rgba(127,127,127,.9);
  --hc-linea: rgba(127,127,127,.35);
  font-family: inherit;
  color: var(--hc-texto);
  box-sizing: border-box;
}
.hc *, .hc *::before, .hc *::after {
  box-sizing: border-box;
  transition: width .4s, height .4s, background-color .4s;
}
@media (prefers-reduced-motion: reduce) {
  .hc, .hc * {
    transition: none !important;
  }
}
.hc-vacio-msg {
  padding: 12px;
  text-align: center;
  color: var(--hc-tenue);
  font-style: italic;
  font-size: 0.9em;
}

/* Gráfico de barras horizontales */
.hc-barras {
  display: grid;
  grid-template-columns: max-content 1fr max-content;
  gap: 6px 12px;
  align-items: center;
  width: 100%;
}
.hc-barra-etiq {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 130px;
  font-size: 0.85em;
}
.hc-pista {
  background: var(--hc-vacio);
  height: 12px;
  border-radius: 4px;
  overflow: hidden;
  width: 100%;
}
.hc-barra-relleno {
  height: 100%;
  border-radius: 4px;
}
.hc-barra-val {
  font-size: 0.85em;
  color: var(--hc-tenue);
  text-align: right;
  min-width: 40px;
}

/* Gráfico de columnas verticales */
.hc-columnas-wrap {
  display: flex;
  flex-direction: column;
  width: 100%;
}
.hc-columnas {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  width: 100%;
}
.hc-columna-pista {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
  background: transparent;
}
.hc-columna {
  width: 100%;
  border-radius: 4px 4px 0 0;
  min-height: 2px;
}
.hc-columnas-etiqs {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 0.75em;
  color: var(--hc-tenue);
}
.hc-col-etiq {
  flex: 1;
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
}

/* Cinta de disponibilidad */
.hc-cinta {
  display: flex;
  gap: 0;              /* con 144 tramos cualquier separación se come los colores */
  border-radius: 3px;
  overflow: hidden;
  width: 100%;
  height: 24px;
  align-items: center;
}
.hc-cinta-celda {
  flex: 1;
  height: 100%;
}

/* Dona */
.hc-dona-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.hc-dona-grafico {
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
}
.hc-dona-centro {
  position: absolute;
  border-radius: 50%;
  background: var(--hc-fondo);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.85em;
  font-weight: bold;
  padding: 4px;
}
.hc-dona-leyenda {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  justify-content: center;
  font-size: 0.8em;
}
.hc-dona-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.hc-dona-box {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

/* Chispa */
.hc-chispa {
  display: inline-flex;
  align-items: flex-end;
  gap: 1px;
  vertical-align: middle;
}
.hc-chispa-bar {
  flex: 1;
  border-radius: 1px 1px 0 0;
  min-height: 1px;
}

/* Mapa radial */
.hc-radial {
  position: relative;
  width: 100%;
  overflow: hidden;
}
.hc-radial-centro {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  text-align: center;
  font-weight: bold;
  font-size: 0.85em;
  background: var(--hc-vacio);
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid var(--hc-linea);
}
.hc-radial-linea {
  position: absolute;
  left: 50%;
  top: 50%;
  height: 1px;
  background: var(--hc-linea);
  transform-origin: 0 50%;
  z-index: 1;
  pointer-events: none;
}
.hc-radial-nodo-wrap {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 3;
}
.hc-radial-nodo {
  border-radius: 50%;
  border: none;
  cursor: pointer;
  padding: 0;
  outline: none;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hc-radial-nodo.hc-estado-ok { background: var(--hc-ok); }
.hc-radial-nodo.hc-estado-alerta { background: var(--hc-alerta); }
.hc-radial-nodo.hc-estado-mal { background: var(--hc-mal); }
.hc-radial-nodo.hc-estado-apagado {
  background: var(--hc-vacio);
  border: 2px dashed var(--hc-linea);
}
.hc-radial-etiq {
  font-size: 0.7em;
  color: var(--hc-tenue);
  margin-top: 2px;
  white-space: nowrap;
  text-align: center;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}
`;

  // Inyecta el bloque de estilos una sola vez
  function estilos() {
    if (!document.getElementById("hc-estilos")) {
      const tag = document.createElement("style");
      tag.id = "hc-estilos";
      tag.textContent = CSS;
      document.head.appendChild(tag);
    }
  }

  // Helper para crear elementos DOM con clases y propiedades
  function el(tag, clase, props) {
    const elem = document.createElement(tag);
    if (clase) elem.className = clase;
    if (props) {
      for (const k in props) {
        if (k === "style" && typeof props[k] === "object") {
          Object.assign(elem.style, props[k]);
        } else if (k === "textContent") {
          elem.textContent = props[k];
        } else if (k === "title") {
          elem.title = props[k];
        } else if (k in elem) {
          elem[k] = props[k];
        } else {
          elem.setAttribute(k, props[k]);
        }
      }
    }
    return elem;
  }

  // Prepara y vacía el contenedor
  function limpiar(cont, etiqueta) {
    estilos();
    if (!cont) return;
    cont.innerHTML = "";
    if (!cont.classList.contains("hc")) {
      cont.classList.add("hc");
    }
    cont.setAttribute("role", "img");
    cont.setAttribute("aria-label", etiqueta || "Gráfico");
  }

  // Formateador numérico por defecto
  const defFormato = v => (v == null ? "–" : String(Math.round(v * 100) / 100));

  // 1. Barras horizontales
  function barras(cont, items, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Gráfico de barras");
    if (!cont) return;

    if (!items || !items.length) {
      cont.appendChild(el("div", "hc-vacio-msg", { textContent: opciones.vacio || "Sin datos" }));
      return;
    }

    const fmt = opciones.formato || defFormato;
    const maxVal = opciones.max != null ? opciones.max : Math.max(1, ...items.map(it => it.valor || 0));
    const grid = el("div", "hc-barras");

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const val = item.valor != null ? item.valor : 0;
      const pct = Math.min(100, Math.max(0, (val / maxVal) * 100));

      let color = item.color;
      if (!color && typeof opciones.colorear === "function") {
        color = opciones.colorear(item);
      }
      if (!color) color = "var(--hc-acento)";

      const txtTooltip = item.texto || (item.etiqueta + ": " + fmt(item.valor));

      const etiqEl = el("div", "hc-barra-etiq", { textContent: item.etiqueta || "", title: txtTooltip });
      const pistaEl = el("div", "hc-pista", { title: txtTooltip });
      const rellenoEl = el("div", "hc-barra-relleno", { style: { width: pct + "%", background: color } });
      pistaEl.appendChild(rellenoEl);

      const valEl = el("div", "hc-barra-val", { textContent: item.texto || fmt(item.valor), title: txtTooltip });

      grid.appendChild(etiqEl);
      grid.appendChild(pistaEl);
      grid.appendChild(valEl);
    }
    cont.appendChild(grid);
  }

  // 2. Columnas verticales
  function columnas(cont, valores, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Gráfico de columnas");
    if (!cont) return;

    if (!valores || !valores.length) {
      cont.appendChild(el("div", "hc-vacio-msg", { textContent: opciones.vacio || "Sin datos" }));
      return;
    }

    const alto = opciones.alto != null ? opciones.alto : 80;
    const fmt = opciones.formato || defFormato;
    const validVals = valores.filter(v => v != null);
    const maxVal = opciones.max != null ? opciones.max : Math.max(1, ...(validVals.length ? validVals : [1]));
    const etiquetas = opciones.etiquetas;

    const wrap = el("div", "hc-columnas-wrap");
    const colsDiv = el("div", "hc-columnas", { style: { height: alto + "px" } });

    for (let i = 0; i < valores.length; i++) {
      const val = valores[i];
      const colPista = el("div", "hc-columna-pista");
      const labelPrefix = (etiquetas && etiquetas[i] != null) ? etiquetas[i] + ": " : "";

      if (val == null) {
        const colEl = el("div", "hc-columna", {
          style: { height: "100%", background: "var(--hc-vacio)", opacity: "0.5" },
          title: labelPrefix + "sin datos"
        });
        colPista.appendChild(colEl);
      } else {
        const pct = Math.min(100, Math.max(0, (val / maxVal) * 100));
        let colColor = "var(--hc-acento)";
        if (opciones.marcar === i) {
          colColor = "var(--hc-alerta)";
        } else if (typeof opciones.color === "function") {
          colColor = opciones.color(val, i);
        } else if (opciones.color) {
          colColor = opciones.color;
        }

        const colEl = el("div", "hc-columna", {
          style: { height: pct + "%", background: colColor },
          title: labelPrefix + fmt(val)
        });
        colPista.appendChild(colEl);
      }
      colsDiv.appendChild(colPista);
    }
    wrap.appendChild(colsDiv);

    if (etiquetas && etiquetas.length) {
      const step = Math.ceil(valores.length / 12);
      const etiqsDiv = el("div", "hc-columnas-etiqs");
      for (let i = 0; i < valores.length; i++) {
        const showLabel = (i % step === 0);
        const span = el("span", "hc-col-etiq", {
          textContent: showLabel ? String(etiquetas[i]) : ""
        });
        etiqsDiv.appendChild(span);
      }
      wrap.appendChild(etiqsDiv);
    }
    cont.appendChild(wrap);
  }

  // 3. Cinta de disponibilidad
  function cinta(cont, valores, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Cinta de disponibilidad");
    if (!cont) return;

    if (!valores || !valores.length) {
      cont.appendChild(el("div", "hc-vacio-msg", { textContent: opciones.vacio || "Sin datos" }));
      return;
    }

    const inicio = opciones.inicio != null ? opciones.inicio : 0;
    const paso = opciones.paso != null ? opciones.paso : 600;
    const umbrales = opciones.umbrales || [0.99, 0.9];
    const cintaDiv = el("div", "hc-cinta");

    for (let i = 0; i < valores.length; i++) {
      const v = valores[i];
      let color = "var(--hc-vacio)";
      if (v != null) {
        if (v >= umbrales[0]) color = "var(--hc-ok)";
        else if (v >= umbrales[1]) color = "var(--hc-alerta)";
        else color = "var(--hc-mal)";
      }

      const tsSec = inicio + i * paso;
      const fecha = new Date(tsSec < 1e11 ? tsSec * 1000 : tsSec);
      const horaStr = opciones.formatoHora
        ? opciones.formatoHora(fecha)
        : fecha.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const valText = v == null ? "sin datos" : (v * 100).toFixed(1) + "%";
      const tooltip = horaStr + " · " + valText;

      const celda = el("div", "hc-cinta-celda", {
        style: { background: color },
        title: tooltip
      });
      cintaDiv.appendChild(celda);
    }
    cont.appendChild(cintaDiv);
  }

  // 4. Dona con conic-gradient
  function dona(cont, partes, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Gráfico de dona");
    if (!cont) return;

    const palette = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];
    const tam = opciones.tam != null ? opciones.tam : 120;
    const grosor = opciones.grosor != null ? opciones.grosor : 18;
    const centroTexto = opciones.centro != null ? opciones.centro : "";
    const total = partes ? partes.reduce((acc, p) => acc + (p.valor || 0), 0) : 0;
    const wrap = el("div", "hc-dona-wrap");

    if (!partes || !partes.length || total <= 0) {
      const donaEmpty = el("div", "hc-dona-grafico", {
        style: { width: tam + "px", height: tam + "px", background: "var(--hc-vacio)" }
      });
      const centroEl = el("div", "hc-dona-centro", {
        style: {
          width: (tam - grosor * 2) + "px",
          height: (tam - grosor * 2) + "px",
          top: grosor + "px",
          left: grosor + "px"
        },
        textContent: centroTexto
      });
      donaEmpty.appendChild(centroEl);
      wrap.appendChild(donaEmpty);
      wrap.appendChild(el("div", "hc-vacio-msg", { textContent: opciones.vacio || "Sin datos" }));
      cont.appendChild(wrap);
      return;
    }

    let cumPct = 0;
    const stops = [];
    const itemsConColor = partes.map((p, i) => {
      const color = p.color || palette[i % palette.length];
      const pct = ((p.valor || 0) / total) * 100;
      const start = cumPct;
      cumPct += pct;
      stops.push(`${color} ${start.toFixed(2)}% ${cumPct.toFixed(2)}%`);
      return { ...p, color, pct };
    });

    const bgGradient = `conic-gradient(${stops.join(", ")})`;
    const donaGrafico = el("div", "hc-dona-grafico", {
      style: { width: tam + "px", height: tam + "px", background: bgGradient }
    });

    const centroEl = el("div", "hc-dona-centro", {
      style: {
        width: (tam - grosor * 2) + "px",
        height: (tam - grosor * 2) + "px",
        top: grosor + "px",
        left: grosor + "px"
      },
      textContent: centroTexto
    });
    donaGrafico.appendChild(centroEl);
    wrap.appendChild(donaGrafico);

    const leyenda = el("div", "hc-dona-leyenda");
    itemsConColor.forEach(item => {
      const itemDiv = el("div", "hc-dona-item", {
        title: `${item.etiqueta}: ${item.valor} (${item.pct.toFixed(1)}%)`
      });
      const box = el("span", "hc-dona-box", { style: { background: item.color } });
      const txt = el("span", "", { textContent: `${item.etiqueta} (${item.pct.toFixed(1)}%)` });
      itemDiv.appendChild(box);
      itemDiv.appendChild(txt);
      leyenda.appendChild(itemDiv);
    });
    wrap.appendChild(leyenda);

    cont.appendChild(wrap);
  }

  // 5. Chispa en línea
  function chispa(cont, valores, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Gráfico de chispa");
    if (!cont) return;
    if (!valores || !valores.length) return;

    const alto = opciones.alto != null ? opciones.alto : 24;
    const ancho = opciones.ancho != null ? opciones.ancho : 96;
    const color = opciones.color || "var(--hc-acento)";
    const fmt = defFormato;
    const validVals = valores.filter(v => v != null);
    const maxVal = Math.max(1, ...(validVals.length ? validVals : [1]));

    const container = el("div", "hc-chispa", {
      style: { width: ancho + "px", height: alto + "px" }
    });

    for (let i = 0; i < valores.length; i++) {
      const v = valores[i];
      const pct = v != null ? Math.min(100, Math.max(0, (v / maxVal) * 100)) : 0;
      const bar = el("div", "hc-chispa-bar", {
        style: { height: pct + "%", background: v == null ? "var(--hc-vacio)" : color },
        title: fmt(v)
      });
      container.appendChild(bar);
    }
    cont.appendChild(container);
  }

  // 6. Mapa radial / estrella
  function radial(cont, datos, opciones = {}) {
    limpiar(cont, opciones.etiqueta || "Mapa radial");
    if (!cont) return;

    const datosObj = datos || {};
    const centroData = datosObj.centro || { etiqueta: "Centro", titulo: "" };
    const nodos = datosObj.nodos || [];
    const alto = opciones.alto != null ? opciones.alto : 360;

    const radContainer = el("div", "hc-radial", { style: { height: alto + "px" } });

    // Elemento central
    const centroEl = el("div", "hc-radial-centro", {
      textContent: centroData.etiqueta || "",
      title: centroData.titulo || centroData.etiqueta || ""
    });
    radContainer.appendChild(centroEl);

    const N = nodos.length;
    const lineas = [];

    for (let i = 0; i < N; i++) {
      const nodo = nodos[i];
      let radiusPct = 42;
      if (N > 16) {
        radiusPct = (i % 2 === 0) ? 34 : 46;
      }
      const angleRad = (2 * Math.PI * i) / N - Math.PI / 2;
      const xPct = 50 + radiusPct * Math.cos(angleRad);
      const yPct = 50 + radiusPct * Math.sin(angleRad);

      // Línea desde el centro
      const linea = el("div", "hc-radial-linea");
      radContainer.appendChild(linea);
      lineas.push({ el: linea, xPct, yPct });

      // Contenedor del nodo
      const wrapNodo = el("div", "hc-radial-nodo-wrap", {
        style: { left: xPct + "%", top: yPct + "%" }
      });

      const peso = nodo.peso != null ? nodo.peso : 0;
      const size = 22 + Math.min(1, Math.max(0, peso)) * 22;
      const estadoClass = "hc-estado-" + (nodo.estado || "ok");

      const btn = el("button", "hc-radial-nodo " + estadoClass, {
        style: { width: size + "px", height: size + "px" },
        title: nodo.titulo || nodo.etiqueta || ""
      });
      if (typeof opciones.onClick === "function") {
        btn.onclick = (e) => {
          e.stopPropagation();
          opciones.onClick(nodo);
        };
      }

      const etiqRaw = nodo.etiqueta || "";
      const etiqCortada = etiqRaw.length > 14 ? etiqRaw.slice(0, 13) + "…" : etiqRaw;
      const etiqEl = el("span", "hc-radial-etiq", { textContent: etiqCortada, title: etiqRaw });

      wrapNodo.appendChild(btn);
      wrapNodo.appendChild(etiqEl);
      radContainer.appendChild(wrapNodo);
    }

    cont.appendChild(radContainer);

    // Ajuste de longitud y ángulo de las líneas en px
    function recalcularLineas() {
      const cw = cont.clientWidth || 360;
      const ch = cont.clientHeight || alto;
      for (let i = 0; i < lineas.length; i++) {
        const l = lineas[i];
        const dx = ((l.xPct - 50) / 100) * cw;
        const dy = ((l.yPct - 50) / 100) * ch;
        const len = Math.sqrt(dx * dx + dy * dy);
        const deg = Math.atan2(dy, dx) * (180 / Math.PI);
        l.el.style.width = len.toFixed(1) + "px";
        l.el.style.transform = `rotate(${deg.toFixed(1)}deg)`;
      }
    }

    recalcularLineas();

    // un solo observador por contenedor: se reemplaza en cada redibujo
    if (cont._hcObservador) cont._hcObservador.disconnect();
    if (typeof ResizeObserver !== "undefined") {
      cont._hcObservador = new ResizeObserver(() => recalcularLineas());
      cont._hcObservador.observe(cont);
    }
  }

  // 7. Formateador de bytes
  function formatoBytes(n) {
    if (n == null) return "–";
    if (n === 0) return "0 B";
    const unidades = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), unidades.length - 1);
    if (i <= 0) return n + " B";
    return (n / Math.pow(1024, i)).toFixed(1) + " " + unidades[i];
  }

  // Exposición global
  global.HChart = {
    barras,
    columnas,
    cinta,
    dona,
    chispa,
    radial,
    formatoBytes,
    version: "0.1.0"
  };
})(window);
