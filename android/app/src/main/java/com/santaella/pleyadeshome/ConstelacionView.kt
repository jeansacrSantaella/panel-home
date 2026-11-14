package com.santaella.pleyadeshome

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import android.view.View
import android.view.animation.DecelerateInterpolator

class ConstelacionView(ctx: Context) : View(ctx) {

    var estado: String = "Conectando con la casa…"
        set(value) {
            field = value
            invalidate()
        }

    private var animator: ValueAnimator? = null
    private var progresoAnim: Float = 0f
    private var callbackTerminado: (() -> Unit)? = null
    private var yaTermino: Boolean = false

    // Estrellas: (x, y, radio)
    private val datosEstrellas = listOf(
        Triple(246f, 586f, 33f),
        Triple(251f, 545f, 20f),
        Triple(542f, 737f, 26f),
        Triple(724f, 565f, 31f),
        Triple(656f, 451f, 29f),
        Triple(724f, 373f, 24f),
        Triple(802f, 503f, 18f),
        Triple(698f, 285f, 18f)
    )

    // Alcyone (la casa)
    private val alcyoneCoord = Pair(438f, 607f)

    // Trazos: pares de índices o coordenadas
    private val paresTrazos = listOf(
        Pair(Pair(251f, 545f), Pair(246f, 586f)),
        Pair(Pair(246f, 586f), Pair(438f, 607f)),
        Pair(Pair(438f, 607f), Pair(542f, 737f)),
        Pair(Pair(542f, 737f), Pair(724f, 565f)),
        Pair(Pair(724f, 565f), Pair(656f, 451f)),
        Pair(Pair(656f, 451f), Pair(438f, 607f)),
        Pair(Pair(656f, 451f), Pair(724f, 373f)),
        Pair(Pair(724f, 373f), Pair(698f, 285f)),
        Pair(Pair(724f, 565f), Pair(802f, 503f))
    )

    // Paints y Paths precalculados
    private val paintFondo = Paint().apply {
        color = Color.parseColor("#0B0F17")
        style = Paint.Style.FILL
    }

