# Diseño del tablero (PleyadesHome)

Distribución tipo "dashboard" de referencia (barra lateral, barra superior con ruta, tarjetas de indicadores con
anillos segmentados, barras de progreso con degradado, gráfica de área con puntos etiquetados, lista de actividad),
**con los colores de la familia Astreo** (no los de la referencia): obsidiana `#0B0F17`, degradado
`--marca-degradado` (violeta `#8B5CF6` → azul `#5aa8ff` → cian `#00E5FF`) y los tokens de `panel.css`/`orion.css`
(`--fondo --superficie --tarjeta --texto --tenue --borde --ok --alerta --mal --info`). Funciona en tema claro y oscuro.

## Estructura (`static/css/tablero.css`)

| Ancho | Navegación |
|---|---|
| ≥ 1024 px | Barra lateral fija de 232 px (`nav#menu-principal`): marca arriba, secciones con ícono + nombre en mayúsculas pequeñas y espaciadas, la activa con barra izquierda e ícono en degradado; abajo el grupo **SERVICIOS** con un punto de estado por servicio (`#lateral-servicios`). El botón ☰ la contrae a solo íconos (72 px, `html.lateral-mini`, recordado en `localStorage`). |
| 760–1023 px | Barra lateral de solo íconos (72 px) con el nombre como `title`. |
| < 760 px | Menú deslizante del celular (como hoy, `menu.js`). |

Barra superior (sobre el contenido, no sobre la lateral): ☰, **ruta** `PANEL / RESUMEN` (`#ruta`, mayúsculas
pequeñas; la sección sale del evento `pestana`), buscador en píldora (`#buscar-global`: Enter → abre Red y filtra
equipos), y a la derecha IP pública, "actualizado", 🔔, tema y cuenta (avatar redondo).

## Componentes CSS (clases genéricas, úsalas en vez de inventar)

| Clase | Qué es |
|---|---|
| `.tarjeta` | Panel plano: fondo `--tarjeta`, borde 1 px `--borde`, radio 14 px, sin sombra pesada; en oscuro un brillo interior muy leve. |
| `.tarjeta h2` | Título en mayúsculas pequeñas, `letter-spacing: .08em`, color con el degradado de marca (texto con `background-clip`). Un `<small>`/`.tenue` al lado va en tono tenue. |
| `.kpis` / `.kpi` | Fila de tarjetas de indicador: anillo arriba, `.kpi-titulo` (mayúsculas, color de acento) y `.kpi-texto` (tenue, 2 líneas máx). |
| `.cifra` | Número grande (ej. "64%") con el degradado de marca. |
| `.progreso` | Lista de barras finas (6 px) con relleno en degradado y etiqueta encima. |
| `.tabla` | Tabla compacta: encabezado en mayúsculas pequeñas tenues, filas con separador 1 px, hover suave; dentro de `.red-tabla-envoltura` con desplazamiento horizontal en el celular. |
| `.paginas` | Paginador: "‹ 1 / 4 ›" con botones `.boton` pequeños. |
| `.actividad` | Lista tipo "Activities": cada `<li>` con punto de color por nivel (`data-nivel="alto|medio|bajo|info"`), título, detalle tenue y hora a la derecha. |
| `.barra-herramientas` | Fila de filtros/inputs que se envuelve en el celular. |
| `.punto` + `data-estado="ok|alerta|mal|nada"` | Punto de estado de 8 px. |

## Componentes de gráfica (`static/js/hchart-tablero.js`, extiende `window.HChart`; solo HTML/CSS, sin canvas ni SVG)

```js
HChart.anillo(cont, {valor, max = 100, etiqueta = "", sufijo = "%", segmentos = 36, tamano = 120})
  // anillo de segmentos (como los indicadores de la referencia); los encendidos llevan el degradado de marca,
  // los apagados `--borde`; número grande al centro y etiqueta debajo. valor null -> "—".
HChart.progreso(cont, items /* [{etiqueta, valor, max = 100, texto?}] */)
  // barras finas con relleno en degradado; `texto` opcional a la derecha (si no, el %).
HChart.bloques(cont, items /* [{etiqueta, valor, max = 100}] */, {bloques = 24})
  // barras horizontales hechas de bloques (como el "ecualizador" de la referencia), encendidos en degradado.
HChart.area(cont, series /* [{nombre, puntos: [{x, y}], color?}] */, {marcas = [/* {x, etiqueta} */], formatoY, formatoX, alto = 220})
  // gráfica de área/línea con relleno translúcido (clip-path polygon), ejes con líneas guía tenues,
  // marcas verticales con etiqueta en puntos elegidos ("Data 01"), leyenda si hay más de una serie.
HChart.anillos(cont, items /* [{valor, max, etiqueta}] */)
  // fila de anillos pequeños unidos por una línea de tiempo con puntos (fila inferior de la referencia).
```
Cada función limpia `cont`, respeta `prefers-reduced-motion` y deja texto accesible (`role="img"` + `aria-label`).

