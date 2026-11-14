package com.santaella.pleyadeshome

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NormalizarTest {
    private fun n(t: String) = Servidores.normalizar(t)

    @Test fun ipSolaAgregaEsquemaYPuerto() = assertEquals("http://192.168.1.50:8770", n(" 192.168.1.50 "))
    @Test fun ipConPuertoRespetaPuerto() = assertEquals("http://192.168.1.50:9000", n("192.168.1.50:9000"))
    @Test fun conEsquemaNoAgregaPuerto() = assertEquals("https://casa.ejemplo.mx", n("HTTPS://Casa.Ejemplo.mx/"))
    @Test fun quitaRutaYConsulta() = assertEquals("http://10.0.0.5:8770", n("http://10.0.0.5:8770/#red?x=1"))
    @Test fun nombreDeHostSinEsquema() = assertEquals("http://lenovo.local:8770", n("lenovo.local"))
    @Test fun vacioEsNulo() = assertNull(n("   "))
    @Test fun basuraEsNula() = assertNull(n("http://"))
    @Test fun espaciosInternosEsNulo() = assertNull(n("192.168 .1.5"))
}