    private val paintTrazo = Paint().apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        isAntiAlias = true
    }

    private val paintEstrellaRelleno = Paint().apply {
        color = Color.parseColor("#F4FDFF")
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    private val paintEstrellaBorde = Paint().apply {
        color = Color.parseColor("#00E5FF")
        style = Paint.Style.STROKE
        isAntiAlias = true
    }

    private val paintAlcyoneEstrella = Paint().apply {
        color = Color.parseColor("#EAFFFF")
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    private val paintAlcyoneCentro = Paint().apply {
        color = Color.WHITE
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    private val paintTextoPleyades = Paint().apply {
        color = Color.parseColor("#E6ECF7")
        textSize = 0f // se ajusta en onSizeChanged
        isAntiAlias = true
        isFakeBoldText = true
    }

    private val paintTextoHome = Paint().apply {
        textSize = 0f
        isAntiAlias = true
        isFakeBoldText = true
    }

    private val paintTextoEstado = Paint().apply {
        color = Color.parseColor("#8A94A8")
        textSize = 0f
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
    }

    private val paintTextoPie = Paint().apply {
        color = Color.parseColor("#8A94A8")
        textSize = 0f
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
    }

    private val pathAlcyoneFigura = Path().apply {
        // M0,-112 C9,-29 29,-9 112,0 C29,9 9,29 0,112 C-9,29 -29,9 -112,0 C-29,-9 -9,-29 0,-112 Z
        moveTo(0f, -112f)
        cubicTo(9f, -29f, 29f, -9f, 112f, 0f)
        cubicTo(29f, 9f, 9f, 29f, 0f, 112f)
        cubicTo(-9f, 29f, -29f, 9f, -112f, 0f)
        cubicTo(-29f, -9f, -9f, -29f, 0f, -112f)
        close()
    }

    private var escalaDibujo = 1f
    private var offsetX = 0f
    private var offsetY = 0f

    // Mapeo de cada estrella a qué trazo finaliza en ella para su aparición
    // Orden de trazos:
    // 0: 251,545 -> 246,586  (llega a 246,586)
    // 1: 246,586 -> 438,607  (llega a Alcyone)
    // 2: 438,607 -> 542,737  (llega a 542,737)
    // 3: 542,737 -> 724,565  (llega a 724,565)
    // 4: 724,565 -> 656,451  (llega a 656,451)
    // 5: 656,451 -> 438,607  (llega a Alcyone)
    // 6: 656,451 -> 724,373  (llega a 724,373)
    // 7: 724,373 -> 698,285  (llega a 698,285)
    // 8: 724,565 -> 802,503  (llega a 802,503)
    // La primera (251,545) aparece al inicio.

    init {
        setBackgroundColor(Color.parseColor("#0B0F17"))
    }

    fun alTerminar(cb: () -> Unit) {
        if (yaTermino) {
            cb()
        } else {
            callbackTerminado = cb
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        animator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1600
            interpolator = DecelerateInterpolator()
            addUpdateListener { anim ->
                progresoAnim = anim.animatedValue as Float
                invalidate()
                if (progresoAnim >= 1f && !yaTermino) {
                    yaTermino = true
                    callbackTerminado?.invoke()
                }
            }
            start()
        }
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        animator = null
        super.onDetachedFromWindow()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)

        // Geometría viewBox x 190..870, y 230..790 -> Ancho = 680, Alto = 560
        val vbMinX = 190f
        val vbMinY = 230f
        val vbAncho = 680f
        val vbAlto = 560f

        // Centrado en el 70% del ancho de la vista y un poco arriba del centro vertical
        val objetivoAncho = w * 0.70f
        escalaDibujo = objetivoAncho / vbAncho

        val dibujoAnchoEscalado = vbAncho * escalaDibujo
        val dibujoAltoEscalado = vbAlto * escalaDibujo

        offsetX = (w - dibujoAnchoEscalado) / 2f - vbMinX * escalaDibujo
        offsetY = (h * 0.42f) - (vbAlto / 2f * escalaDibujo) - vbMinY * escalaDibujo

        // Configurar grosores y shaders escalados
        paintTrazo.strokeWidth = 26f * escalaDibujo
        paintEstrellaBorde.strokeWidth = 8f * escalaDibujo

        // LinearGradient violeta #8B5CF6 → azul #5AA8FF → cian #00E5FF de (246,737) a (802,285)
        val x1Shader = 246f * escalaDibujo + offsetX
        val y1Shader = 737f * escalaDibujo + offsetY
        val x2Shader = 802f * escalaDibujo + offsetX
        val y2Shader = 285f * escalaDibujo + offsetY

        paintTrazo.shader = LinearGradient(
            x1Shader, y1Shader, x2Shader, y2Shader,
            intArrayOf(
                Color.parseColor("#8B5CF6"),
                Color.parseColor("#5AA8FF"),
                Color.parseColor("#00E5FF")
            ),
            floatArrayOf(0f, 0.5f, 1f),
            Shader.TileMode.CLAMP
        )

        // Tamaños de texto
        val densidad = resources.displayMetrics.scaledDensity
        paintTextoPleyades.textSize = 34f * densidad
        paintTextoHome.textSize = 34f * densidad
        paintTextoEstado.textSize = 12f * densidad
        paintTextoPie.textSize = 11f * densidad

        // Shader para "Home"
        val textoHomeAncho = paintTextoHome.measureText("Home")
        val textoPleyadesAncho = paintTextoPleyades.measureText("Pleyades")
        val totalTextoAncho = textoPleyadesAncho + textoHomeAncho
        val inicioTextoX = (w - totalTextoAncho) / 2f

        paintTextoHome.shader = LinearGradient(
            inicioTextoX + textoPleyadesAncho, 0f,
            inicioTextoX + totalTextoAncho, 0f,
            intArrayOf(
                Color.parseColor("#8B5CF6"),
                Color.parseColor("#5AA8FF"),
                Color.parseColor("#00E5FF")
            ),
            null,
            Shader.TileMode.CLAMP
        )
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        canvas.drawColor(Color.parseColor("#0B0F17"))

        val progresoTotal = progresoAnim * 0.75f
        val numTrazos = paresTrazos.size
        val fraccionPorTrazo = 1f / numTrazos.toFloat()

        // Dibujar trazos
        for (i in 0 until numTrazos) {
            val inicioTrazoProgreso = i * fraccionPorTrazo
            if (progresoTotal <= inicioTrazoProgreso) continue

            val finTrazoProgreso = (i + 1) * fraccionPorTrazo
            val tLocal = if (progresoTotal >= finTrazoProgreso) {
                1f
            } else {
                (progresoTotal - inicioTrazoProgreso) / fraccionPorTrazo
            }

            val par = paresTrazos[i]
            val x1 = par.first.first * escalaDibujo + offsetX
            val y1 = par.first.second * escalaDibujo + offsetY
            val x2 = par.second.first * escalaDibujo + offsetX
            val y2 = par.second.second * escalaDibujo + offsetY

            val currentX2 = x1 + (x2 - x1) * tLocal
            val currentY2 = y1 + (y2 - y1) * tLocal

            canvas.drawLine(x1, y1, currentX2, currentY2, paintTrazo)
        }

        // Dibujar estrellas normales
        // Mapeo de aparición de estrellas según fin de trazos:
        // Estrellas en datosEstrellas:
        // 0: (246, 586) -> Termina trazo 0
        // 1: (251, 545) -> Aparece al inicio (progresoTotal > 0)
        // 2: (542, 737) -> Termina trazo 2
        // 3: (724, 565) -> Termina trazo 3
        // 4: (656, 451) -> Termina trazo 4
        // 5: (724, 373) -> Termina trazo 6
        // 6: (802, 503) -> Termina trazo 8
        // 7: (698, 285) -> Termina trazo 7
        val umbralesEstrellas = listOf(
            fraccionPorTrazo * 1f, // 0: 246,586 (trazo 0 termina)
            0f,                    // 1: 251,545 (inicio)
            fraccionPorTrazo * 3f, // 2: 542,737 (trazo 2 termina)
            fraccionPorTrazo * 4f, // 3: 724,565 (trazo 3 termina)
            fraccionPorTrazo * 5f, // 4: 656,451 (trazo 4 termina)
            fraccionPorTrazo * 7f, // 5: 724,373 (trazo 6 termina)
            fraccionPorTrazo * 9f, // 6: 802,503 (trazo 8 termina)
            fraccionPorTrazo * 8f  // 7: 698,285 (trazo 7 termina)
        )

        for (i in datosEstrellas.indices) {
            val umbral = umbralesEstrellas[i]
            if (progresoTotal >= umbral) {
                // Calcular alpha/escala de aparición rápida tras superar el umbral
                val span = fraccionPorTrazo
                val tEstrella = if (span == 0f) 1f else ((progresoTotal - umbral) / (span * 0.5f)).coerceIn(0f, 1f)

                val (vx, vy, radioBase) = datosEstrellas[i]
                val cx = vx * escalaDibujo + offsetX
                val cy = vy * escalaDibujo + offsetY
                val radioActual = radioBase * escalaDibujo * tEstrella

                if (radioActual > 0f) {
                    paintEstrellaRelleno.alpha = (255 * tEstrella).toInt()
                    paintEstrellaBorde.alpha = (255 * tEstrella).toInt()

                    canvas.drawCircle(cx, cy, radioActual, paintEstrellaRelleno)
                    canvas.drawCircle(cx, cy, radioActual, paintEstrellaBorde)
                }
            }
        }

        // Alcyone (casa) en (438, 607) -> Aparece cuando terminan los trazos que llegan a ella (trazo 1 y 5, usamos umbral de trazo 1 o interpolación desde 0.6)
        val umbralAlcyone = fraccionPorTrazo * 2f
        if (progresoTotal >= umbralAlcyone || progresoAnim >= 0.6f) {
            val tAlcyone = ((progresoAnim - 0.6f) / 0.4f).coerceIn(0f, 1f)
            if (tAlcyone > 0f) {
                val acx = alcyoneCoord.first * escalaDibujo + offsetX
                val acy = alcyoneCoord.second * escalaDibujo + offsetY

                // Halo RadialGradient radio 125 (escalado)
                val radioHalo = 125f * escalaDibujo
                val shaderHalo = RadialGradient(
                    acx, acy, radioHalo,
                    intArrayOf(
                        Color.WHITE,
                        Color.parseColor("#9FF6FF"),
                        Color.parseColor("#6600E5FF"), // Cian 40% aprox
                        Color.TRANSPARENT
                    ),
                    floatArrayOf(0f, 0.3f, 0.7f, 1f),
                    Shader.TileMode.CLAMP
                )
                val paintHalo = Paint().apply {
                    shader = shaderHalo
                    isAntiAlias = true
                    alpha = (255 * tAlcyone).toInt()
                }
                canvas.drawCircle(acx, acy, radioHalo, paintHalo)

                // Estrella de cuatro puntas con path
                canvas.save()
                canvas.translate(acx, acy)
                canvas.scale(tAlcyone * escalaDibujo, tAlcyone * escalaDibujo)
                paintAlcyoneEstrella.alpha = (255 * tAlcyone).toInt()
                canvas.drawPath(pathAlcyoneFigura, paintAlcyoneEstrella)

                // Círculo blanco radio 15 (escalado)
                canvas.drawCircle(0f, 0f, 15f * escalaDibujo, paintAlcyoneCentro)
                canvas.restore()
            }
        }

        // Textos debajo del dibujo
        val alphaTextos = (0.5f + (progresoAnim * 0.5f)).coerceIn(0.5f, 1f)
        val alphaInt = (255 * alphaTextos).toInt()

        val textoPleyades = "Pleyades"
        val textoHome = "Home"
        val anchoPleyades = paintTextoPleyades.measureText(textoPleyades)
        val anchoHome = paintTextoHome.measureText(textoHome)
        val anchoTotalTexto = anchoPleyades + anchoHome

        // Posición Y de los títulos: debajo del dibujo escalado
        val vbMaxY = 790f
        val dibujoMaxYSc = vbMaxY * escalaDibujo + offsetY
        val posYTitulos = dibujoMaxYSc + 48f * resources.displayMetrics.density

        val inicioX = (width - anchoTotalTexto) / 2f

        paintTextoPleyades.alpha = alphaInt
        paintTextoHome.alpha = alphaInt

        canvas.drawText(textoPleyades, inicioX, posYTitulos, paintTextoPleyades)
        canvas.drawText(textoHome, inicioX + anchoPleyades, posYTitulos, paintTextoHome)

        // Estado debajo
        paintTextoEstado.alpha = alphaInt
        val posYEstado = posYTitulos + 28f * resources.displayMetrics.density
        canvas.drawText(estado, width / 2f, posYEstado, paintTextoEstado)

        // Pie abajo del todo, a 24dp del borde inferior
        paintTextoPie.alpha = alphaInt
        val posYPie = height - 24f * resources.displayMetrics.density
        canvas.drawText("familia Astreo · Santaella", width / 2f, posYPie, paintTextoPie)
    }
}
