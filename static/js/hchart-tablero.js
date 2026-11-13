/**
 * hchart-tablero.js — Componentes de gráfica avanzados para el tablero (PleyadesHome).
 * Extiende window.HChart con anillos segmentados, progreso, bloques, área y anillos múltiples.
 */
(function (global) {
  "use strict";

  // Asegura que window.HChart existe
  const HChart = global.HChart || (global.HChart = {});

  // Estilos CSS inyectados para los componentes del tablero
  const CSS_TABLERO = `
:where(.hct) {
  --texto: var(--hc-texto, #ffffff);
  --tenue: var(--hc-tenue, rgba(255,255,255,0.6));
  --borde: var(--hc-linea, rgba(255,255,255,0.15));
  --tarjeta: rgba(255,255,255,0.02);
  --marca-degradado: linear-gradient(90deg, #8B5CF6, #5aa8ff, #00E5FF);
  --marca-violeta: #8B5CF6;
  --marca-cian: #00E5FF;
  font-family: inherit;
  color: var(--texto);
  box-sizing: border-box;
  position: relative;
}
.hct *, .hct *::before, .hct *::after {
  box-sizing: border-box;
  transition: all .3s ease;
}
@media (prefers-reduced-motion: reduce) {
  .hct, .hct * {
    transition: none !important;
  }
}
.hct-vacio {
  padding: 16px;
  text-align: center;
  color: var(--tenue);
  font-style: italic;
  font-size: 0.9em;
}

/* Anillo segmentado: cuadrado de --hct-tam, escala con max-width:100% */
.hct-anillo-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}
.hct-anillo-svg {
  position: relative;
  width: var(--hct-tam, 120px);
  max-width: 100%;
  aspect-ratio: 1;
  container-type: size;
  flex: none;
}
.hct-anillo-seg {
  position: absolute;
  left: 50%;
  top: 50%;
  background: var(--borde);
}
.hct-anillo-centro {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  z-index: 2;
  gap: 2cqw;
  line-height: 1.1;
}
.hct-anillo-val {
  font-size: 19cqw;
  font-weight: bold;
  background: var(--marca-degradado);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hct-anillo-etiq {
  font-size: 8cqw;
  max-width: 62cqw;
  color: var(--tenue);
  text-transform: uppercase;
  letter-spacing: .06em;
  text-align: center;
}

/* Progreso */
.hct-progreso-lista {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.hct-progreso-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}
.hct-progreso-info > span:last-child { color: var(--tenue); }
.hct-progreso-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.85em;
}
.hct-progreso-pista {
  background: var(--borde);
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  width: 100%;
}
.hct-progreso-relleno {
  height: 100%;
  border-radius: 3px;
  background: var(--marca-degradado);
}

/* Bloques */
.hct-bloques-lista {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.hct-bloques-fila {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.hct-bloques-etiq {
  font-size: 0.85em;
  width: 110px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--tenue);
}
.hct-bloques-grid {
  display: flex;
  gap: 2px;
  flex: 1;
}
.hct-bloque {
  flex: 1;
  height: 12px;
  border-radius: 2px;
  background: var(--borde);
}
.hct-bloque.activo { background: var(--bc, var(--marca-cian)); }

/* Gráfica de área */
.hct-area-wrap { display: flex; flex-direction: column; width: 100%; gap: 6px; }
.hct-area-cont { position: relative; width: 100%; overflow: hidden; }
.hct-area-plot { position: absolute; left: 6px; right: 6px; top: 30px; bottom: 2px; }
.hct-area-guia {
  position: absolute; left: -6px; right: -6px; height: 0;
  border-top: 1px dashed var(--borde); pointer-events: none;
}
.hct-area-guia.cero { border-top-style: solid; }
.hct-area-guia-val {
  position: absolute; left: 6px; bottom: 2px;
  font-size: 0.7em; line-height: 1; color: var(--tenue); white-space: nowrap;
}
.hct-area-relleno, .hct-area-linea { position: absolute; inset: 0; pointer-events: none; }
.hct-area-marca {
  position: absolute; top: -6px; bottom: 0; width: 1px;
  background: rgba(255,255,255,0.28); pointer-events: none; z-index: 3;
}
.hct-area-marca-etiq {
  position: absolute; top: -20px; left: 0; transform: translateX(-50%);
  font-size: 0.7em; line-height: 1.2; background: rgba(20,26,40,0.9);
  border: 1px solid var(--borde); padding: 1px 8px; border-radius: 999px;
  white-space: nowrap; color: var(--texto);
}
.hct-area-marca-pto {
  position: absolute; width: 9px; height: 9px; z-index: 4; border-radius: 50%;
  background: #fff; transform: translate(-50%, -50%);
  box-shadow: 0 0 0 3px rgba(255,255,255,0.2);
}
.hct-area-pto {
  position: absolute; width: 8px; height: 8px; border-radius: 50%;
  border: 2px solid var(--pc, #00E5FF); background: #0B0F17;
  transform: translate(-50%, -50%); z-index: 2; cursor: default;
}
.hct-area-etiqs-x { position: relative; height: 1.2em; font-size: 0.75em; color: var(--tenue); margin: 0 6px; }
.hct-area-etiqs-x span { position: absolute; top: 0; white-space: nowrap; transform: translateX(-50%); }
.hct-area-leyenda { display: flex; gap: 14px; justify-content: center; font-size: 0.8em; margin-top: 4px; }
.hct-area-leyenda-item { display: flex; align-items: center; gap: 6px; }
.hct-area-leyenda-box { width: 10px; height: 10px; border-radius: 2px; }

/* Anillos múltiples */
.hct-anillos-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}
.hct-anillos-fila {
  display: flex;
  justify-content: space-around;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.hct-anillos-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
}
.hct-anillos-item > div:first-child { width: 72px; max-width: 100%; }
.hct-anillos-linea-wrap {
  position: relative;
  height: 24px;
  width: 100%;
  display: flex;
  align-items: center;
}
.hct-anillos-barra {
  position: absolute;
  left: 10px;
  right: 10px;
  height: 2px;
  background: var(--borde);
}
.hct-anillos-punto {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--marca-cian);
  transform: translateX(-50%);
}
`;

  // Inyecta estilos del tablero una sola vez
  function estilosTablero() {
    if (!document.getElementById("hct-estilos")) {
      const tag = document.createElement("style");
      tag.id = "hct-estilos";
      tag.textContent = CSS_TABLERO;
      document.head.appendChild(tag);
    }
  }

  // Helper DOM genérico
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

  // Prepara contenedor base
  function limpiarContenedor(cont, label) {
    estilosTablero();
    if (!cont) return;
    cont.innerHTML = "";
    if (!cont.classList.contains("hct")) {
      cont.classList.add("hct");
    }
    cont.setAttribute("role", "img");
    cont.setAttribute("aria-label", label || "Gráfico de tablero");
  }

  // Interpola el degradado de marca (violeta, azul, cian) en t de 0 a 1
  function colorMarca(t) {
    const cs = [[139, 92, 246], [90, 168, 255], [0, 229, 255]];
    t = Math.min(1, Math.max(0, t)) * 2;
    const i = Math.min(1, Math.floor(t)), f = t - i;
    const c = cs[i].map((v, k) => Math.round(v + (cs[i + 1][k] - v) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  // 1. Anillo segmentado
  function anillo(cont, opciones = {}) {
    const valor = opciones.valor;
    const max = opciones.max != null ? opciones.max : 100;
    const etiqueta = opciones.etiqueta || "";
    const sufijo = opciones.sufijo != null ? opciones.sufijo : "%";
    const segmentos = opciones.segmentos || 36;
    const tamano = opciones.tamano || 120;

    const valNum = (valor != null && !isNaN(valor)) ? Number(valor) : null;
    const labelAria = `${etiqueta}: ${valNum != null ? valNum + sufijo : "Sin datos"}`;
    limpiarContenedor(cont, labelAria);
    if (!cont) return;

    const wrap = el("div", "hct-anillo-wrap");
    const caja = el("div", "hct-anillo-svg");
    caja.style.setProperty("--hct-tam", tamano + "px");

    const pct = valNum == null ? 0 : Math.min(1, Math.max(0, valNum / max));
    const activos = Math.round(pct * segmentos);
    // Medidas en cqw (% del lado): el anillo cabe siempre en el cuadrado
    const largo = Math.max(8 / tamano * 100, 9);
    const radio = 50 - largo / 2;
    const ancho = Math.min(largo * 0.45, (2 * Math.PI * radio / segmentos) * 0.55);
    for (let i = 0; i < segmentos; i++) {
      const seg = el("div", "hct-anillo-seg");
      seg.style.width = ancho + "cqw";
      seg.style.height = largo + "cqw";
      seg.style.marginLeft = (-ancho / 2) + "cqw";
      seg.style.marginTop = (-largo / 2) + "cqw";
      seg.style.borderRadius = (ancho / 2) + "cqw";
      seg.style.transform = `rotate(${(i * 360) / segmentos}deg) translateY(-${radio}cqw)`;
      if (valNum != null && i < activos) seg.style.background = colorMarca(segmentos > 1 ? i / (segmentos - 1) : 0);
      caja.appendChild(seg);
    }

    const centro = el("div", "hct-anillo-centro");
    centro.appendChild(el("div", "hct-anillo-val", {
      textContent: valNum == null ? "—" : Math.round(valNum * 10) / 10 + sufijo
    }));
    if (etiqueta) centro.appendChild(el("div", "hct-anillo-etiq", { textContent: etiqueta }));
    caja.appendChild(centro);
    wrap.appendChild(caja);
    cont.appendChild(wrap);
  }

  // 2. Progreso
  function progreso(cont, items, opciones = {}) {
    const labelAria = opciones.etiqueta || "Gráfico de barras de progreso";
    limpiarContenedor(cont, labelAria);
    if (!cont) return;

    if (!items || !items.length) {
      cont.appendChild(el("div", "hct-vacio", { textContent: "Sin datos" }));
      return;
    }

    const lista = el("div", "hct-progreso-lista");
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const val = (it.valor != null && !isNaN(it.valor)) ? Number(it.valor) : 0;
      const max = it.max != null ? it.max : 100;
      const pct = Math.min(100, Math.max(0, (val / max) * 100));

      const itemDiv = el("div", "hct-progreso-item");
      const infoDiv = el("div", "hct-progreso-info");
      infoDiv.appendChild(el("span", "", { textContent: it.etiqueta || "" }));
      infoDiv.appendChild(el("span", "", { textContent: it.texto || (Math.round(pct * 10) / 10 + "%") }));

      const pistaDiv = el("div", "hct-progreso-pista");
      pistaDiv.appendChild(el("div", "hct-progreso-relleno", { style: { width: pct + "%", backgroundSize: (pct > 0 ? 10000 / pct : 100) + "% 100%" } }));

      itemDiv.appendChild(infoDiv);
      itemDiv.appendChild(pistaDiv);
      lista.appendChild(itemDiv);
    }
    cont.appendChild(lista);
  }

  // 3. Bloques
  function bloques(cont, items, opciones = {}) {
    const numBloques = opciones.bloques || 24;
    const labelAria = opciones.etiqueta || "Gráfico de bloques";
    limpiarContenedor(cont, labelAria);
    if (!cont) return;

    if (!items || !items.length) {
      cont.appendChild(el("div", "hct-vacio", { textContent: "Sin datos" }));
      return;
    }

    const lista = el("div", "hct-bloques-lista");
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const val = (it.valor != null && !isNaN(it.valor)) ? Number(it.valor) : 0;
      const max = it.max != null ? it.max : 100;
      const pct = Math.min(1, Math.max(0, val / max));
      const activos = Math.round(pct * numBloques);

      const fila = el("div", "hct-bloques-fila");
      fila.appendChild(el("div", "hct-bloques-etiq", { textContent: it.etiqueta || "", title: it.etiqueta || "" }));

      const grid = el("div", "hct-bloques-grid");
      for (let b = 0; b < numBloques; b++) {
        const bloqueEl = el("div", "hct-bloque" + (b < activos ? " activo" : ""));
        if (b < activos) bloqueEl.style.setProperty("--bc", colorMarca(numBloques > 1 ? b / (numBloques - 1) : 0));
        grid.appendChild(bloqueEl);
      }
      fila.appendChild(grid);
      lista.appendChild(fila);
    }
    cont.appendChild(lista);
  }

  // Paso "bonito" (1, 2, 2.5, 5, 10 por potencia de 10) para n intervalos
  function pasoBonito(rango, n) {
    const crudo = rango / n;
    const mag = Math.pow(10, Math.floor(Math.log10(crudo)));
    const f = crudo / mag;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
  }

  // 4. Área
  function area(cont, series, opciones = {}) {
    const alto = opciones.alto != null ? opciones.alto : 220;
    const formatoY = opciones.formatoY || (v => Math.round(v * 100) / 100);
    const formatoX = opciones.formatoX || (v => v);
    const marcas = opciones.marcas || [];
    const desdeCero = opciones.desdeCero !== false;
    const labelAria = opciones.etiqueta || "Gráfico de área";

    limpiarContenedor(cont, labelAria);
    if (!cont) return;

    if (!series || !series.length || !series.some(s => s.puntos && s.puntos.length)) {
      cont.appendChild(el("div", "hct-vacio", { textContent: "Sin datos" }));
      return;
    }

    let minY = Infinity, maxY = -Infinity, maxPtsLen = 0;
    series.forEach(s => {
      const pts = s.puntos || [];
      if (pts.length > maxPtsLen) maxPtsLen = pts.length;
      pts.forEach(p => {
        if (p.y != null && !isNaN(p.y)) {
          if (p.y < minY) minY = p.y;
          if (p.y > maxY) maxY = p.y;
        }
      });
    });
    if (minY === Infinity) { minY = 0; maxY = 100; }
    if (desdeCero) minY = Math.min(0, minY);
    if (maxY <= minY) maxY = minY + 1;
    const paso = pasoBonito(maxY - minY, 4);
    const base = Math.floor(minY / paso) * paso;
    const techo = base + paso * Math.max(1, Math.ceil((maxY - base) / paso - 1e-9));
    const rangoY = techo - base;
    const yPct = v => 100 - ((v - base) / rangoY) * 100;

    const wrap = el("div", "hct-area-wrap");
    const contGraf = el("div", "hct-area-cont", { style: { height: alto + "px" } });
    const plot = el("div", "hct-area-plot");
    contGraf.appendChild(plot);

    // Guías horizontales con su valor
    const nGuias = Math.round(rangoY / paso);
    for (let i = 0; i <= nGuias; i++) {
      const v = base + paso * i;
      const guia = el("div", "hct-area-guia" + (i === 0 ? " cero" : ""), { style: { top: yPct(v) + "%" } });
      guia.appendChild(el("div", "hct-area-guia-val", { textContent: formatoY(v) }));
      plot.appendChild(guia);
    }

    const paleta = ["#00E5FF", "#8B5CF6", "#5aa8ff", "#22c55e"];
    const colorDe = (s, i) => s.color || paleta[i % paleta.length];
    const xPctDe = (i, n) => (n > 1 ? (i / (n - 1)) * 100 : 50);

    const coordsSeries = series.map(s => {
      const pts = s.puntos || [];
      return pts.map((p, i) => ({
        x: xPctDe(i, pts.length),
        y: yPct(p.y != null && !isNaN(p.y) ? p.y : base),
        p
      }));
    });

    // Marcas: índice numérico o valor x del punto
    const idxMarcas = new Set();
    const marcasRes = marcas.map(m => {
      const pts = series[0].puntos || [];
      let idx = typeof m.x === "number" ? m.x : pts.findIndex(p => p.x === m.x);
      if (idx < 0 || idx >= pts.length) idx = -1;
      return { m, idx };
    }).filter(r => r.idx >= 0);
    marcasRes.forEach(r => idxMarcas.add(r.idx));

    series.forEach((s, sIdx) => {
      const col = colorDe(s, sIdx);
      const co = coordsSeries[sIdx];
      if (!co.length) return;
      const pts1 = co.length === 1 ? [co[0], { ...co[0], x: co[0].x + 0.01 }] : co;
      const relleno = el("div", "hct-area-relleno");
      relleno.style.background = `linear-gradient(to bottom, color-mix(in srgb, ${col} 35%, transparent), color-mix(in srgb, ${col} 0%, transparent))`;
      relleno.style.clipPath = "polygon(" + pts1.map(c => `${c.x}% ${c.y}%`).join(", ") + `, ${pts1[pts1.length - 1].x}% 100%, ${pts1[0].x}% 100%)`;
      plot.appendChild(relleno);

      const linea = el("div", "hct-area-linea");
      linea.style.background = col;
      linea.style.clipPath = "polygon(" +
        pts1.map(c => `${c.x}% calc(${c.y}% - 1.5px)`).concat(
          pts1.slice().reverse().map(c => `${c.x}% calc(${c.y}% + 1.5px)`)).join(", ") + ")";
      plot.appendChild(linea);

      co.forEach((c, i) => {
        if (co.length > 24 && !idxMarcas.has(i)) return;
        const pto = el("div", "hct-area-pto", {
          style: { left: c.x + "%", top: c.y + "%" },
          title: `${s.nombre || "Serie"}: ${formatoX(c.p.x)}, ${formatoY(c.p.y)}`
        });
        pto.style.setProperty("--pc", col);
        plot.appendChild(pto);
      });
    });

    // Marcas verticales con etiqueta tipo píldora
    marcasRes.forEach(({ m, idx }) => {
      const c = coordsSeries[0][idx];
      const marca = el("div", "hct-area-marca", { style: { left: c.x + "%" } });
      if (m.etiqueta) {
        const et = el("div", "hct-area-marca-etiq", { textContent: m.etiqueta });
        if (c.x < 8) et.style.transform = "translateX(-12px)";
        else if (c.x > 92) et.style.transform = "translateX(calc(-100% + 12px))";
        marca.appendChild(et);
      }
      plot.appendChild(marca);
      plot.appendChild(el("div", "hct-area-marca-pto", { style: { left: c.x + "%", top: c.y + "%" } }));
    });

    wrap.appendChild(contGraf);

    // Etiquetas X (máx 6) en su posición real
    const ref = series.reduce((a, s) => ((s.puntos || []).length > (a.puntos || []).length ? s : a), series[0]).puntos || [];
    if (ref.length) {
      const etX = el("div", "hct-area-etiqs-x");
      const k = Math.min(6, ref.length);
      const usados = new Set();
      for (let j = 0; j < k; j++) {
        const i = k > 1 ? Math.round((j * (ref.length - 1)) / (k - 1)) : 0;
        if (usados.has(i)) continue;
        usados.add(i);
        const px = xPctDe(i, ref.length);
        const sp = el("span", "", { textContent: formatoX(ref[i].x), style: { left: px + "%" } });
        if (px === 0) sp.style.transform = "none";
        else if (px === 100) sp.style.transform = "translateX(-100%)";
        etX.appendChild(sp);
      }
      wrap.appendChild(etX);
    }

    if (series.length > 1) {
      const leyenda = el("div", "hct-area-leyenda");
      series.forEach((s, sIdx) => {
        const item = el("div", "hct-area-leyenda-item");
        item.appendChild(el("span", "hct-area-leyenda-box", { style: { background: colorDe(s, sIdx) } }));
        item.appendChild(el("span", "", { textContent: s.nombre || `Serie ${sIdx + 1}` }));
        leyenda.appendChild(item);
      });
      wrap.appendChild(leyenda);
    }

    cont.appendChild(wrap);
  }

  // 5. Anillos múltiples
  function anillos(cont, items, opciones = {}) {
    const labelAria = opciones.etiqueta || "Fila de anillos múltiples";
    limpiarContenedor(cont, labelAria);
    if (!cont) return;

    if (!items || !items.length) {
      cont.appendChild(el("div", "hct-vacio", { textContent: "Sin datos" }));
      return;
    }

    const wrap = el("div", "hct-anillos-wrap");
    const fila = el("div", "hct-anillos-fila");

    items.forEach(it => {
      const itemWrap = el("div", "hct-anillos-item");
      const subCont = el("div");
      anillo(subCont, {
        valor: it.valor,
        max: it.max != null ? it.max : 100,
        etiqueta: "",
        sufijo: it.sufijo || "%",
        tamano: 72,
        segmentos: 24
      });
      itemWrap.appendChild(subCont);
      if (it.etiqueta) {
        itemWrap.appendChild(el("span", "tenue", { style: { fontSize: "0.8em" }, textContent: it.etiqueta }));
      }
      fila.appendChild(itemWrap);
    });

    wrap.appendChild(fila);

    // Línea horizontal inferior con puntos bajo cada anillo
    const lineaWrap = el("div", "hct-anillos-linea-wrap");
    lineaWrap.appendChild(el("div", "hct-anillos-barra"));
    items.forEach((_, idx) => {
      const pctPos = ((idx + 0.5) / items.length) * 100;
      const punto = el("div", "hct-anillos-punto", { style: { left: pctPos + "%" } });
      lineaWrap.appendChild(punto);
    });
    wrap.appendChild(lineaWrap);

    cont.appendChild(wrap);
  }

  // Exponer funciones en window.HChart
  HChart.anillo = anillo;
  HChart.progreso = progreso;
  HChart.bloques = bloques;
  HChart.area = area;
  HChart.anillos = anillos;

})(window);
