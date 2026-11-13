;(function () {
  'use strict'

  // Tarjeta de estado de la red (KPIs, calidad y sonda)
  document.addEventListener('red-datos', function (e) {
    const detalle = e.detail || {}
    const resumen = detalle.resumen || {}
    const sonda = detalle.sonda || {}
    const vivo = detalle.vivo

    const cuerpo = document.querySelector('#red-estado-cuerpo')
    const sub = document.querySelector('#red-estado-sub')

    if (!cuerpo || !sub) return

    cuerpo.replaceChildren()
    sub.replaceChildren()

    // Fila con 4 KPIs
    const kpisDiv = document.createElement('div')
    kpisDiv.className = 'kpis'

    const checks = resumen.checks || {}
    const uptime = resumen.uptime || {}
    const keys = [
      { k: 'lan', label: 'Red local' },
      { k: 'wan', label: 'Internet' },
      { k: 'dns', label: 'DNS' }
    ]

    keys.forEach(function (item) {
      const kpi = document.createElement('div')
      kpi.className = 'kpi'

      // null = sin dato (HChart lo muestra como "—")
      const porc = uptime[item.k] !== undefined ? uptime[item.k] : null
      const contAnillo = document.createElement('div')
      contAnillo.className = 'kpi-anillo'

      if (window.HChart && typeof window.HChart.anillo === 'function') {
        window.HChart.anillo(contAnillo, { valor: porc, etiqueta: item.label })
      } else {
        const txtRespaldo = document.createElement('span')
        txtRespaldo.textContent = porc === null ? '—' : porc + '%'
        contAnillo.appendChild(txtRespaldo)
      }

      const titulo = document.createElement('div')
      titulo.className = 'kpi-titulo'
      titulo.textContent = item.label
      kpi.appendChild(titulo)
      kpi.appendChild(contAnillo)

      const texto = document.createElement('div')
      texto.className = 'kpi-texto'
      const check = checks[item.k]
      if (check && check.down_since) {
        const fechaStr = window.RedPanel && typeof window.RedPanel.fecha === 'function' 
          ? window.RedPanel.fecha(check.down_since) 
          : check.down_since
        texto.textContent = 'Caído desde ' + fechaStr
      } else {
        texto.textContent = 'En línea'
      }
      kpi.appendChild(texto)
      kpisDiv.appendChild(kpi)
    })

    // KPI 4: Equipos online
    const kpiEq = document.createElement('div')
    kpiEq.className = 'kpi'

    const dispositivos = resumen.devices || []
    const totalEq = dispositivos.length
    const onlineEq = dispositivos.filter(function (d) { return d.online }).length

    const cifra = document.createElement('div')
    cifra.className = 'cifra'
    cifra.textContent = String(onlineEq)
    kpiEq.appendChild(cifra)

    const tituloEq = document.createElement('div')
    tituloEq.className = 'kpi-titulo'
    tituloEq.textContent = 'Equipos'
    kpiEq.appendChild(tituloEq)

    const textoEq = document.createElement('div')
    textoEq.className = 'kpi-texto'
    textoEq.textContent = 'de ' + totalEq + ' equipos'
    kpiEq.appendChild(textoEq)

    kpisDiv.appendChild(kpiEq)
    cuerpo.appendChild(kpisDiv)

    // Calidad (progreso)
    const quality = resumen.quality || {}
    const itemsCalidad = []
    Object.keys(quality).forEach(function (targetKey) {
      const q = quality[targetKey]
      const label = targetKey === 'gateway' ? 'Router' : targetKey
      const loss = q && q.loss !== undefined && q.loss !== null ? q.loss : 0
      const valorProgreso = Math.max(0, 100 - loss)
      const avg = q && q.avg !== undefined && q.avg !== null ? Math.round(q.avg) : '—'
      const textoCalidad = avg + ' ms · ' + loss + ' % pérdida'

      itemsCalidad.push({
        etiqueta: label,
        valor: valorProgreso,
        texto: textoCalidad
      })
    })

    if (itemsCalidad.length > 0) {
      const contProgreso = document.createElement('div')
      contProgreso.className = 'red-calidad-progreso'
      if (window.HChart && typeof window.HChart.progreso === 'function') {
        window.HChart.progreso(contProgreso, itemsCalidad)
      } else {
        itemsCalidad.forEach(function (it) {
          const row = document.createElement('div')
          row.textContent = it.etiqueta + ': ' + it.texto
          contProgreso.appendChild(row)
        })
      }
      cuerpo.appendChild(contProgreso)
    }

    // Pie de estado (#red-estado-sub)
    const nombreSonda = sonda.nombre || 'Desconocida'
    const vistoSonda = sonda.visto || 0
    const haceStr = window.RedPanel && typeof window.RedPanel.hace === 'function'
      ? window.RedPanel.hace(vistoSonda)
      : String(vistoSonda)

    const textoSub = document.createElement('span')
    let textoSubStr = 'Sonda ' + nombreSonda + ' · ' + haceStr
    if (vivo === false) {
      textoSubStr += ' · sin datos recientes'
      textoSub.className = 'alerta'
    }
    textoSub.textContent = textoSubStr
    sub.appendChild(textoSub)

    const ipPublica = resumen.public_ip
    if (ipPublica) {
      const spanIp = document.createElement('span')
      spanIp.className = 'red-estado-ip'
      spanIp.textContent = ' · IP ' + ipPublica
      sub.appendChild(spanIp)
    }
  })
})();
