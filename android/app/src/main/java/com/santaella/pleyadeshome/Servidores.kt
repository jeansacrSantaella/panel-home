package com.santaella.pleyadeshome

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.net.URISyntaxException
import java.util.Locale

data class Servidor(val nombre: String, val url: String)

class Servidores(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("servidores", Context.MODE_PRIVATE)

    fun lista(): List<Servidor> {
        val jsonStr = prefs.getString("lista", null) ?: return emptyList()
        val resultado = mutableListOf<Servidor>()
        try {
            val arr = JSONArray(jsonStr)
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                val nombre = obj.optString("nombre", "")
                val url = obj.optString("url", "")
                if (url.isNotEmpty()) {
                    resultado.add(Servidor(nombre, url))
                }
            }
        } catch (e: Exception) {
            // Tolera JSON corrupto devolviendo lista vacía
            return emptyList()
        }
        return resultado
    }

    fun guardar(lista: List<Servidor>) {
        val arr = JSONArray()
        for (s in lista) {
            val obj = JSONObject()
            obj.put("nombre", s.nombre)
            obj.put("url", s.url)
            arr.put(obj)
        }
        prefs.edit().putString("lista", arr.toString()).apply()
    }

    fun activa(): String? {
        return prefs.getString("activa", null)
    }

    fun fijarActiva(url: String?) {
        prefs.edit().putString("activa", url).apply()
    }

    fun agregar(s: Servidor) {
        val l = lista().toMutableList()
        val index = l.indexOfFirst { it.url.equals(s.url, ignoreCase = true) }
        if (index >= 0) {
            l[index] = s
        } else {
            l.add(s)
        }
        guardar(l)

        if (activa() == null || l.size == 1) {
            fijarActiva(s.url)
        }
    }

    fun reemplazar(urlVieja: String, nuevo: Servidor) {
        val l = lista().toMutableList()
        val index = l.indexOfFirst { it.url.equals(urlVieja, ignoreCase = true) }
        if (index >= 0) {
            l[index] = nuevo
        } else {
            l.add(nuevo)
        }
        guardar(l)

        val actual = activa()
        if (actual != null && actual.equals(urlVieja, ignoreCase = true)) {
            fijarActiva(nuevo.url)
        }
    }

    fun quitar(url: String) {
        val l = lista().toMutableList()
        l.removeAll { it.url.equals(url, ignoreCase = true) }
        guardar(l)

        val actual = activa()
        if (actual != null && actual.equals(url, ignoreCase = true)) {
            fijarActiva(l.firstOrNull()?.url)
        }
    }

    companion object {
        const val PUERTO = 8770

        fun normalizar(texto: String): String? {
            val trimmed = texto.trim()
            if (trimmed.isEmpty()) return null

            val tieneEsquema = trimmed.lowercase(Locale.ROOT).startsWith("http://") ||
                    trimmed.lowercase(Locale.ROOT).startsWith("https://")

            val candidato = if (!tieneEsquema) {
                "http://$trimmed"
            } else {
                trimmed
            }

            try {
                val uri = URI(candidato)
                val scheme = uri.scheme?.lowercase(Locale.ROOT) ?: return null
                val host = uri.host?.lowercase(Locale.ROOT)
                if (host.isNullOrEmpty()) return null

                val port = uri.port

                // Si el texto original no traía esquema y no trae puerto explícito, agrega :8770
                val puertoFinal = if (!tieneEsquema && port == -1) {
                    ":$PUERTO"
                } else if (port != -1) {
                    ":$port"
                } else {
                    ""
                }

                return "$scheme://$host$puertoFinal"
            } catch (e: URISyntaxException) {
                return null
            } catch (e: Exception) {
                return null
            }
        }
    }
}
