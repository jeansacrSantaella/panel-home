import logging
import os
import time
import json
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("detector")

PANEL_URL = os.environ.get("PANEL_URL", "http://panel-home:8770")
INTERNO_TOKEN = os.environ.get("INTERNO_TOKEN", "")
GO2RTC_URL = os.environ.get("GO2RTC_URL", "http://go2rtc:1984")
RTSP_URL = os.environ.get("RTSP_URL", "rtsp://go2rtc:8554")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
INTERVALO = float(os.environ.get("INTERVALO", "1.5"))
CONFIANZA = float(os.environ.get("CONFIANZA", "0.5"))
MOVIMIENTO = float(os.environ.get("MOVIMIENTO", "0.004"))
ENFRIAMIENTO = float(os.environ.get("ENFRIAMIENTO", "30"))
RETENCION_HORAS = float(os.environ.get("RETENCION_HORAS", "24"))
CLIP_SEG = int(os.environ.get("CLIP_SEG", "15"))
MODELO = os.environ.get("MODELO", "yolo11n.pt")

FOTOS = os.path.join(DATA_DIR, "fotos")
CLIPS = os.path.join(DATA_DIR, "clips")
CLASES = {0: "persona", 2: "carro", 3: "moto", 7: "carro", 15: "gato", 16: "perro"}

_previo = {}
_ultima = {}
_grabando = {}
_camaras_cache = []
modelo = None

def ruta_foto(base, cid, t, clases):
    fecha = time.strftime("%Y-%m-%d", time.localtime(t))
    hora = time.strftime("%H-%M-%S", time.localtime(t))
    return os.path.join(base, fecha, f"{cid}_{hora}_{'-'.join(clases)}.jpg")

def parsear_camaras(datos):
    if not isinstance(datos, list):
        return None
    camaras_filtradas = []
    for c in datos:
        if isinstance(c, dict) and "id" in c:
            camaras_filtradas.append(c)
    return camaras_filtradas

def leer_camaras(cache, get=None, url=None, token=None):
    if get is None:
        import requests
        get = requests.get
    if url is None:
        url = PANEL_URL + "/api/interno/camaras"
    if token is None:
        token = INTERNO_TOKEN
    try:
        r = get(url, headers={"Authorization": "Bearer " + token}, timeout=5)
        datos = r.json()
        parsed = parsear_camaras(datos)
        if parsed is not None:
            return parsed
    except Exception:
        pass
    return cache

def foto(cid):
    import requests
    import numpy as np
    import cv2
    try:
        r = requests.get(f"{GO2RTC_URL}/api/frame.jpeg", params={"src": cid}, timeout=15)
        return cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None

def mascara_movimiento(cid, img):
    import numpy as np
    import cv2
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gris.shape
    nw = 320
    nh = int(h * (nw / w))
    gris = cv2.resize(gris, (nw, nh))
    gris = cv2.GaussianBlur(gris, (5, 5), 0)
    
    if cid not in _previo or _previo[cid].shape != gris.shape:
        _previo[cid] = gris
        return None
    
    diff = cv2.absdiff(_previo[cid], gris)
    _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, None, iterations=2)
    _previo[cid] = gris
    return mask

def movimiento_en(mascara, caja, ancho_original):
    import numpy as np
    x1, y1, x2, y2 = caja
    f = mascara.shape[1] / ancho_original
    mx1, my1 = max(0, int(x1 * f)), max(0, int(y1 * f))
    mx2, my2 = min(mascara.shape[1], int(x2 * f)), min(mascara.shape[0], int(y2 * f))
    if mx2 <= mx1 or my2 <= my1:
        return 0
    roi = mascara[my1:my2, mx1:mx2]
    return np.count_nonzero(roi) / roi.size