## Pestaña Red (`static/js/red/`)

`nucleo.js` define `window.RedPanel` y despacha `document` → `red-datos` con `{resumen, sonda, vivo}` (la forma de
`/api/summary` de NetWatch en `resumen`). Cada tarjeta es un script: `estado.js`, `equipos.js`, `escaner.js`,
`velocidad.js`, `eventos.js`.

## Piel de vidrio (`static/css/vidrio.css`, se carga al final)

Segunda referencia del dueño (panel de casa tipo tableta de pared): paneles de **vidrio translúcido** sobre el cielo
de Astreo (obsidiana + nebulosa violeta/cian), esquinas de 22 px, borde de 1 px con brillo arriba, desenfoque
`backdrop-filter: blur(18px) saturate(1.3)`, sombras suaves; botones y mosaicos redondeados. Aplica a `.tarjeta`,
barra superior, lateral, chips y diálogos en TODAS las pestañas. Tokens: `--vidrio`, `--vidrio-borde`,
`--vidrio-brillo`, `--vidrio-desenfoque` (claro y oscuro). En < 760 px y con `prefers-reduced-transparency: reduce`
→ sin `backdrop-filter`, fondo sólido semitransparente.

## Pestaña Inicio (`#pestana-inicio`, la de entrada)

Rejilla tipo tableta horizontal (en celular se apila en este mismo orden):

```
[ chips de estado (franja #chips) ............................ ][ reloj #inicio-reloj ]
[ cámara #inicio-camara (video + selector) ][ clima #inicio-clima ][ habitación #inicio-hab ]
[ habitaciones #inicio-habitaciones ][ atajos #inicio-atajos ][ agenda #inicio-agenda ........ ]
[ dock inferior #inicio-dock: luces encendidas · cámaras · internet · clima · rutina ......... ]
```

- `static/js/inicio/nucleo.js` → `window.InicioPanel`: `api`, `el`, `hace`, `iconoClima(nombre) -> SVG string fijo`
  y eventos document: `inicio-luces` `{luces (con habitacion), habitaciones (resumen), rutinas}` cada 10 s,
  `inicio-clima` (datos de `/api/clima`) cada 10 min; además se reutiliza el evento `panel` de app.js (cámaras, red,
  ip, salud). Solo pide datos con la pestaña Inicio abierta. `InicioPanel.recargarLuces()`.
- API: `GET /api/luces` (cada foco trae `habitacion`), `GET /api/luces/habitaciones` → `{habitaciones: resumen, nombres}`,
  `POST /api/luces/<id>/habitacion {habitacion}`, `POST /api/luces/habitacion {habitacion, encendida?|brillo?|temperatura?|color?}`
  → `{habitacion, total, ok, fallaron}`, `GET /api/rutinas`, `POST /api/rutinas/<id>/ejecutar`, `POST /api/luces/todas {encendida}`,
  `GET /api/clima` → `{configurado, ciudad, actualizado, error, actual: {temp, sensacion, humedad, codigo, descripcion, icono, es_dia},
  hoy: {max, min}, dias: [{fecha, dia, codigo, descripcion, icono, max, min}]}`.
- Tarjetas (un script cada una en `static/js/inicio/`): `reloj.js` (HH:MM grande + segundos pequeños + fecha larga),
  `camara.js` (una sola cámara a la vez con `stream.html` de go2rtc como `app.js`; botones con el nombre de cada cámara
  a la derecha, la activa resaltada; quita el iframe al salir de Inicio para liberar la sesión de video), `clima.js`,
  `habitacion.js` (arco grande tipo termostato: brillo promedio de la habitación elegida, − / + de 10 en 10, botones
  encender/apagar/"Noche" (primera rutina cuyo nombre contenga "noche") y selector de habitación), `habitaciones.js`
  (lista: ícono por nombre, nombre, insignia con focos encendidos, toque = encender/apagar la habitación), `atajos.js`
  (mosaicos de focos y rutinas; encendido = mosaico claro), `agenda.js` (Hoy / Ayer con `/api/eventos?desde=` y el
  mes con los días que tienen capturas `/api/capturas` → clic abre `#capturas` con esa fecha), `dock.js`.
