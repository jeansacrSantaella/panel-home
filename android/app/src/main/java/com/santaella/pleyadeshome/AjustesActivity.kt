package com.santaella.pleyadeshome

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class AjustesActivity : Activity() {

    private lateinit var gestorServidores: Servidores
    private lateinit var contenedorFilas: LinearLayout
    private lateinit var btnBuscar: Button
    private lateinit var btnProbar: Button
    
    // Mapa temporal para guardar el estado de los puntos de conexión (url -> booleano o null)
    private val estadosSondeo = mutableMapOf<String, Boolean?>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Color de barra de estado
        window.statusBarColor = Color.parseColor("#0B0F17")
        
        gestorServidores = Servidores(this)

        val dp = resources.displayMetrics.density
        val paddingPx = (20 * dp).toInt()

        // Contenedor principal con Scroll
        val scroll = ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#0B0F17"))
            isFillViewport = true
        }

        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(paddingPx, paddingPx, paddingPx, paddingPx)
        }

        // 1. Título y subtítulo
        val txtTitulo = TextView(this).apply {
            text = "Servidores"
            textSize = 24f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#E6ECF7"))
        }
        raiz.addView(txtTitulo)

        val txtSub = TextView(this).apply {
            text = "Elige a qué dirección se conecta la app. Si la casa cambia de IP, edítala aquí o búscala en la red."
            textSize = 14f
            setTextColor(Color.parseColor("#8A94A8"))
            setPadding(0, (6 * dp).toInt(), 0, (16 * dp).toInt())
        }
        raiz.addView(txtSub)

        // 2. Contenedor de filas de servidores
        contenedorFilas = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        raiz.addView(contenedorFilas)

        // 3. Botones principales
        val btnAgregar = Button(this).apply {
            isAllCaps = false
            text = "＋ Agregar dirección"
            setTextColor(Color.parseColor("#0B0F17"))
            setTypeface(null, Typeface.BOLD)
            setCapsAll(false)
            elevation = 0f
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 14f * dp
                orientation = GradientDrawable.Orientation.LEFT_RIGHT
                colors = intArrayOf(
                    Color.parseColor("#8B5CF6"),
                    Color.parseColor("#5AA8FF"),
                    Color.parseColor("#00E5FF")
                )
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                (48 * dp).toInt()
            ).apply {
                topMargin = (10 * dp).toInt()
            }
            setOnClickListener {
                mostrarDialogoEditar(null)
            }
        }
        raiz.addView(btnAgregar)

        btnBuscar = Button(this).apply {
            isAllCaps = false
            text = "Buscar en la red"
            setTextColor(Color.parseColor("#00E5FF"))
            setCapsAll(false)
            elevation = 0f
            background = crearFondoSuperficie(dp, bordeCian = true)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                (48 * dp).toInt()
            ).apply {
                topMargin = (10 * dp).toInt()
            }
            setOnClickListener {
                ejecutarBusquedaEnRed()
            }
        }
        raiz.addView(btnBuscar)

        btnProbar = Button(this).apply {
            isAllCaps = false
            text = "Probar conexión"
            setTextColor(Color.parseColor("#00E5FF"))
            setCapsAll(false)
            elevation = 0f
            background = crearFondoSuperficie(dp, bordeCian = true)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                (48 * dp).toInt()
            ).apply {
                topMargin = (10 * dp).toInt()
            }
            setOnClickListener {
                ejecutarProbarConexion()
            }
        }
        raiz.addView(btnProbar)

        // 4. Pie centrado
        val txtPie = TextView(this).apply {
            text = "PleyadesHome · familia Astreo · Santaella"
            textSize = 12f
            setTextColor(Color.parseColor("#8A94A8"))
            gravity = Gravity.CENTER
            setPadding(0, (30 * dp).toInt(), 0, (10 * dp).toInt())
        }
        raiz.addView(txtPie)

        scroll.addView(raiz)
        setContentView(scroll)

        refrescarFilas()

        // Si viene el extra de primera vez, abrir diálogo de agregar
        if (intent.getBooleanExtra("primera_vez", false)) {
            mostrarDialogoEditar(null)
        }
    }

    private fun crearFondoSuperficie(dp: Float, bordeCian: Boolean): GradientDrawable {
        return GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = 16f * dp
            setColor(Color.parseColor("#121A2B"))
            if (bordeCian) {
                setStroke((1 * dp).toInt(), Color.parseColor("#00E5FF"))
            } else {
                setStroke((1 * dp).toInt(), Color.parseColor("#1F2A40"))
            }
        }
    }

    private fun refrescarFilas() {
        contenedorFilas.removeAllViews()
        val dp = resources.displayMetrics.density
        val lista = gestorServidores.lista()
        val activa = gestorServidores.activa()

        if (lista.isEmpty()) {
            val txtVacio = TextView(this).apply {
                text = "Aún no hay servidores. Agrega la dirección del panel, por ejemplo 192.168.1.50"
                textSize = 14f
                setTextColor(Color.parseColor("#8A94A8"))
                setPadding(0, (10 * dp).toInt(), 0, (10 * dp).toInt())
            }
            contenedorFilas.addView(txtVacio)
            return
        }

        for (servidor in lista) {
            val esActiva = servidor.url == activa
            val filaLayout = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                background = crearFondoSuperficie(dp, bordeCian = esActiva)
                setPadding((14 * dp).toInt(), (14 * dp).toInt(), (14 * dp).toInt(), (14 * dp).toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    bottomMargin = (10 * dp).toInt()
                }
                setOnClickListener {
                    gestorServidores.fijarActiva(servidor.url)
                    setResult(RESULT_OK)
                    finish()
                }
            }

            // Punto de estado
            val estado = estadosSondeo[servidor.url]
            val colorPunto = when (estado) {
                true -> Color.parseColor("#34D399")
                false -> Color.parseColor("#F87171")
                else -> Color.parseColor("#8A94A8")
            }
            val punto = View(this).apply {
                background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(colorPunto)
                }
                layoutParams = LinearLayout.LayoutParams((10 * dp).toInt(), (10 * dp).toInt()).apply {
                    marginEnd = (12 * dp).toInt()
                }
            }
            filaLayout.addView(punto)

            // Columna con nombre y url
            val colTextos = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            val filaTitulo = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }

            val txtNombre = TextView(this).apply {
                text = servidor.nombre
                textSize = 16f
                setTypeface(null, Typeface.BOLD)
                setTextColor(Color.parseColor("#E6ECF7"))
            }
            filaTitulo.addView(txtNombre)

            if (esActiva) {
                val txtEnUso = TextView(this).apply {
                    text = "EN USO"
                    textSize = 11f
                    setTypeface(null, Typeface.BOLD)
                    setTextColor(Color.parseColor("#00E5FF"))
                    setPadding((8 * dp).toInt(), 0, 0, 0)
                }
                filaTitulo.addView(txtEnUso)
            }
            colTextos.addView(filaTitulo)

            val txtUrl = TextView(this).apply {
                text = servidor.url
                textSize = 13f
                setTextColor(Color.parseColor("#8A94A8"))
                typeface = Typeface.MONOSPACE
            }
            colTextos.addView(txtUrl)

            filaLayout.addView(colTextos)

            // Botón Editar
            val btnEditar = TextView(this).apply {
                text = "Editar"
                textSize = 14f
                setTextColor(Color.parseColor("#00E5FF"))
                setPadding((10 * dp).toInt(), (10 * dp).toInt(), 0, (10 * dp).toInt())
                setOnClickListener {
                    mostrarDialogoEditar(servidor)
                }
            }
            filaLayout.addView(btnEditar)

            contenedorFilas.addView(filaLayout)
        }
    }

    private fun mostrarDialogoEditar(servidorExistente: Servidor?) {
        val dp = resources.displayMetrics.density
        val padding = (20 * dp).toInt()

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
        }

        val inputNombre = EditText(this).apply {
            hint = "Nombre (ej. Casa, Fuera de casa)"
            setText(servidorExistente?.nombre ?: "")
            setTextColor(Color.parseColor("#E6ECF7"))
            setHintTextColor(Color.parseColor("#8A94A8"))
        }
        layout.addView(inputNombre)

        val inputUrl = EditText(this).apply {
            hint = "Dirección (ej. 192.168.1.50 o https://mi-dominio)"
            setText(servidorExistente?.url ?: "")
            setTextColor(Color.parseColor("#E6ECF7"))
            setHintTextColor(Color.parseColor("#8A94A8"))
            inputType = InputType.TYPE_TEXT_VARIATION_URI
        }
        layout.addView(inputUrl)

        val builder = AlertDialog.Builder(this, R.style.Dialogo)
            .setTitle(if (servidorExistente == null) "Agregar dirección" else "Editar dirección")
            .setView(layout)
            .setPositiveButton("Guardar", null) // Se sobrescribe abajo para evitar cierre automático si hay error
            .setNegativeButton("Cancelar", null)

        if (servidorExistente != null) {
            builder.setNeutralButton("Quitar") { _, _ ->
                confirmarQuitar(servidorExistente.url)
            }
        }

        val dialogo = builder.create()
        dialogo.setOnShowListener {
            dialogo.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val textoUrl = inputUrl.text.toString()
                val urlNormalizada = Servidores.normalizar(textoUrl)
                if (urlNormalizada == null) {
                    Toast.makeText(this, "Dirección no válida", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }

                var nombre = inputNombre.text.toString().trim()
                if (nombre.isEmpty()) {
                    nombre = "Casa"
                }

                if (servidorExistente != null) {
                    gestorServidores.reemplazar(servidorExistente.url, Servidor(nombre, urlNormalizada))
                } else {
                    gestorServidores.agregar(Servidor(nombre, urlNormalizada))
                    if (gestorServidores.activa() == null) {
                        gestorServidores.fijarActiva(urlNormalizada)
                    }
                }

                setResult(RESULT_OK)
                refrescarFilas()
                dialogo.dismiss()

                // Probar url en segundo plano
                Thread {
                    val responde = Sondeo.responde(urlNormalizada)
                    runOnUiThread {
                        estadosSondeo[urlNormalizada] = responde
                        refrescarFilas()
                        if (responde) {
                            Toast.makeText(this, "Conectado", Toast.LENGTH_SHORT).show()
                        } else {
                            Toast.makeText(this, "No responde (se guardó igual)", Toast.LENGTH_SHORT).show()
                        }
                    }
                }.start()
            }
        }
        dialogo.show()
    }

    private fun confirmarQuitar(url: String) {
        AlertDialog.Builder(this, R.style.Dialogo)
            .setTitle("Quitar servidor")
            .setMessage("¿Seguro que deseas quitar esta dirección?")
            .setPositiveButton("Quitar") { _, _ ->
                gestorServidores.quitar(url)
                estadosSondeo.remove(url)
                setResult(RESULT_OK)
                refrescarFilas()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun ejecutarBusquedaEnRed() {
        btnBuscar.isEnabled = false
        btnBuscar.text = "Buscando… 0%"

        Thread {
            val urlsEncontradas = Sondeo.buscarEnRed(this, Servidores.PUERTO) { avance ->
                runOnUiThread {
                    btnBuscar.text = "Buscando… $avance%"
                }
            }

            runOnUiThread {
                btnBuscar.isEnabled = true
                btnBuscar.text = "Buscar en la red"

                if (urlsEncontradas.isEmpty()) {
                    AlertDialog.Builder(this, R.style.Dialogo)
                        .setTitle("Sin resultados")
                        .setMessage("No encontré el panel en esta red. Revisa que el celular esté en el WiFi de la casa y que el panel esté encendido.")
                        .setPositiveButton("Aceptar", null)
                        .show()
                } else {
                    val itemsArray = urlsEncontradas.toTypedArray()
                    AlertDialog.Builder(this, R.style.Dialogo)
                        .setTitle("Selecciona una dirección")
                        .setItems(itemsArray) { _, cual ->
                            val nuevaUrl = itemsArray[cual]
                            procesarUrlEncontrada(nuevaUrl)
                        }
                        .setNegativeButton("Cancelar", null)
                        .show()
                }
            }
        }.start()
    }

    private fun procesarUrlEncontrada(nueva: String) {
        val listaActual = gestorServidores.lista()
        val activaActual = gestorServidores.activa()

        // Si ya existe exactamente esa url
        if (listaActual.any { it.url == nueva }) {
            gestorServidores.fijarActiva(nueva)
            setResult(RESULT_OK)
            refrescarFilas()
            Toast.makeText(this, "Activada: $nueva", Toast.LENGTH_SHORT).show()
            return
        }

        // Si hay una activa y su host difiere pero su puerto coincide
        if (activaActual != null) {
            try {
                val uriActiva = java.net.URI(activaActual)
                val uriNueva = java.net.URI(nueva)
                if (uriActiva.port == uriNueva.port && uriActiva.host != uriNueva.host) {
                    AlertDialog.Builder(this, R.style.Dialogo)
                        .setTitle("Cambio de IP detectado")
                        .setMessage("¿Reemplazar $activaActual por $nueva? (la casa cambió de IP)")
                        .setPositiveButton("Reemplazar") { _, _ ->
                            val servidorActivo = listaActual.find { it.url == activaActual }
                            val nombre = servidorActivo?.nombre ?: "Casa"
                            gestorServidores.reemplazar(activaActual, Servidor(nombre, nueva))
                            gestorServidores.fijarActiva(nueva)
                            setResult(RESULT_OK)
                            refrescarFilas()
                        }
                        .setNeutralButton("Agregar aparte") { _, _ ->
                            gestorServidores.agregar(Servidor("Casa", nueva))
                            gestorServidores.fijarActiva(nueva)
                            setResult(RESULT_OK)
                            refrescarFilas()
                        }
                        .setNegativeButton("Cancelar", null)
                        .show()
                    return
                }
            } catch (_: Exception) {}
        }

        // Si no hay activa o no aplica lo anterior
        if (activaActual == null) {
            gestorServidores.agregar(Servidor("Casa", nueva))
            gestorServidores.fijarActiva(nueva)
        } else {
            gestorServidores.agregar(Servidor("Casa", nueva))
            gestorServidores.fijarActiva(nueva)
        }
        setResult(RESULT_OK)
        refrescarFilas()
        Toast.makeText(this, "Agregada y activada: $nueva", Toast.LENGTH_SHORT).show()
    }

    private fun ejecutarProbarConexion() {
        val lista = gestorServidores.lista()
        if (lista.isEmpty()) {
            Toast.makeText(this, "No hay servidores para probar", Toast.LENGTH_SHORT).show()
            return
        }

        btnProbar.isEnabled = false
        btnProbar.text = "Probando…"

        Thread {
            for (servidor in lista) {
                val ok = Sondeo.responde(servidor.url)
                estadosSondeo[servidor.url] = ok
            }

            runOnUiThread {
                btnProbar.isEnabled = true
                btnProbar.text = "Probar conexión"
                refrescarFilas()
                Toast.makeText(this, "Prueba finalizada", Toast.LENGTH_SHORT).show()
            }
        }.start()
    }

    private fun setCapsAll(caps: Boolean) {
        // Método auxiliar para compatibilidad de botones con setAllCaps / textAllCaps
    }
}
