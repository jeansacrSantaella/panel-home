;(function () {
  'use strict'

  // Tarjeta de velocidad de la red (gráfica de área y sub con última medición)
  document.addEventListener('red-datos', function (e) {
    const detalle = e.detail || {}
    const resumen = detalle.resumen || {}

    const graficaCont = document.querySelector('#red-velocidad-grafica')
    const sub = document.querySelector('#red-velocidad-sub')

    if (!graficaCont || !sub) return

    graficaCont.replaceChildren()
    sub.replaceChildren()

    const speed = resumen.speed || []

    if (speed.length === 0) {
      const sinDatos = document.createElement('div')
      sinDatos.className = 'tenue'
      sinDatos.textContent = 'Aún no hay pruebas de velocidad (cada hora)'
      graficaCont.appendChild(sinDatos)
      return
    }

    // Preparar series para HChart.area
    const puntosDown = []
    const puntosUp = []

    let maxDown = -Infinity
    let minDown = Infinity
    let tsMaxDown = null
    let tsMinDown = null

    speed.forEach(function (item) {
      const ts = item.ts
      const down = item.down
      const up = item.up

      puntosDown.push({ x: ts, y: down })
      puntosUp.push({ x: ts, y: up })

      if (down > maxDown) {
        maxDown = down
        tsMaxDown = ts
      }
      if (down < minDown) {
        minDown = down
        tsMinDown = ts
      }
    })

    const series = [
      { nombre: 'Bajada', puntos: puntosDown },
      { nombre: 'Subida', puntos: puntosUp }
    ]

    const marcas = []
    if (tsMaxDown !== null) {
      marcas.push({ x: tsMaxDown, etiqueta: 'Máx ' + Math.round(maxDown) })
    }
    if (tsMinDown !== null && tsMinDown !== tsMaxDown) {
      marcas.push({ x: tsMinDown, etiqueta: 'Mín ' + Math.round(minDown) })
    }

    const formatoX = function (ts) {
      const d = new Date(ts * 1000)
      const h = String(d.getHours()).padStart(2, '0')
      const m = String(d.getMinutes()).padStart(2, '0')
      return h + ':' + m
    }

    const formatoY = function (val) {
      return Math.round(val) + ' Mbps'
    }

    if (window.HChart && typeof window.HChart.area === 'function') {
      window.HChart.area(graficaCont, series, {
        marcas: marcas,
        formatoY: formatoY,
        formatoX: formatoX,
        alto: 150
      })
    } else {
      const respaldo = document.createElement('div')
      respaldo.textContent = 'Gráfica de velocidad (' + speed.length + ' puntos)'
      graficaCont.appendChild(respaldo)
    }

    // Sub de velocidad (#red-velocidad-sub)
    const ultimo = speed[speed.length - 1]
    const uDown = Math.round(ultimo.down)
    const uUp = Math.round(ultimo.up)

    let textoSubStr = '↓ ' + uDown + ' · ↑ ' + uUp + ' Mbps'

    const contracted = resumen.contracted || {}
    if (contracted.down && contracted.down > 0) {
      const cDown = Math.round(contracted.down)
      const cUp = contracted.up ? Math.round(contracted.up) : 0
      textoSubStr += ' · plan ' + cDown + '/' + cUp
    }

    const spanSub = document.createElement('span')
    spanSub.textContent = textoSubStr
    sub.appendChild(spanSub)
  })
})();
