# Imagen base Python slim
FROM python:3.12-slim

# Instala tzdata para el manejo de hora local en nombres de fotos
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1 PANEL_HOST=0.0.0.0 PANEL_PORT=8770 PANEL_DB=/data/panel.db

WORKDIR /app

# Copia de código fuente
COPY main.py .
COPY panel/ ./panel/
COPY static/ ./static/

VOLUME /data
EXPOSE 8770

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8770/api/panel', timeout=4)"

CMD ["python", "main.py"]
