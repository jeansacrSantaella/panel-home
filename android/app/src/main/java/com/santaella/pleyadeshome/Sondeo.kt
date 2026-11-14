package com.santaella.pleyadeshome

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkAddress
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URI
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.min

object Sondeo {

    fun responde(url: String, msTope: Int = 2500): Boolean {
        var conexion: HttpURLConnection? = null
        return try {
            val uri = URI(url.trimEnd('/') + "/salud")
            val objUrl = uri.toURL()
            conexion = (objUrl.openConnection() as HttpURLConnection).apply {
                connectTimeout = msTope
                readTimeout = msTope
                instanceFollowRedirects = true
                useCaches = false
                requestMethod = "GET"
            }

            val codigo = conexion.responseCode
            if (codigo != 200) {
                return false
            }

            val inputStream = try {
                conexion.inputStream
            } catch (e: Exception) {
                conexion.errorStream
            } ?: return false

            val reader = BufferedReader(InputStreamReader(inputStream))
            val sb = StringBuilder()
            val charBuf = CharArray(1024)
            var totalLeido = 0
            var leidos: Int

            while (reader.read(charBuf).also { leidos = it } != -1) {
                val aLeer = min(leidos, 2048 - totalLeido)
                if (aLeer > 0) {
                    sb.append(charBuf, 0, aLeer)
                    totalLeido += aLeer
                }
                if (totalLeido >= 2048) break
            }
            reader.close()

            val cuerpo = sb.toString().lowercase()
            cuerpo.contains("\"ok\"")
        } catch (e: Exception) {
            false
        } finally {
            try {
                conexion?.disconnect()
            } catch (e: Exception) {
                // Ignorar
            }
        }
    }

    fun primeraQueResponde(urls: List<String>): String? {
        if (urls.isEmpty()) return null

        val n = min(urls.size, 8)
        val executor = Executors.newFixedThreadPool(n)
        val resultados = java.util.concurrent.ConcurrentHashMap<String, Boolean>()

        try {
            for (url in urls) {
                executor.submit {
                    val resp = responde(url, 2500)
                    resultados[url] = resp
                }
            }

            executor.shutdown()
            executor.awaitTermination(4, TimeUnit.SECONDS)

            // Devuelve la primera URL EN EL ORDEN DE LA LISTA que respondió true
            for (url in urls) {
                if (resultados[url] == true) {
                    return url
                }
            }
        } catch (e: Exception) {
            // Retornar null en caso de interrupción u otro error
        } finally {
            executor.shutdownNow()
        }

        return null
    }

    fun ipLocal(ctx: Context): String? {
        try {
            val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return null
            val redActiva = cm.activeNetwork ?: return null
            val props = cm.getLinkProperties(redActiva) ?: return null

            for (linkAddr: LinkAddress in props.linkAddresses) {
                val addr = linkAddr.address
                if (addr is Inet4Address && !addr.isLoopbackAddress) {
                    return addr.hostAddress
                }
            }
        } catch (e: Exception) {
            return null
        }
        return null
    }

    fun buscarEnRed(ctx: Context, puerto: Int = Servidores.PUERTO, avance: ((Int) -> Unit)? = null): List<String> {
        val ipStr = ipLocal(ctx) ?: return emptyList()
        val partes = ipStr.split(".")
        if (partes.size != 4) return emptyList()

        val prefijo = "${partes[0]}.${partes[1]}.${partes[2]}"
        val propioOcteto = partes[3].toIntOrNull() ?: -1

        val pool = Executors.newFixedThreadPool(48)
        val encontrados = java.util.concurrent.ConcurrentLinkedQueue<String>()
        val contadorCompletados = AtomicInteger(0)
        val totalIps = 254

        for (i in 1..254) {
            if (i == propioOcteto) {
                val completados = contadorCompletados.incrementAndGet()
                avance?.invoke((completados * 100) / totalIps)
                continue
            }

            pool.submit {
                val ipObjetivo = "$prefijo.$i"
                var socketConectado = false

                try {
                    val socket = Socket()
                    socket.connect(InetSocketAddress(ipObjetivo, puerto), 350)
                    socket.close()
                    socketConectado = true
                } catch (e: Exception) {
                    // No hay servicio en ese puerto
                }

                if (socketConectado) {
                    val urlCandidata = "http://$ipObjetivo:$puerto"
                    if (responde(urlCandidata, 1500)) {
                        encontrados.add(urlCandidata)
                    }
                }

                val completados = contadorCompletados.incrementAndGet()
                avance?.invoke((completados * 100) / totalIps)
            }
        }

        try {
            pool.shutdown()
            pool.awaitTermination(25, TimeUnit.SECONDS)
        } catch (e: Exception) {
            pool.shutdownNow()
        }

        // Ordenar las URLs encontradas por el último octeto
        return encontrados.toList().sortedBy { url ->
            try {
                val uri = URI(url)
                val host = uri.host ?: ""
                val ultPartes = host.split(".")
                if (ultPartes.size == 4) {
                    ultPartes[3].toIntOrNull() ?: 0
                } else {
                    0
                }
            } catch (e: Exception) {
                0
            }
        }
    }
}
