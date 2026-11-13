/* Esqueletos de carga: bloques grises con brillo mientras llegan los datos. */
(function () {
  "use strict";

  // Crea un div con clase y los hijos dados (aplana arrays).
  const d = (clase, ...hijos) => {
    const e = document.createElement("div");
    e.className = clase;
    hijos.flat().forEach((h) => e.appendChild(h));
    return e;
  };
  const rep = (n, f) => Array.from({ length: n }, (_, i) => f(i));
  const estilo = (e, css) => (Object.assign(e.style, css), e);
  const celdas = (k) => rep(k, () => d("esq-celda"));
  const col = (...h) => d("esq-col", ...h);
  const C = () => d("esq-c");
  const B = () => d("esq-b");

  // Cada forma: [cantidad por defecto, generador de los hijos]
  const FORMAS = {
    kpis: [4, (n) => rep(n, () => d("esq-b", C(), estilo(col(celdas(2)), { flex: "1" })))],
    anillo: [0, () => [C(), B(), d("esq-celda")]],
    lista: [5, (n) => rep(n, () => d("esq-fila", C(), col(celdas(2))))],
    tabla: [6, (n) => [d("esq-fila", rep(5, B)), ...rep(n, () => d("esq-fila", celdas(5)))]],
    mosaicos: [6, (n) => rep(n, B)],
    grafica: [0, () => {
      const bloque = estilo(B(), { position: "relative", overflow: "hidden" });
      [20, 40, 60, 80].forEach((p) => bloque.appendChild(estilo(d(""), {
        position: "absolute", left: "0", right: "0", top: p + "%", height: "1px",
        background: "color-mix(in srgb, var(--texto) 10%, transparent)",
      })));
      // Onda tenue recortada con clip-path
      bloque.appendChild(estilo(B(), {
        position: "absolute", left: "0", top: "0", opacity: ".6",
        clipPath: "polygon(0 60%, 15% 45%, 30% 55%, 50% 35%, 70% 50%, 85% 30%, 100% 45%, 100% 100%, 0 100%)",
      }));
      return [bloque];
    }],
    video: [1, (n) => rep(n, () => estilo(d("esq-b", C()), {
      aspectRatio: "16 / 9", display: "flex", alignItems: "center", justifyContent: "center",
    }))],
    texto: [3, (n) => rep(n, B)],
    agenda: [0, () => [col(celdas(5)), d("esq-agenda-grilla", rep(35, B))]],
    pildoras: [4, (n) => rep(n, () => d("esq-b", C()))],
  };

  // Quita solo los esqueletos y el aria-busy.
  function quitar(cont) {
    cont.querySelectorAll(":scope > .esq").forEach((e) => e.remove());
    cont.removeAttribute("aria-busy");
  }

  // Pinta un esqueleto dentro del contenedor.
  function pintar(cont, forma, n) {
    quitar(cont);
    const [defecto, gen] = FORMAS[forma] || FORMAS.texto;
    const nodo = d("esq esq-" + forma, gen(n || defecto));
    nodo.setAttribute("aria-hidden", "true");
    // La cuadricula de video anula el 16:9 del contenedor; cada bloque lo lleva.
    if (forma === "video") {
      estilo(nodo, { aspectRatio: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px" });
    }
    cont.appendChild(nodo);
    cont.setAttribute("aria-busy", "true");
  }

  // Pinta solo si la promesa tarda mas de 300 ms; quita al terminar.
  function mientras(cont, promesa, forma, n) {
    const t = setTimeout(() => pintar(cont, forma, n), 300);
    const fin = () => {
      clearTimeout(t);
      quitar(cont);
    };
    Promise.resolve(promesa).then(fin, fin);
    return promesa;
  }

  // Pinta el esqueleto de un contenedor y lo quita cuando llega contenido real.
  function automatico(cont) {
    if (cont.children.length) return;
    const n = parseInt(cont.dataset.esqueletoN, 10) || undefined;
    pintar(cont, cont.dataset.esqueleto, n);
    const obs = new MutationObserver((muts) => {
      const llego = muts.some((m) => [...m.addedNodes].some((x) => x.nodeType !== 1 || !x.classList.contains("esq")));
      if (llego) {
        obs.disconnect();
        quitar(cont);
      }
    });
    obs.observe(cont, { childList: true });
  }

  function iniciar() {
    document.querySelectorAll("[data-esqueleto]").forEach(automatico);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();

  window.Esqueleto = { pintar, quitar, mientras };
})();
