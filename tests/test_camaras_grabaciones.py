from __future__ import annotations

import io
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from panel.camaras.grabaciones import MAX_SELECCION, GrabacionError, Grabaciones


class SoloEscritura:
    """Salida binaria sin seek ni tell, como el wfile de http.server."""

    def __init__(self):
        self.trozos = []

    def write(self, datos: bytes) -> int:
        self.trozos.append(bytes(datos))
        return len(datos)

    def getvalue(self) -> bytes:
        return b"".join(self.trozos)


class GrabacionesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.g = Grabaciones(self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def crear(self, tipo: str, fecha: str, nombre: str, contenido: bytes = b"x") -> Path:
        carpeta = self.data / tipo / fecha
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / nombre
        ruta.write_bytes(contenido)
        return ruta

    def test_dias_ordena_y_mezcla_fotos_y_clips(self):
        self.crear("fotos", "2026-01-02", "a.jpg")
        self.crear("clips", "2026-01-03", "b.mp4")
        self.crear("fotos", "2026-01-01", "c.jpg")
        self.crear("clips", "2026-01-02", "d.mp4")
        (self.data / "fotos" / "basura").mkdir(parents=True)
        (self.data / "clips" / "2026-1-1").mkdir(parents=True)
        self.assertEqual(self.g.dias(), ["2026-01-03", "2026-01-02", "2026-01-01"])

    def test_dias_sin_carpetas(self):
        self.assertEqual(self.g.dias(), [])

    def test_fotos_y_clips_filtran_por_extension(self):
        self.crear("fotos", "2026-01-02", "a.jpg")
        self.crear("fotos", "2026-01-02", "d.jpg")
        self.crear("fotos", "2026-01-02", "b.png")
        self.crear("fotos", "2026-01-02", "c.mp4")
        self.crear("clips", "2026-01-02", "z.mp4")
        self.crear("clips", "2026-01-02", "a.mp4")
        self.crear("clips", "2026-01-02", "n.jpg")
        self.assertEqual(self.g.fotos("2026-01-02"), ["a.jpg", "d.jpg"])
        self.assertEqual(self.g.clips("2026-01-02"), ["a.mp4", "z.mp4"])
        self.assertEqual(self.g.fotos("2026-01-09"), [])

    def test_fecha_invalida_da_422(self):
        for fecha in ("2026-1-1", "../x", "/tmp"):
            with self.subTest(fecha=fecha):
                with self.assertRaises(GrabacionError) as ctx:
                    self.g.fotos(fecha)
                self.assertEqual(ctx.exception.codigo, 422)
                with self.assertRaises(GrabacionError) as ctx:
                    self.g.clips(fecha)
                self.assertEqual(ctx.exception.codigo, 422)

    def test_ruta_rechaza_nombres_y_fechas_inseguras(self):
        casos = [
            ("fotos", "2026-01-01", "../x.jpg"),
            ("fotos", "2026-01-01", "a/b.jpg"),
            ("fotos", "2026-1-1", "a.jpg"),
            ("fotos", "../../etc", "a.jpg"),
            ("fotos", "/etc", "a.jpg"),
            ("fotos", "2026-01-01", "/etc/passwd"),
            ("otro", "2026-01-01", "a.jpg"),
        ]
        for tipo, fecha, archivo in casos:
            with self.subTest(tipo=tipo, fecha=fecha, archivo=archivo):
                with self.assertRaises(GrabacionError) as ctx:
                    self.g.ruta(tipo, fecha, archivo)
                self.assertEqual(ctx.exception.codigo, 404)

    def test_ruta_valida_no_exige_que_exista(self):
        ruta = self.g.ruta("fotos", "2026-01-01", "a.jpg")
        self.assertEqual(ruta, self.data / "fotos" / "2026-01-01" / "a.jpg")
        self.assertFalse(ruta.exists())

    def test_ruta_no_sale_por_enlace_simbolico(self):
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        objetivo = Path(fuera.name) / "secreto.jpg"
        objetivo.write_bytes(b"x")
        carpeta = self.data / "fotos" / "2026-01-01"
        carpeta.mkdir(parents=True)
        os.symlink(objetivo, carpeta / "enlace.jpg")
        with self.assertRaises(GrabacionError) as ctx:
            self.g.ruta("fotos", "2026-01-01", "enlace.jpg")
        self.assertEqual(ctx.exception.codigo, 404)

    def test_mime_por_tipo(self):
        self.assertEqual(self.g.tipo_mime("fotos"), "image/jpeg")
        self.assertEqual(self.g.tipo_mime("clips"), "video/mp4")

    def test_resolver_omite_inexistentes_y_arma_arcname(self):
        self.crear("fotos", "2026-01-01", "a.jpg")
        self.crear("clips", "2026-01-01", "b.mp4")
        res = self.g.resolver(["2026-01-01/a.jpg", "2026-01-01/no.jpg"], ["2026-01-01/b.mp4"])
        self.assertEqual([arc for _, arc in res], ["fotos/2026-01-01/a.jpg", "clips/2026-01-01/b.mp4"])

    def test_resolver_limites_y_formato(self):
        with self.assertRaises(GrabacionError) as ctx:
            self.g.resolver(["2026-01-01/a.jpg"] * (MAX_SELECCION + 1), [])
        self.assertEqual(ctx.exception.codigo, 422)
        with self.assertRaises(GrabacionError) as ctx:
            self.g.resolver(["sinbarra"], [])
        self.assertEqual(ctx.exception.codigo, 422)
        with self.assertRaises(GrabacionError) as ctx:
            self.g.resolver(["2026-01-01/../x.jpg"], [])
        self.assertEqual(ctx.exception.codigo, 404)

    def test_borrar_devuelve_conteo_y_quita_carpeta_vacia(self):
        self.crear("fotos", "2026-01-01", "a.jpg")
        self.crear("fotos", "2026-01-01", "b.jpg")
        self.crear("clips", "2026-01-01", "c.mp4")
        n = self.g.borrar(["2026-01-01/a.jpg", "2026-01-01/b.jpg", "2026-01-01/x.jpg"], [])
        self.assertEqual(n, 2)
        self.assertFalse((self.data / "fotos" / "2026-01-01").exists())
        self.assertTrue((self.data / "clips" / "2026-01-01" / "c.mp4").exists())

    def test_borrar_dia_devuelve_conteo_y_quita_carpetas(self):
        self.crear("fotos", "2026-01-01", "a.jpg")
        self.crear("clips", "2026-01-01", "c.mp4")
        self.crear("clips", "2026-01-02", "d.mp4")
        self.assertEqual(self.g.borrar_dia("2026-01-01"), 2)
        self.assertFalse((self.data / "fotos" / "2026-01-01").exists())
        self.assertFalse((self.data / "clips" / "2026-01-01").exists())
        self.assertTrue((self.data / "clips" / "2026-01-02" / "d.mp4").exists())
        self.assertEqual(self.g.borrar_dia("2026-01-05"), 0)
        with self.assertRaises(GrabacionError):
            self.g.borrar_dia("../x")

    def test_escribir_zip_sobre_salida_sin_seek(self):
        self.crear("fotos", "2026-01-01", "a.jpg", b"JPEG")
        self.crear("clips", "2026-01-01", "b.mp4", b"MP4")
        salida = SoloEscritura()
        self.g.escribir_zip(self.g.pares_dia("2026-01-01"), salida)
        with zipfile.ZipFile(io.BytesIO(salida.getvalue())) as z:
            self.assertEqual(z.namelist(), ["fotos/2026-01-01/a.jpg", "clips/2026-01-01/b.mp4"])
            self.assertEqual(z.read("fotos/2026-01-01/a.jpg"), b"JPEG")
            self.assertEqual(z.read("clips/2026-01-01/b.mp4"), b"MP4")

    def test_escribir_zip_sin_pares_da_404_y_no_escribe(self):
        salida = SoloEscritura()
        with self.assertRaises(GrabacionError) as ctx:
            self.g.escribir_zip([], salida)
        self.assertEqual(ctx.exception.codigo, 404)
        self.assertEqual(salida.trozos, [])

    def test_nombre_zip(self):
        self.assertRegex(Grabaciones.nombre_zip(), r"^grabaciones_\d{4}-\d\d-\d\d_\d\d-\d\d\.zip$")


if __name__ == "__main__":
    unittest.main()
