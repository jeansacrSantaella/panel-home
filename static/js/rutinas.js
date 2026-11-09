(function () {
  "use strict";

  // Elementos del DOM
  const secRutinas = document.getElementById("rutinas");
  const ulRutinas = document.getElementById("rutinas-lista");
  const btnNueva = document.getElementById("rutina-nueva");
  const dlgRutina = document.getElementById("dlg-rutina");
  const formRutina = document.getElementById("form-rutina");
  const h2Titulo = document.getElementById("rutina-titulo");
  const inputId = document.getElementById("rutina-id");
  const inputNombre = document.getElementById("rutina-nombre");
  const btnCapturar = document.getElementById("rutina-capturar");
  const ulFocos = document.getElementById("rutina-focos");
  const chkProgramar = document.getElementById("rutina-programar");
  const divHorario = document.getElementById("rutina-horario-campos");
  const inputHora = document.getElementById("rutina-hora");
  const pError = document.getElementById("rutina-error");
  const btnCancelar = document.getElementById("rutina-cancelar");

  let lucesData = [];
  let rutinasData = [];

  // Petición HTTP a la API
  function api(url, options = {}) {
    options.credentials = "same-origin";
    // el servidor solo acepta POST con JSON (protección contra peticiones forjadas): siempre mandamos cuerpo
    if (options.method === "POST" && options.body === undefined) options.body = {};
    if (options.body && typeof options.body === "object") {
      options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers);
      options.body = JSON.stringify(options.body);
    }
    return fetch(url, options);
  }

  // Notificación en pantalla
  function avisar(msg) {
    if (typeof window.mostrarAviso === "function") {
      window.mostrarAviso(msg);
    } else {
      const el = document.getElementById("luces-aviso");
      if (el) {
        el.textContent = msg;
        el.hidden = false;
        setTimeout(() => { el.hidden = true; }, 4000);
      }
    }
  }

  // Formato de texto para los días de programación
  function formatoDias(dias) {
    if (!dias || !dias.length) return "";
    const s = [...dias].sort((a, b) => a - b);
    if (s.length === 7) return "Diario";
    if (s.length === 5 && s.every((v, i) => v === i)) return "L–V";
    const letras = ["L", "M", "M", "J", "V", "S", "D"];
    return s.map((d) => letras[d]).join(" ");
  }

  // Cargar luces y rutinas desde el servidor
  async function cargarDatos() {
    try {
      const [resLuces, resRutinas] = await Promise.all([
        api("/api/luces").then((r) => r.json()),
        api("/api/rutinas").then((r) => r.json())
      ]);

      if (!resLuces.configurado) {
        if (secRutinas) secRutinas.hidden = true;
        return;
      }
      if (secRutinas) secRutinas.hidden = false;

      lucesData = resLuces.luces || [];
      rutinasData = resRutinas.rutinas || [];

      renderLista();
    } catch (e) {
      // Silenciar errores de red periódicos
    }
  }

  // Renderizar lista de rutinas
  function renderLista() {
    if (!ulRutinas) return;
    ulRutinas.textContent = "";

    if (!rutinasData.length) {
      const liVacio = document.createElement("li");
      liVacio.className = "tenue rutinas-vacio";
      liVacio.textContent = "Crea una rutina para prender o apagar varios focos con un clic o a una hora.";
      ulRutinas.appendChild(liVacio);
      return;
    }

    rutinasData.forEach((r) => {
      const li = document.createElement("li");
      li.className = "rutina" + (r.horario && !r.activa ? " pausada" : "");

      // Info
      const divInfo = document.createElement("div");
      divInfo.className = "rutina-info";
      const bNombre = document.createElement("b");
      bNombre.textContent = r.nombre;
      const spanTenue = document.createElement("span");
      spanTenue.className = "tenue";
      const resHorario = r.horario ? `${formatoDias(r.horario.dias)} ${r.horario.hora}` : "Manual";
      const cantFocos = (r.acciones || []).length;
      spanTenue.textContent = ` ${resHorario} · ${cantFocos} focos`;

      divInfo.appendChild(bNombre);
      divInfo.appendChild(spanTenue);
      li.appendChild(divInfo);

      // Botón Ejecutar
      const btnEjecutar = document.createElement("button");
      btnEjecutar.className = "rutina-ejecutar";
      btnEjecutar.setAttribute("aria-label", "Ejecutar " + r.nombre);
      btnEjecutar.textContent = "▶";
      btnEjecutar.addEventListener("click", async () => {
        li.classList.add("ocupada");
        try {
          const res = await api(`/api/rutinas/${r.id}/ejecutar`, { method: "POST" }).then((res) => res.json());
          let msg = "";
          if (res.ok === res.total) {
            msg = `«${r.nombre}» lista`;
          } else {
            const fallaronStr = (res.fallaron || []).join(", ");
            msg = `«${r.nombre}»: ${res.ok} de ${res.total} focos (no respondió: ${fallaronStr})`;
          }
          avisar(msg);
          document.dispatchEvent(new CustomEvent("rutina-ejecutada"));
        } catch (err) {
          avisar("Error al ejecutar rutina");
        } finally {
          li.classList.remove("ocupada");
        }
      });
      li.appendChild(btnEjecutar);

      // Switch activa (si tiene horario)
      if (r.horario) {
        const btnActiva = document.createElement("button");
        btnActiva.className = "rutina-activa";
        btnActiva.setAttribute("role", "switch");
        btnActiva.setAttribute("aria-checked", String(r.activa));
        btnActiva.setAttribute("aria-label", "Programación de " + r.nombre);
        btnActiva.addEventListener("click", async () => {
          try {
            await api(`/api/rutinas/${r.id}/activa`, {
              method: "POST",
              body: { activa: !r.activa }
            });
            cargarDatos();
          } catch (e) {}
        });
        li.appendChild(btnActiva);
      }

      // Editar
      const btnEditar = document.createElement("button");
      btnEditar.className = "rutina-editar";
      btnEditar.textContent = "Editar";
      btnEditar.addEventListener("click", () => abrirEditor(r));
      li.appendChild(btnEditar);

      // Borrar
      const btnBorrar = document.createElement("button");
      btnBorrar.className = "rutina-borrar";
      btnBorrar.textContent = "Borrar";
      btnBorrar.addEventListener("click", async () => {
        if (confirm(`¿Borrar la rutina «${r.nombre}»?`)) {
          try {
            await api(`/api/rutinas/${r.id}/borrar`, { method: "POST" });
            cargarDatos();
          } catch (e) {}
        }
      });
      li.appendChild(btnBorrar);

      ulRutinas.appendChild(li);
    });
  }

  // Abrir editor de rutina
  function abrirEditor(rutina) {
    if (pError) {
      pError.hidden = true;
      pError.textContent = "";
    }

    if (rutina) {
      h2Titulo.textContent = "Editar rutina";
      inputId.value = rutina.id;
      inputNombre.value = rutina.nombre;
    } else {
      h2Titulo.textContent = "Nueva rutina";
      inputId.value = "";
      inputNombre.value = "";
    }

    // Horario
    const horario = rutina ? rutina.horario : null;
    const diasInputs = formRutina.querySelectorAll(".rutina-dias input[type=checkbox]");
    if (horario) {
      chkProgramar.checked = true;
      divHorario.hidden = false;
      inputHora.value = horario.hora;
      diasInputs.forEach((cb) => {
        cb.checked = (horario.dias || []).includes(parseInt(cb.value, 10));
      });
    } else {
      chkProgramar.checked = false;
      divHorario.hidden = true;
      inputHora.value = "19:00";
      diasInputs.forEach((cb) => {
        const val = parseInt(cb.value, 10);
        cb.checked = val >= 0 && val <= 4;
      });
    }

    // Focos
    renderFocosForm(rutina);

    if (dlgRutina) {
      if (typeof dlgRutina.showModal === "function") dlgRutina.showModal();
      else dlgRutina.hidden = false;
    }
    if (inputNombre) inputNombre.focus();
  }

  // Renderizar controles de focos en el dialog
  function renderFocosForm(rutina) {
    if (!ulFocos) return;
    ulFocos.textContent = "";

    const acciones = rutina ? rutina.acciones || [] : [];

    lucesData.forEach((foco) => {
      const act = acciones.find((a) => a.id === foco.id);

      const li = document.createElement("li");
      li.className = "rutina-foco";
      li.dataset.focoId = foco.id;

      // Checkbox e inclusión
      const lblIncluir = document.createElement("label");
      lblIncluir.className = "rutina-incluir";
      const chkIncluir = document.createElement("input");
      chkIncluir.type = "checkbox";
      chkIncluir.className = "rf-incluir";
      chkIncluir.checked = !!act;
      const bNombre = document.createElement("b");
      bNombre.textContent = foco.nombre;
      lblIncluir.appendChild(chkIncluir);
      lblIncluir.appendChild(bNombre);
      li.appendChild(lblIncluir);

      // Acción
      const selAccion = document.createElement("select");
      selAccion.className = "rf-accion";
      const optEncender = document.createElement("option");
      optEncender.value = "encender";
      optEncender.textContent = "Encender";
      const optApagar = document.createElement("option");
      optApagar.value = "apagar";
      optApagar.textContent = "Apagar";
      selAccion.appendChild(optEncender);
      selAccion.appendChild(optApagar);
      if (act && act.encendida === false) selAccion.value = "apagar";
      li.appendChild(selAccion);

      // Ajustes
      const divAjustes = document.createElement("div");
      divAjustes.className = "rf-ajustes";

      const inBrillo = document.createElement("input");
      inBrillo.type = "range";
      inBrillo.className = "rf-brillo";
      inBrillo.min = "1";
      inBrillo.max = "100";
      inBrillo.setAttribute("aria-label", "Brillo");
      inBrillo.value = act && act.brillo !== undefined ? act.brillo : 100;
      divAjustes.appendChild(inBrillo);

      let selModo = null, inTemp = null, inColor = null;

      if (foco.tiene_color || foco.tiene_temperatura) {
        selModo = document.createElement("select");
        selModo.className = "rf-modo";
        const optBlanco = document.createElement("option");
        optBlanco.value = "blanco";
        optBlanco.textContent = "Blanco";
        selModo.appendChild(optBlanco);
        if (foco.tiene_color) {
          const optColor = document.createElement("option");
          optColor.value = "color";
          optColor.textContent = "Color";
          selModo.appendChild(optColor);
        }

        inTemp = document.createElement("input");
        inTemp.type = "range";
        inTemp.className = "rf-temp";
        inTemp.min = "0";
        inTemp.max = "100";
        inTemp.setAttribute("aria-label", "Blanco cálido a frío");
        inTemp.value = act && act.temperatura !== undefined ? act.temperatura : 50;

        inColor = document.createElement("input");
        inColor.type = "color";
        inColor.className = "rf-color";
        inColor.value = act && act.color ? act.color : "#ffffff";

        if (act && act.color && foco.tiene_color) {
          selModo.value = "color";
        } else {
          selModo.value = "blanco";
        }

        divAjustes.appendChild(selModo);
        divAjustes.appendChild(inTemp);
        divAjustes.appendChild(inColor);
      }

      li.appendChild(divAjustes);

      function actualizarVisibilidad() {
        const visible = chkIncluir.checked && selAccion.value === "encender";
        divAjustes.hidden = !visible;
        if (selModo && visible) {
          const esColor = selModo.value === "color";
          inTemp.hidden = esColor;
          inColor.hidden = !esColor;
        }
      }

      chkIncluir.addEventListener("change", actualizarVisibilidad);
      selAccion.addEventListener("change", actualizarVisibilidad);
      if (selModo) selModo.addEventListener("change", actualizarVisibilidad);

      actualizarVisibilidad();
      ulFocos.appendChild(li);
    });
  }

  // Capturar estado actual de luces en línea
  if (btnCapturar) {
    btnCapturar.addEventListener("click", () => {
      lucesData.forEach((foco) => {
        if (!foco.en_linea) return;
        const li = ulFocos.querySelector(`[data-foco-id="${foco.id}"]`);
        if (!li) return;

        const chkIncluir = li.querySelector(".rf-incluir");
        const selAccion = li.querySelector(".rf-accion");
        const inBrillo = li.querySelector(".rf-brillo");
        const selModo = li.querySelector(".rf-modo");
        const inTemp = li.querySelector(".rf-temp");
        const inColor = li.querySelector(".rf-color");

        chkIncluir.checked = true;
        selAccion.value = foco.encendida ? "encender" : "apagar";
        if (inBrillo && foco.brillo !== undefined) inBrillo.value = foco.brillo;

        if (selModo) {
          if (foco.modo === "colour" && foco.tiene_color) {
            selModo.value = "color";
          } else {
            selModo.value = "blanco";
          }
        }
        if (inTemp && foco.temperatura !== undefined) inTemp.value = foco.temperatura;
        if (inColor && foco.color) inColor.value = foco.color;

        chkIncluir.dispatchEvent(new Event("change"));
      });
    });
  }

  // Eventos UI del diálogo
  if (chkProgramar) {
    chkProgramar.addEventListener("change", () => {
      divHorario.hidden = !chkProgramar.checked;
    });
  }

  if (btnCancelar) {
    btnCancelar.addEventListener("click", () => {
      if (dlgRutina) {
        if (typeof dlgRutina.close === "function") dlgRutina.close();
        else dlgRutina.hidden = true;
      }
    });
  }

  if (btnNueva) {
    btnNueva.addEventListener("click", () => abrirEditor(null));
  }

  // Guardar rutina
  if (formRutina) {
    formRutina.addEventListener("submit", async (e) => {
      e.preventDefault();
      const nombre = inputNombre.value.trim();
      if (!nombre) {
        pError.textContent = "Ponle un nombre";
        pError.hidden = false;
        return;
      }

      const acciones = [];
      const lisFoco = ulFocos.querySelectorAll(".rutina-foco");
      lisFoco.forEach((li) => {
        const id = li.dataset.focoId;
        const inc = li.querySelector(".rf-incluir").checked;
        if (!inc) return;

        const accionVal = li.querySelector(".rf-accion").value;
        const encendida = accionVal === "encender";
        const acc = { id, encendida };

        if (encendida) {
          const inBrillo = li.querySelector(".rf-brillo");
          if (inBrillo) acc.brillo = parseInt(inBrillo.value, 10);

          const selModo = li.querySelector(".rf-modo");
          if (selModo && selModo.value === "color") {
            const inColor = li.querySelector(".rf-color");
            if (inColor) acc.color = inColor.value;
          } else {
            const inTemp = li.querySelector(".rf-temp");
            if (inTemp) acc.temperatura = parseInt(inTemp.value, 10);
          }
        }
        acciones.push(acc);
      });

      if (!acciones.length) {
        pError.textContent = "Elige al menos un foco";
        pError.hidden = false;
        return;
      }

      let horario = null;
      if (chkProgramar.checked) {
        const hora = inputHora.value;
        const dias = [];
        const diasInputs = formRutina.querySelectorAll(".rutina-dias input[type=checkbox]");
        diasInputs.forEach((cb) => {
          if (cb.checked) dias.push(parseInt(cb.value, 10));
        });
        if (!dias.length) {
          pError.textContent = "Elige al menos un día";
          pError.hidden = false;
          return;
        }
        horario = { hora, dias };
      }

      const body = { nombre, acciones, horario };
      if (inputId.value) body.id = parseInt(inputId.value, 10);

      try {
        const res = await api("/api/rutinas", { method: "POST", body });
        if (res.ok) {
          if (dlgRutina) {
            if (typeof dlgRutina.close === "function") dlgRutina.close();
            else dlgRutina.hidden = true;
          }
          cargarDatos();
        } else {
          const errData = await res.json();
          pError.textContent = errData.error || "Error al guardar rutina";
          pError.hidden = false;
        }
      } catch (err) {
        pError.textContent = "Error de red al guardar";
        pError.hidden = false;
      }
    });
  }

  // Inicialización y eventos externos
  document.addEventListener("luces", cargarDatos);
  cargarDatos();
  setInterval(cargarDatos, 30000);
})();
