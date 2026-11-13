from __future__ import annotations

import argparse
import sys
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panel.db import Db
from panel.camaras.registro import Registro


def copiar_datos(origen: Path, destino: Path) -> dict:
    """Copia recursivamente las carpetas fotos/ y clips/ de origen a destino.

    Preserva subcarpetas por fecha, usa shutil.copy2 solo si el archivo no existe
    en destino y crea carpetas faltantes. Devuelve un diccionario con los conteos
    de archivos copiados y existentes.
    """
    copiados = 0
    existentes = 0

    subcarpetas = ["fotos", "clips"]
    for sub in subcarpetas:
        orig_sub = origen / sub
        if not orig_sub.is_dir():
            continue

        dest_sub = destino / sub
        for archivo_origen in orig_sub.rglob("*"):
            if archivo_origen.is_dir():
                continue

            rel_path = archivo_origen.relative_to(orig_sub)
            archivo_destino = dest_sub / rel_path

            if archivo_destino.exists():
                existentes += 1
            else:
                archivo_destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archivo_origen, archivo_destino)
                copiados += 1

    return {"copiados": copiados, "existentes": existentes}


def migrar(cameras_json: Path, panel_db: Path, datos: Path | None = None) -> dict:
    """Importa cámaras desde cameras.json y opcionalmente copia datos multimedia.

    Devuelve un diccionario con los conteos de cámaras importadas, archivos copiados
    y archivos existentes.
    """
    if not cameras_json.is_file():
        print(f"Error: El archivo de cámaras '{cameras_json}' no existe.", file=sys.stderr)
        sys.exit(1)

    reg = Registro(Db(panel_db))
    n_camaras = reg.importar_json(cameras_json)
    print(f"Se importaron {n_camaras} cámaras.")

    copiados = 0
    existentes = 0
    if datos is not None and datos.is_dir():
        destino_datos = panel_db.parent
        res_copia = copiar_datos(datos, destino_datos)
        copiados = res_copia["copiados"]
        existentes = res_copia["existentes"]
        print(f"Archivos copiados: {copiados}, ya existentes: {existentes}.")

    return {
        "camaras": n_camaras,
        "copiados": copiados,
        "existentes": existentes,
    }


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal para el script CLI de migración de cámaras."""
    parser = argparse.ArgumentParser(description="Migrar cámaras y datos desde gestorCamaras.")
    parser.add_argument("cameras", type=Path, help="Ruta al archivo cameras.json de gestorCamaras")
    parser.add_argument(
        "--panel-db",
        type=Path,
        default=ROOT / "data" / "panel.db",
        help="Ruta a la base de datos del panel",
    )
    parser.add_argument(
        "--datos",
        type=Path,
        default=None,
        help="Carpeta de datos de gestorCamaras (fotos/ y clips/)",
    )

    args = parser.parse_args(argv)

    try:
        migrar(args.cameras, args.panel_db, args.datos)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
