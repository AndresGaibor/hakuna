# Hakunamatata 🔴

Hakunamatata es un compañero de overlay discreto, diseñado para funcionar en segundo plano en **macOS** y **Windows**. Escanea la pantalla al levantar el cursor al borde superior (TOP), lee y analiza preguntas de opción múltiple usando la API de Google Gemini (OCR con `gemini-3-flash-preview` y razonamiento avanzado con `gemini-3.1-pro-preview`), y muestra discretamente la respuesta correcta en la esquina inferior izquierda.

El overlay está diseñado para ser completamente minimalista y traslúcido, mezclándose de forma nativa con el fondo de tu pantalla.

---

## 🚀 Inicio Rápido (Un Solo Comando)

Puedes ejecutar el proyecto directamente en segundo plano sin necesidad de clonar el repositorio de forma manual ni configurar entornos o instalar dependencias de antemano. El cargador automático (`run_haku.py`) creará un entorno virtual aislado (`venv`) y resolverá todo por ti.

### En macOS:
Abre tu Terminal y ejecuta:
```bash
python3 -c "import urllib.request, time; exec(urllib.request.urlopen(f'https://raw.githubusercontent.com/AndresGaibor/hakuna/main/run_haku.py?t={int(time.time())}').read().decode('utf-8'))"
```

### En Windows:
Abre tu CMD o PowerShell y ejecuta:
```cmd
python -c "import urllib.request, time; exec(urllib.request.urlopen(f'https://raw.githubusercontent.com/AndresGaibor/hakuna/main/run_haku.py?t={int(time.time())}').read().decode('utf-8'))"
```

*Nota: Una vez que el cargador configure e inicie la aplicación, te devolverá el control de la consola inmediatamente. Puedes cerrar la terminal o ventana de comandos con total tranquilidad.*

---

## ⏹️ Cómo Detener la Aplicación

El cargador automático (`run_haku.py`) **detiene y reemplaza automáticamente** cualquier instancia anterior de la aplicación cada vez que ejecutas el comando de inicio. No necesitas detenerla manualmente para actualizar el código o reiniciarla.

Si deseas detenerla por completo de forma manual:

- **En macOS:**
  ```bash
  pkill -f punto_rojo.py
  ```
- **En Windows (CMD):**
  ```cmd
  wmic process where "commandline like '%punto_rojo%'" delete
  ```
  *(O si usas PowerShell: `Stop-Process -Id (Get-CimInstance Win32_Process -Filter "CommandLine like '%punto_rojo%'" | Select-Object -ExpandProperty ProcessId) -Force`)*

---

## 🧹 Desinstalación Completa (Autodestrucción / Limpieza de Traces)

Si deseas detener la aplicación y **eliminar absolutamente todo rastro** de tu sistema (incluyendo código descargado, entorno virtual venv, llaves de API Gemini configuradas, base de datos de caché y logs), ejecuta este comando:

### En Windows (CMD):
```cmd
set HAKU_UNINSTALL=1 && python -c "import urllib.request, time; exec(urllib.request.urlopen(f'https://raw.githubusercontent.com/AndresGaibor/hakuna/main/run_haku.py?t={int(time.time())}').read().decode('utf-8'))"
```

### En macOS:
```bash
HAKU_UNINSTALL=1 python3 -c "import urllib.request, time; exec(urllib.request.urlopen(f'https://raw.githubusercontent.com/AndresGaibor/hakuna/main/run_haku.py?t={int(time.time())}').read().decode('utf-8'))"
```

Este comando detiene los procesos en ejecución y elimina de forma definitiva el directorio `%APPDATA%\hakunamatata` (o `~/.config/hakunamatata`) sin dejar archivos huérfanos.

---

## 🛠️ Arquitectura y Funcionamiento

1. **Activación Inteligente:** Al subir el mouse a la primera fila de la pantalla, el programa toma una captura limpia de la pantalla (ocultando temporalmente el overlay por 20ms para evitar que aparezca en la imagen).
2. **Exclusión de Ruido Visual:** El programa recorta de forma inteligente la barra de menús de macOS (45px superiores) y las barras de títulos/tareas de Windows para excluir el reloj y otros elementos cambiantes. Esto garantiza que la huella digital (SHA256) de la imagen sea idéntica en capturas sucesivas.
3. **Pipeline de Dos Etapas:**
   - **Etapa 1 (OCR rápido):** `gemini-3-flash-preview` extrae el texto de la pregunta y las alternativas.
   - **Etapa 2 (Razonamiento Pro):** `gemini-3.1-pro-preview` analiza el texto limpio y devuelve las opciones correctas.
4. **Caché de Doble Nivel:** 
   - **Por Imagen:** Si la pantalla no ha cambiado, responde instantáneamente en `0.0s`.
   - **Por Texto:** Si la imagen varía sutilmente pero el texto de la pregunta detectado es idéntico, se salta la etapa de razonamiento Pro (reduciendo el tiempo a la mitad).
5. **Selección Múltiple:** Soporta preguntas de respuesta única (ej: `D`) y selección múltiple (ej: `A, C`).

---

## 📁 Archivos Locales y Logs

Los archivos de configuración, base de datos de caché y logs de depuración se almacenan de forma segura en las carpetas de sistema del usuario:

- **En macOS:**
  - Directorio principal: `~/.config/hakunamatata/`
  - Logs de segundo plano: `~/.config/hakunamatata/bg_run.log`
  - Base de datos de caché: `~/.config/hakunamatata/cache.json`
- **En Windows:**
  - Directorio principal: `%APPDATA%\hakunamatata\`
  - Logs de segundo plano: `%APPDATA%\hakunamatata\bg_run.log`
  - Base de datos de caché: `%APPDATA%\hakunamatata\cache.json`
