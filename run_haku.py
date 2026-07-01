from __future__ import annotations

import json
import os
import sys
import subprocess
import urllib.request
import venv
import zipfile
import shutil
import tempfile


def log(msg: str):
    print(f"[HAKU] {msg}", flush=True)


def obtener_ruta_app() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "app")


def obtener_ruta_venv() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "venv")


def instalar_dependencias(venv_dir: str) -> str:
    log("Verificando entorno virtual (venv)...")
    if not os.path.exists(venv_dir):
        log("Creando entorno virtual para aislar dependencias (PEP 668)...")
        # En macOS forzamos symlinks=True para heredar los permisos de Screen Recording
        # del binario de Python global. En otras plataformas usamos el comportamiento por defecto.
        usar_symlinks = (sys.platform == "darwin")
        venv.create(venv_dir, with_pip=True, symlinks=usar_symlinks)
        log("Entorno virtual creado con éxito.")

    # Obtener el binario de python del venv
    if sys.platform.startswith("win"):
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    # Asegurar que venv_python existe
    if not os.path.exists(venv_python):
        raise FileNotFoundError(f"No se encontró el ejecutable de Python en el venv: {venv_python}")

    libs = ["google-genai", "Pillow"]
    if sys.platform == "darwin":
        libs.extend(["pyobjc-core", "pyobjc-framework-Cocoa", "pyobjc-framework-Quartz"])

    for lib in libs:
        # Mapear importación de biblioteca para probar si está instalada en el venv
        if lib == "Pillow":
            lib_import = "PIL"
        elif lib == "google-genai":
            lib_import = "google.genai"
        elif lib == "pyobjc-core":
            lib_import = "objc"
        elif lib == "pyobjc-framework-Cocoa":
            lib_import = "Cocoa"
        elif lib == "pyobjc-framework-Quartz":
            lib_import = "Quartz"
        else:
            lib_import = lib

        # Comprobar si la biblioteca se puede importar en el venv
        test_cmd = [venv_python, "-c", f"import {lib_import}"]
        res = subprocess.run(test_cmd, capture_output=True)
        if res.returncode != 0:
            log(f"Instalando {lib} dentro del entorno virtual...")
            # Correr pip dentro del venv de forma segura sin contaminar el sistema
            subprocess.run([venv_python, "-m", "pip", "install", lib], check=True)

    return venv_python


def descargar_y_extraer_codigo(app_dir: str):
    log("Descargando código fuente desde GitHub...")
    zip_url = "https://github.com/AndresGaibor/hakuna/archive/refs/heads/main.zip"

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")

        # Descargar zip
        urllib.request.urlretrieve(zip_url, zip_path)

        # Extraer en el directorio temporal
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # El directorio extraído es hakuna-main
        extracted_dir = os.path.join(tmpdir, "hakuna-main")
        haku_src = os.path.join(extracted_dir, "python", "hakunamatata")

        # Detección inteligente de la estructura del repositorio (anidado vs raíz)
        if not os.path.exists(haku_src):
            haku_src = extracted_dir

        if os.path.exists(app_dir):
            # En Windows el proceso de fondo (pythonw.exe) mantiene app_dir como
            # directorio de trabajo, por lo que el SO bloquea el directorio y
            # shutil.rmtree falla con PermissionError (WinError 32).
            # Solución: copiar encima sin borrar el directorio padre.
            shutil.copytree(haku_src, app_dir, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(app_dir), exist_ok=True)
            shutil.move(haku_src, app_dir)
        log("Código instalado en el directorio local de la app.")


def ejecutar_en_segundo_plano(app_dir: str, venv_python: str):
    terminar_instancia_previa()

    punto_rojo_path = os.path.join(app_dir, "punto_rojo.py")
    src_dir = os.path.join(app_dir, "src")
    venv_dir = os.path.dirname(os.path.dirname(venv_python))

    # Preparar el PYTHONPATH y el entorno virtual activado
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.pathsep.join([src_dir, env.get("PYTHONPATH", "")])
    env["VIRTUAL_ENV"] = venv_dir
    # Forzar UTF-8 para evitar UnicodeEncodeError con caracteres como ✓ ✗ en Windows (cp1252)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Quitar PYTHONHOME si está configurado para evitar conflictos de bibliotecas estándar
    env.pop("PYTHONHOME", None)

    if sys.platform == "darwin":
        log("Lanzando en segundo plano para macOS...")
        try:
            pid = os.fork()
            if pid > 0:
                log(f"Iniciado en segundo plano con PID {pid}. Puedes cerrar esta terminal.")
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork fallido: {e}\n")
            sys.exit(1)

        os.setsid()

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork 2 fallido: {e}\n")
            sys.exit(1)

        # Redirigir stdout/stderr a archivo de log en la carpeta de la app para ver depuración
        log_path = os.path.join(os.path.dirname(app_dir), "bg_run.log")
        log_file = open(log_path, "a")
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        os.dup2(log_file.fileno(), sys.stderr.fileno())

        # Cambiar directorio de trabajo y reemplazar el proceso usando execve de Unix
        os.chdir(app_dir)
        os.execve(venv_python, [venv_python, punto_rojo_path], env)

    elif sys.platform.startswith("win"):
        log_path = os.path.join(os.path.dirname(app_dir), "bg_run.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # Buscar el ejecutable de Python del venv: python.exe → pythonw.exe → fallback
        scripts_dir = os.path.join(venv_dir, "Scripts")
        for candidato in ["python.exe", "pythonw.exe"]:
            ruta_candidato = os.path.join(scripts_dir, candidato)
            if os.path.exists(ruta_candidato):
                venv_python_exe = ruta_candidato
                break
        else:
            venv_python_exe = venv_python  # fallback al python que ya sabemos que existe

        log(f"Ejecutable: {venv_python_exe}")
        log(f"Script    : {punto_rojo_path}")
        log(f"Log       : {log_path}")

        try:
            log_file = open(log_path, "a", encoding="utf-8")
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                [venv_python_exe, "-u", punto_rojo_path],
                cwd=app_dir,
                env=env,
                creationflags=DETACHED_PROCESS,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
            )
            log(f"Iniciado en segundo plano (PID {proc.pid}). Log → {log_path}")
        except Exception as e:
            log(f"ERROR al lanzar proceso de fondo: {e}")
            raise

    else:
        log("Plataforma no soportada para segundo plano.")