def grabar_clip(cid, fecha, hora):
    if CLIP_SEG <= 0:
        return
    if _grabando.get(cid) and _grabando[cid].poll() is None:
        return
    ruta = os.path.join(CLIPS, fecha, f"{cid}_{hora}_persona.mp4")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-rtsp_transport", "tcp",
        "-i", f"{RTSP_URL}/{cid}", "-t", str(CLIP_SEG), "-map", "0:v:0",
        "-map", "0:a:0?", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart",
        "-y", ruta
    ]
    try:
        _grabando[cid] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info(f"{cid}: grabando clip {CLIP_SEG}s")
    except OSError as e:
        log.warning("Error iniciando ffmpeg: %s", e)

def procesar(c):
    import numpy as np
    import cv2
    cid = c["id"]
    img = foto(cid)
    if img is None:
        return
    
    m = mascara_movimiento(cid, img)
    if m is None or np.count_nonzero(m) / m.size < MOVIMIENTO:
        return
    
    res = modelo(img, conf=CONFIANZA, classes=list(CLASES), verbose=False)[0]
    detecciones = []
    for b in res.boxes:
        cls_id = int(b.cls)
        caja = b.xyxy[0].tolist()
        if movimiento_en(m, caja, img.shape[1]) >= 0.02:
            detecciones.append(CLASES[cls_id])
    
    if not detecciones:
        return
        
    clases_detectadas = sorted(list(set(detecciones)))
    ahora = time.time()
    validas = [cls for cls in clases_detectadas if ahora - _ultima.get((cid, cls), 0) >= ENFRIAMIENTO]
    
    if validas:
        for cls in validas:
            _ultima[(cid, cls)] = ahora
        
        img_plot = res.plot()
        path = ruta_foto(FOTOS, cid, ahora, validas)
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cv2.imwrite(path, img_plot)
        if "persona" in validas:
            fecha = time.strftime("%Y-%m-%d", time.localtime(ahora))
            hora = time.strftime("%H-%M-%S", time.localtime(ahora))
            grabar_clip(cid, fecha, hora)
        log.info(f"{cid}: {'-'.join(validas)}")

def limpiar(bases=None, horas=None, ahora=None):
    if bases is None:
        bases = (FOTOS, CLIPS)
    if horas is None:
        horas = RETENCION_HORAS
    if ahora is None:
        ahora = time.time()
    limite = ahora - horas * 3600
    for base in bases:
        if not os.path.exists(base):
            continue
        try:
            subdirs = os.listdir(base)
        except OSError:
            continue
        for d in subdirs:
            folder = os.path.join(base, d)
            if not os.path.isdir(folder):
                continue
            try:
                files = os.listdir(folder)
            except OSError:
                continue
            for f in files:
                p = os.path.join(folder, f)
                try:
                    mt = os.path.getmtime(p)
                    if mt < limite:
                        os.remove(p)
                except OSError:
                    pass
            try:
                if not os.listdir(folder):
                    os.rmdir(folder)
            except OSError:
                pass

def fotos_entre(desde, hasta, base=None):
    if base is None:
        base = FOTOS
    fotos = []
    if not os.path.exists(base):
        return []
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".jpg"):
                continue
            p = os.path.join(root, f)
            mt = os.path.getmtime(p)
            if desde <= mt < hasta:
                name = f[:-4]
                cid = name.split("_")[0]
                clases = name.split("_")[-1].split("-")
                fotos.append({"path": p, "mtime": mt, "cid": cid, "clases": clases})
    return sorted(fotos, key=lambda x: x["mtime"])

def main():
    global modelo, _camaras_cache
    from ultralytics import YOLO
    modelo = YOLO(MODELO)
    limpiar()
    proxima_limpieza = time.time() + 600

    while True:
        _camaras_cache = leer_camaras(_camaras_cache)
        for c in _camaras_cache:
            try:
                procesar(c)
            except Exception:
                log.exception("procesar: fallo")
        
        ahora = time.time()
        if ahora >= proxima_limpieza:
            limpiar()
            proxima_limpieza = ahora + 600
        
        time.sleep(INTERVALO)

if __name__ == "__main__":
    main()
