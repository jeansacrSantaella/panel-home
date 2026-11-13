# Red: sonda + panel-home (contrato)

La red se mide desde **fuera de Docker** (la tabla ARP y las MAC solo se ven en la red de la casa) y se procesa en
**panel-home**. Reemplaza a NetWatch (`../analizadorRed/NetWhatch`, copia de referencia en `docs/origen/netwatch/`).

```
sonda/  (fuera de Docker, sin dependencias)          panel-home (Docker)
  mide: ping, DNS, ARP, IP pública, velocidad  ──POST /api/interno/red──▶  panel/red/: estado, base, eventos,
  junta lecturas y las manda cada 15 s                                    resumen (= /api/summary de NetWatch),
  si el panel no responde, las guarda y reintenta                         escáner, alias, CSV, avisos
```

- La **sonda** solo mide. No guarda base, no decide caídas, no avisa.
- **panel-home** aplica las reglas de NetWatch (3 fallos = caída, 3 escaneos sin ver un equipo = desconectado,
  pausa si hay hueco > 4 sondeos), guarda en `panel.db` y arma el mismo resumen que `/api/summary`, así el resto
  del panel (recolector, mapa, caídas, línea de tiempo) no cambia.
- Si no llegan lecturas en 90 s, `fuentes.netwatch_resumen()` devuelve `None` → evento `fuente_caida` "Red".
- El escáner de un equipo (puertos, ping, TTL, DNS) corre en panel-home: TCP e ICMP sí cruzan el NAT de Docker.

## `POST /api/interno/red`

Cabecera `Authorization: Bearer <RED_TOKEN>` (comparación en tiempo constante; sin token configurado la ruta
responde 404). Cuerpo JSON ≤ 2 MB:

```json
{"sonda": "lenovo", "version": 1, "enviado": 1794581858, "lecturas": [ ... ]}
```

Respuesta `200 {"ok": true, "recibidas": n}` · `401` token malo · `400` JSON inválido.
El panel procesa las lecturas en orden de `ts`. Una lectura con tipo desconocido se ignora.

### Lecturas

| `t` | Cada | Campos |
|---|---|---|
| `sondeo` | 5 s | `ts`, `gateway` (IP o null), `resultados`: `[{"kind": "ping"\|"dns", "target": "gateway"\|"1.1.1.1"\|"8.8.8.8", "ok": bool, "ms": float\|null}]` |
| `escaneo` | 120 s | `ts`, `base` ("192.168.1"), `propia` (IP de la sonda), `equipos`: `{"aa:bb:cc:dd:ee:ff": {"ip": "192.168.1.50", "hostname": "x" \| null}}` (MAC en minúsculas, solo de la /24) |
| `calidad` | 30 s | `ts`, `resultados`: `[{"mac", "ip", "ok": bool, "ms": float\|null}]` (equipos del último escaneo) |
| `ip_publica` | 300 s | `ts`, `ip` |
| `velocidad` | 3600 s (solo si el último sondeo tuvo internet) | `ts`, `down`, `up` (Mbps) |

`target` usa los mismos nombres que NetWatch (`"gateway"` para el router) para que las consultas de disponibilidad
sean idénticas.

## Tablas en `panel.db` (mismas columnas que NetWatch, con prefijo `red_`)

```
red_equipos(mac PK, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses DEFAULT 0, network)
red_sondeos(ts, kind, target, ok, ms)      -- kind: ping | dns | dev ; índice por ts
red_eventos(ts, kind, detail)              -- kinds de NetWatch: lan_down lan_up wan_down wan_up dns_down dns_up
                                           --   new_device ip_change ip_first device_online device_offline monitor_gap
red_velocidad(ts, down, up)
estado: "red:ip_publica", "red:ultimo_sondeo", "red:ultima_lectura", "red:servicios"
```

Retención: sondeos 30 días; eventos, equipos y velocidad sin límite (como NetWatch).

## Configuración

| Variable | Dónde | Qué |
|---|---|---|
| `RED_INTERNA=1` | panel-home | usa la red interna en vez de leer NetWatch por HTTP |
| `RED_TOKEN` | panel-home y sonda | secreto compartido (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `--panel`, `--token`, `--nombre` | sonda | `python3 -m sonda --panel http://192.168.1.94:8770 --token ...` |

## Windows (la .94)

La sonda corre nativa en Windows (en español o inglés): `ping -n`, `arp -a` (varias interfaces, incluidas las
vEthernet de WSL/Docker), `route print` (ruta por defecto de menor métrica), salida decodificada con la página OEM.
Lee `RED_TOKEN` del `.env` del repo y apunta por defecto a `http://127.0.0.1:8770`. Instalación como tarea
programada (SYSTEM, al iniciar, se reinicia sola): [SONDA_WINDOWS.md](SONDA_WINDOWS.md).