def terminar_instancia_previa():
    """Mata cualquier instancia anterior de punto_rojo.py que siga corriendo."""
    if sys.platform.startswith("win"):
        # Filtrar directamente en WMIC por commandline para evitar falsos positivos
        try:
            result = subprocess.run(
                ["wmic", "process",
                 "where", "commandline like '%punto_rojo%'",
                 "get", "processid", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.lower().startswith("node"):
                    continue
                # Formato CSV: Node,ProcessId
                partes = line.split(",")
                pid = partes[-1].strip()
                if pid.isdigit() and int(pid) != os.getpid():
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True)
                    log(f"Instancia previa terminada (PID {pid}).")
        except Exception as e:
            log(f"Aviso: no se pudo verificar instancias previas: {e}")
    else:
        # En macOS/Linux usamos pkill
        try:
            subprocess.run(["pkill", "-f", "punto_rojo.py"], capture_output=True)
            log("Instancia previa terminada (pkill).")
        except Exception:
            pass


def ejecutar_en_primer_plano(app_dir: str, venv_python: str):
    """Modo debug: mata instancia previa y lanza punto_rojo.py en el mismo terminal con logs visibles."""
    terminar_instancia_previa()

    punto_rojo_path = os.path.join(app_dir, "punto_rojo.py")
    src_dir = os.path.join(app_dir, "src")
    venv_dir = os.path.dirname(os.path.dirname(venv_python))

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.pathsep.join([src_dir, env.get("PYTHONPATH", "")])
    env["VIRTUAL_ENV"] = venv_dir
    env.pop("PYTHONHOME", None)
    # Forzar salida sin buffer para que los logs aparezcan en tiempo real
    env["PYTHONUNBUFFERED"] = "1"

    log("Modo DEBUG — ejecutando en primer plano con logs en tiempo real...")
    log(f"  Script : {punto_rojo_path}")
    log(f"  Python : {venv_python}")
    log(f"  Src    : {src_dir}")
    log("Presiona Ctrl+C para detener.")
    print(flush=True)

    # En Windows subprocess.run bloquea el terminal (primer plano real)
    if sys.platform.startswith("win"):
        proc = subprocess.run(
            [venv_python, "-u", punto_rojo_path],
            cwd=app_dir,
            env=env,
        )
        sys.exit(proc.returncode)
    else:
        os.chdir(app_dir)
        os.execve(venv_python, [venv_python, "-u", punto_rojo_path], env)



def _ruta_config() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "config.json")


def _leer_api_key_guardada() -> str | None:
    try:
        with open(_ruta_config(), encoding="utf-8") as f:
            return json.load(f).get("api_key")
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _guardar_api_key(api_key: str) -> None:
    ruta = _ruta_config()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f)
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass


def solicitar_api_key() -> None:
    """Pide la API key al usuario en la terminal visible y la persiste en disco.

    Solo solicita si no hay ya una clave guardada o en variable de entorno.
    """
    # Ya existe en variable de entorno → no hace falta pedir nada
    if os.environ.get("GEMINI_API_KEY"):
        log("API key detectada en variable de entorno GEMINI_API_KEY.")
        return

    # Ya existe guardada en disco → tampoco pedir
    if _leer_api_key_guardada():
        log("API key encontrada en configuración guardada.")
        return

    # No hay clave: pedir al usuario ahora, en este terminal visible
    print()
    print("==========================================")
    print("  HAKUNAMATATA - Configuración inicial")
    print("==========================================")
    print()
    print("Necesitas una API key de Google Gemini para continuar.")
    print("Obtén una gratis en: https://aistudio.google.com/apikey")
    print()

    while True:
        try:
            key = input("Ingresa tu API key de Gemini: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nInstalación cancelada.")
            sys.exit(0)

        if key:
            break
        print("La API key no puede estar vacía. Inténtalo de nuevo.")

    _guardar_api_key(key)
    log(f"API key guardada en: {_ruta_config()}")


def _ruta_flag_debug() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "hakunamatata", "debug.flag")


def main():
    # Modo debug si existe el archivo flag O la variable de entorno (con .strip() por Windows cmd)
    flag_file = os.path.exists(_ruta_flag_debug())
    env_var = bool(os.environ.get("HAKU_DEBUG", "").strip())
    debug = "--debug" in sys.argv or flag_file or env_var

    log(f"[diag] HAKU_DEBUG={os.environ.get('HAKU_DEBUG', '')!r}  flag_file={flag_file}  debug={debug}")

    app_dir = obtener_ruta_app()
    venv_dir = obtener_ruta_venv()

    # 0. Pedir API key antes de hacer cualquier otra cosa
    solicitar_api_key()

    # 1. Instalar dependencias en el venv aislado
    venv_python = instalar_dependencias(venv_dir)

    # 2. Descargar código limpio
    descargar_y_extraer_codigo(app_dir)

    # 3. Lanzar proceso
    if debug:
        ejecutar_en_primer_plano(app_dir, venv_python)
    else:
        ejecutar_en_segundo_plano(app_dir, venv_python)


# Ejecutar siempre, tanto en invocación directa como a través de exec() del one-liner
main()
