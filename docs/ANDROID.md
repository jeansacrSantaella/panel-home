# App Android (APK)

PleyadesHome para Android: muestra el panel de la casa en pantalla completa y deja **agregar o cambiar la
dirección del panel** cuando la casa cambia de IP. Es nativa (Kotlin, sin librerías), pesa menos de 1 MB y vive en `android/`.

## Qué hace

- **Pantalla de inicio**: las Pléyades se dibujan trazo a trazo mientras se conecta.
- **Varias direcciones**: por ejemplo "Casa" (`192.168.1.50`) y "Fuera de casa" (`https://mi-dominio`).
  Al abrir prueba primero la que está en uso y luego las demás; se queda con la primera que responda a `/salud`.
- **Si la IP cambió**: cuando ninguna responde, busca el panel en la red WiFi (puerto 8770, toda la red /24, unos
  segundos) y, si lo encuentra, actualiza la dirección sola y avisa "La casa cambió de IP".
- **Si no lo encuentra**: pantalla "No encuentro el panel" con *Reintentar* y *Cambiar dirección*.
- **Al volver a la app** tras más de un minuto, comprueba que el panel siga respondiendo; si no, lo busca de nuevo.
- **Pantalla Servidores**: agregar, editar, quitar, elegir cuál usar, *Buscar en la red* y *Probar conexión*.
  Se abre desde el panel (menú de la cuenta → *Cambiar servidor de la app*), desde el inicio de sesión
  (*Cambiar servidor de la app*) o desde la pantalla de error. Esos botones solo aparecen dentro de la app.
- Las cámaras arrancan **en silencio**, igual que en Chrome (la app exige un toque para reproducir con sonido).
  El botón 🔇/🔊 de cada video activa o quita el audio; en la pestaña Cámaras de gestorCamaras está su botón "🔇 Audio".
- Descargas de capturas (van a *Descargas*) y la sesión se conserva entre aperturas.

Al escribir una dirección basta la IP: `192.168.1.50` se guarda como `http://192.168.1.50:8770`. Si se escribe
con `http://` o `https://`, se respeta tal cual (útil para un dominio o un proxy sin puerto).

> Al cambiar de dirección el navegador de la app la trata como otro sitio: hay que **iniciar sesión otra vez** una vez.

## Instalar en el celular

1. Copia `PleyadesHome.apk` al celular (cable, Drive, Telegram…).
2. Ábrelo y acepta "Instalar apps de origen desconocido" si lo pide.
3. La primera vez pide la dirección del panel: escribe la IP de la Lenovo (o toca *Buscar en la red* con el
   celular en el WiFi de la casa).

## Compilar el APK

Requiere JDK 17 y el SDK de Android (en la Mac: `brew install --cask android-commandlinetools`, luego
`sdkmanager "platforms;android-35" "build-tools;35.0.0" "platform-tools"`). `android/local.properties` apunta al SDK.

```sh
cd android
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew assembleRelease   # app/build/outputs/apk/release/app-release.apk
./gradlew testDebugUnitTest                                          # pruebas de la normalización de direcciones
```

El APK de *release* va firmado con la llave de depuración (se instala directo, no es para la tienda).
Para publicar una versión nueva sube `versionCode`/`versionName` en `android/app/build.gradle.kts`.

## Archivos

| Archivo | Qué hace |
|---|---|
| `Servidores.kt` | lista de direcciones y la activa (SharedPreferences), `normalizar()` |
| `Sondeo.kt` | `/salud`, prueba en paralelo, IP local y búsqueda en la red |
| `MainActivity.kt` | WebView del panel, arranque, error, descargas, puente `window.PleyadesApp` |
| `AjustesActivity.kt` | pantalla Servidores |
| `ConstelacionView.kt` | pantalla de inicio animada |

Puente JS: `window.PleyadesApp.servidores()` abre la pantalla Servidores y `window.PleyadesApp.version()` da la versión.
La app agrega ` PleyadesHomeApp/1.0` al User-Agent.
