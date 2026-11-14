package com.santaella.pleyadeshome

import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.GeolocationPermissions
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.net.URL

class MainActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var constelacionView: ConstelacionView
    private lateinit var panelError: LinearLayout
    private lateinit var txtErrorDir: TextView

    private val servidores by lazy { Servidores(this) }
    private var urlCargadaActual: String? = null
    private var animacionConstelacionTerminada = false
    private var cargaWebViewLista = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Depuración remota del WebView (chrome://inspect) solo en el APK de depuración
        if (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0) WebView.setWebContentsDebuggingEnabled(true)

        // Barra de estado y navegación obsidiana
        window.statusBarColor = Color.parseColor("#0B0F17")
        window.navigationBarColor = Color.parseColor("#0B0F17")

        // Vista raíz: FrameLayout MATCH_PARENT
        val raiz = FrameLayout(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.parseColor("#0B0F17"))
        }

        // 1. WebView (abajo)
        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.parseColor("#0B0F17"))
            
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                // Como en Chrome: el video no puede arrancar con sonido sin un toque; las cámaras empiezan en silencio
                // y el botón 🔇/🔊 del panel (un toque) activa o quita el audio
                mediaPlaybackRequiresUserGesture = true
                mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                loadWithOverviewMode = true
                useWideViewPort = true
                builtInZoomControls = false
                setSupportZoom(false)
                userAgentString = (userAgentString ?: "") + " PleyadesHomeApp/1.0"
            }

            CookieManager.getInstance().setAcceptCookie(true)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
            }

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    val url = request?.url?.toString() ?: return false
                    val activa = servidores.activa()
                    try {
                        val hostActiva = if (!activa.isNullOrEmpty()) URL(activa).host else null
                        val hostNueva = URL(url).host
                        if (hostActiva != null && hostNueva != null && hostActiva != hostNueva) {
                            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                            return true
                        }
                    } catch (_: Exception) {}
                    return false
                }

                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: android.webkit.WebResourceError?
                ) {
                    if (request?.isForMainFrame == true) {
                        mostrarPanelError()
                    }
                }

                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    cargaWebViewLista = true
                    verificarOcultarConstelacion()
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest?) {
                    request?.grant(request.resources)
                }

                override fun onGeolocationPermissionsShowPrompt(
                    origin: String?,
                    callback: GeolocationPermissions.Callback?
                ) {
                    callback?.invoke(origin, false, false)
                }
            }

            setDownloadListener(DownloadListener { url, userAgent, contentDisposition, mimetype, _ ->
                try {
                    val request = DownloadManager.Request(Uri.parse(url)).apply {
                        setMimeType(mimetype)
                        addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url))
                        addRequestHeader("User-Agent", userAgent)
                        setDescription(url)
                        setTitle(URLUtil.guessFileName(url, contentDisposition, mimetype))
                        setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                        setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, URLUtil.guessFileName(url, contentDisposition, mimetype))
                    }
                    val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                    dm.enqueue(request)
                    Toast.makeText(this@MainActivity, "Descargando…", Toast.LENGTH_SHORT).show()
                } catch (e: Exception) {
                    Toast.makeText(this@MainActivity, "Error al descargar", Toast.LENGTH_SHORT).show()
                }
            })

            addJavascriptInterface(Puente(), "PleyadesApp")
        }

        // 2. Panel de error (medio)
        panelError = crearPanelError().apply {
            visibility = View.GONE
        }

        // 3. ConstelacionView (arriba)
        constelacionView = ConstelacionView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            estado = "Conectando con la casa…"
            alTerminar {
                animacionConstelacionTerminada = true
                verificarOcultarConstelacion()
            }
        }

        raiz.addView(webView)
        raiz.addView(panelError)
        raiz.addView(constelacionView)
        setContentView(raiz)

        // Arrancar proceso de red
        ejecutarArranque(animacionLarga = true)
    }

    private fun crearPanelError(): LinearLayout {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#0B0F17"))
            setPadding(px(28), px(28), px(28), px(28))
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            isFillViewport = true
        }

        val contenido = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }

        val txtTitulo = TextView(this).apply {
            text = "No encuentro el panel"
            textSize = 22f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#E6ECF7"))
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, px(16))
        }

        txtErrorDir = TextView(this).apply {
            text = "Puede que la casa haya cambiado de IP o que el celular no esté en su WiFi.\n\nDirección actual: —"
            textSize = 14f
            setTextColor(Color.parseColor("#8A94A8"))
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, px(24))
        }

        val btnReintentar = Button(this).apply {
            text = "Reintentar"
            textSize = 15f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#0B0F17"))
            isAllCaps = false
            val bg = GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                intArrayOf(Color.parseColor("#8B5CF6"), Color.parseColor("#5AA8FF"), Color.parseColor("#00E5FF"))
            ).apply {
                cornerRadius = px(14).toFloat()
            }
            background = bg
            setPadding(px(24), 0, px(24), 0)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                px(48)
            ).apply { setMargins(0, 0, 0, px(12)) }
            setOnClickListener {
                panelError.visibility = View.GONE
                constelacionView.alpha = 1f
                constelacionView.visibility = View.VISIBLE
                constelacionView.estado = "Conectando con la casa…"
                cargaWebViewLista = false
                ejecutarArranque(animacionLarga = false)
            }
        }

        val btnCambiar = Button(this).apply {
            text = "Cambiar dirección"
            textSize = 15f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#00E5FF"))
            isAllCaps = false
            val bg = GradientDrawable().apply {
                setColor(Color.parseColor("#0B0F17"))
                setStroke(px(2), Color.parseColor("#00E5FF"))
                cornerRadius = px(14).toFloat()
            }
            background = bg
            setPadding(px(24), 0, px(24), 0)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                px(48)
            ).apply { setMargins(0, 0, 0, px(32)) }
            setOnClickListener {
                val intent = Intent(this@MainActivity, AjustesActivity::class.java)
                startActivityForResult(intent, 1)
            }
        }

        val txtPie = TextView(this).apply {
            text = "familia Astreo · Santaella"
            textSize = 11f
            setTextColor(Color.parseColor("#8A94A8"))
            gravity = Gravity.CENTER
        }

        contenido.addView(txtTitulo)
        contenido.addView(txtErrorDir)
        contenido.addView(btnReintentar)
        contenido.addView(btnCambiar)
        contenido.addView(txtPie)
        scroll.addView(contenido)
        layout.addView(scroll)

        return layout
    }

    private fun ejecutarArranque(animacionLarga: Boolean) {
        if (!animacionLarga) {
            constelacionView.estado = "Conectando con la casa…"
        }

        Thread {
            val lista = servidores.lista()
            if (lista.isEmpty()) {
                runOnUiThread {
                    val intent = Intent(this, AjustesActivity::class.java).apply {
                        putExtra("primera_vez", true)
                    }
                    startActivityForResult(intent, 1)
                }
                return@Thread
            }

            val activaActual = servidores.activa()
            val orden = mutableListOf<String>()
            if (activaActual != null) {
                orden.add(activaActual)
            }
            for (s in lista) {
                if (s.url != activaActual) {
                    orden.add(s.url)
                }
            }

            val encontrada = Sondeo.primeraQueResponde(orden)
            if (encontrada != null) {
                val servidorEncontrado = lista.find { it.url == encontrada }
                val nombreServidor = servidorEncontrado?.nombre ?: "Casa"
                val cambio = encontrada != activaActual
                if (cambio) {
                    servidores.fijarActiva(encontrada)
                }
                runOnUiThread {
                    if (cambio) Toast.makeText(this, "Conectado a $nombreServidor", Toast.LENGTH_SHORT).show()
                    cargarUrl(encontrada)
                }
                return@Thread
            }

            // Si ninguna responde, buscar en red
            runOnUiThread {
                constelacionView.estado = "Buscando el panel en la red…"
            }

            val nuevasEncontradas = Sondeo.buscarEnRed(this, Servidores.PUERTO) { avance ->
                runOnUiThread {
                    constelacionView.estado = "Buscando el panel en la red… $avance%"
                }
            }

            if (nuevasEncontradas.isNotEmpty()) {
                val nuevaUrl = nuevasEncontradas.first()
                val hostNueva = try { URL(nuevaUrl).host } catch (_: Exception) { nuevaUrl }
                if (activaActual != null) {
                    try {
                        val puertoActiva = URL(activaActual).port
                        val puertoNueva = URL(nuevaUrl).port
                        if (puertoActiva == puertoNueva) {
                            val nombreActivo = servidores.lista().find { it.url == activaActual }?.nombre ?: "Casa"
                            servidores.reemplazar(activaActual, Servidor(nombreActivo, nuevaUrl))
                        } else {
                            servidores.agregar(Servidor("Casa", nuevaUrl))
                        }
                    } catch (_: Exception) {
                        servidores.agregar(Servidor("Casa", nuevaUrl))
                    }
                } else {
                    servidores.agregar(Servidor("Casa", nuevaUrl))
                }
                servidores.fijarActiva(nuevaUrl)
                runOnUiThread {
                    Toast.makeText(this, "La casa cambió de IP: ahora es $hostNueva", Toast.LENGTH_SHORT).show()
                    cargarUrl(nuevaUrl)
                }
                return@Thread
            }

            // No se encontró nada
            runOnUiThread {
                mostrarPanelError()
            }
        }.start()
    }

    private fun cargarUrl(url: String) {
        urlCargadaActual = url
        cargaWebViewLista = false
        webView.loadUrl(url)
    }

    private fun verificarOcultarConstelacion() {
        if (cargaWebViewLista && animacionConstelacionTerminada && constelacionView.visibility == View.VISIBLE) {
            constelacionView.animate()
                .alpha(0f)
                .setDuration(350)
                .withEndAction {
                    constelacionView.visibility = View.GONE
                }
                .start()
        }
    }

    private fun mostrarPanelError() {
        val activa = servidores.activa() ?: "—"
        txtErrorDir.text = "Puede que la casa haya cambiado de IP o que el celular no esté en su WiFi.\n\nDirección actual: $activa"
        panelError.visibility = View.VISIBLE
        constelacionView.visibility = View.GONE
    }

    inner class Puente {
        @JavascriptInterface
        fun servidores() {
            runOnUiThread {
                val intent = Intent(this@MainActivity, AjustesActivity::class.java)
                startActivityForResult(intent, 1)
            }
        }

        @JavascriptInterface
        fun version(): String {
            return try {
                val pInfo = packageManager.getPackageInfo(packageName, 0)
                pInfo.versionName ?: "1.0"
            } catch (e: Exception) {
                "1.0"
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    private var pausadaDesde = 0L

    override fun onPause() {
        super.onPause()
        pausadaDesde = System.currentTimeMillis()
        CookieManager.getInstance().flush()
    }

    // Al volver tras un rato (el celular cambió de red o la casa de IP): si el panel ya no responde, se busca de nuevo
    override fun onResume() {
        super.onResume()
        val url = urlCargadaActual ?: return
        if (pausadaDesde == 0L || System.currentTimeMillis() - pausadaDesde < 60_000) return
        if (panelError.visibility == View.VISIBLE) return
        Thread {
            if (!Sondeo.responde(url)) runOnUiThread {
                constelacionView.alpha = 1f
                constelacionView.visibility = View.VISIBLE
                constelacionView.estado = "Conectando con la casa…"
                cargaWebViewLista = false
                ejecutarArranque(animacionLarga = false)
            }
        }.start()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 1) {
            val lista = servidores.lista()
            if (lista.isEmpty()) {
                finish()
                return
            }
            val activaActual = servidores.activa()
            if (activaActual != urlCargadaActual || panelError.visibility == View.VISIBLE) {
                panelError.visibility = View.GONE
                constelacionView.alpha = 1f
                constelacionView.visibility = View.VISIBLE
                constelacionView.estado = "Conectando con la casa…"
                animacionConstelacionTerminada = true
                cargaWebViewLista = false
                ejecutarArranque(animacionLarga = false)
            }
        }
    }

    private fun px(dp: Int): Int {
        return (dp * resources.displayMetrics.density).toInt()
    }
}
