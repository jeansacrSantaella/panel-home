/* Clases CSS usadas:
   - inicio-atajos-mosaico: botón individual de acceso directo.
   - encendido: modificador para mosaicos de focos encendidos.
   - inicio-atajos-icono: contenedor del ícono SVG.
   - inicio-atajos-nombre: etiqueta con el nombre del acceso directo.
   - inicio-atajos-marca: indicador breve con texto (ej. "4/4").
   - inicio-atajos-ver: mosaico fijo al final ("Ver todo").
   - ocupada: estado de carga mientras se ejecuta una acción.
*/
(function () {
  "use strict";

  const SVG_BOMBILLA = '<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3Z"/>';
  const SVG_RUTINA = '<circle cx="12" cy="12" r="9"/><path d="M10 8.5v7l5.5-3.5Z"/>';
  const SVG_VER = '<path d="M5 12h14M13 6l6 6-6 6"/>';

  function crearSvg(pathHtml, ariaHidden = true) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    if (ariaHidden) {
      svg.setAttribute("aria-hidden", "true");
    }
    svg.setAttribute("focusable", "false");
    svg.innerHTML = pathHtml;
    return svg;
  }

  function pintar(datos) {
    const contenedor = document.querySelector("#inicio-atajos .inicio-mosaicos");
    if (!contenedor) return;

    contenedor.textContent = "";

    const luces = (datos && datos.luces) || [];
    const rutinas = (datos && datos.rutinas) || [];

    // Combinar elementos limitando a un total de 8 antes de añadir "Ver todo"
    const elementos = [];

    luces.forEach(l => {
      elementos.push({ tipo: "foco", datos: l });
    });

    rutinas.forEach(r => {
      elementos.push({ tipo: "rutina", datos: r });
    });

    const recortados = elementos.slice(0, 8);

    recortados.forEach(item => {
      if (item.tipo === "foco") {
        const foco = item.datos;
        const btn = InicioPanel.el("button", "inicio-atajos-mosaico", {
          type: "button",
          title: foco.nombre || foco.id
        });

        const encendida = Boolean(foco.encendida && foco.en_linea);
        if (encendida) {
          btn.classList.add("encendido");
        }
        btn.setAttribute("aria-pressed", encendida ? "true" : "false");

        if (foco.en_linea === false) {
          btn.disabled = true;
          btn.title = "Sin respuesta";
        }

        const iconoSpan = InicioPanel.el("span", "inicio-atajos-icono");
        iconoSpan.appendChild(crearSvg(SVG_BOMBILLA));

        const nombreSpan = InicioPanel.el("span", "inicio-atajos-nombre", {
          textContent: foco.nombre || foco.id
        });

        btn.append(iconoSpan, nombreSpan);

        btn.addEventListener("click", async () => {
          if (btn.classList.contains("ocupada")) return;
          btn.classList.add("ocupada");
          try {
            await InicioPanel.api("/api/luces/" + encodeURIComponent(foco.id), {
              method: "POST",
              body: { encendida: !foco.encendida }
            });
            InicioPanel.recargarLuces();
          } catch (e) {
            btn.title = e.message;
            setTimeout(() => {
              btn.title = foco.nombre || foco.id;
            }, 3000);
          } finally {
            btn.classList.remove("ocupada");
          }
        });

        contenedor.appendChild(btn);

      } else if (item.tipo === "rutina") {
        const rutina = item.datos;
        const btn = InicioPanel.el("button", "inicio-atajos-mosaico", {
          type: "button",
          title: rutina.nombre || rutina.id
        });
        btn.setAttribute("aria-label", rutina.nombre || rutina.id);

        const iconoSpan = InicioPanel.el("span", "inicio-atajos-icono");
        iconoSpan.appendChild(crearSvg(SVG_RUTINA));

        const nombreSpan = InicioPanel.el("span", "inicio-atajos-nombre", {
          textContent: rutina.nombre || rutina.id
        });

        const marcaSpan = InicioPanel.el("span", "inicio-atajos-marca");

        btn.append(iconoSpan, nombreSpan, marcaSpan);

        btn.addEventListener("click", async () => {
          if (btn.classList.contains("ocupada")) return;
          btn.classList.add("ocupada");
          try {
            const res = await InicioPanel.api("/api/rutinas/" + encodeURIComponent(rutina.id) + "/ejecutar", {
              method: "POST"
            });
            if (res && res.total !== undefined && res.ok !== undefined) {
              marcaSpan.textContent = res.ok + "/" + res.total;
              setTimeout(() => {
                marcaSpan.textContent = "";
              }, 2000);
            }
            InicioPanel.recargarLuces();
          } catch (e) {
            btn.title = e.message;
            setTimeout(() => {
              btn.title = rutina.nombre || rutina.id;
            }, 3000);
          } finally {
            btn.classList.remove("ocupada");
          }
        });

        contenedor.appendChild(btn);
      }
    });

    // Siempre añadir el mosaico "Ver todo" al final
    const btnVerTodo = InicioPanel.el("button", "inicio-atajos-mosaico inicio-atajos-ver", {
      type: "button",
      title: "Ver todo"
    });

    const iconoVer = InicioPanel.el("span", "inicio-atajos-icono");
    iconoVer.appendChild(crearSvg(SVG_VER));

    const nombreVer = InicioPanel.el("span", "inicio-atajos-nombre", {
      textContent: "Ver todo"
    });

    btnVerTodo.append(iconoVer, nombreVer);
    btnVerTodo.addEventListener("click", () => {
      location.hash = "#luces";
    });

    contenedor.appendChild(btnVerTodo);
  }

  document.addEventListener("inicio-luces", e => pintar(e.detail));
})();
