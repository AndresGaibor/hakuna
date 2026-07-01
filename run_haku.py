from __future__ import annotations

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

        # Limpiar directorio de la app si ya existe para tener una instalación limpia
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir)
        os.makedirs(os.path.dirname(app_dir), exist_ok=True)

        # Mover los archivos a la ubicación de la app permanente
        shutil.move(haku_src, app_dir)
        log("Código instalado en el directorio local de la app.")


def ejecutar_en_segundo_plano(app_dir: str, venv_python: str):
    punto_rojo_path = os.path.join(app_dir, "punto_rojo.py")
    src_dir = os.path.join(app_dir, "src")
    venv_dir = os.path.dirname(os.path.dirname(venv_python))

    # Preparar el PYTHONPATH y el entorno virtual activado
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.pathsep.join([src_dir, env.get("PYTHONPATH", "")])
    env["VIRTUAL_ENV"] = venv_dir

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
        log("Lanzando en segundo plano para Windows...")
        # En Windows buscamos pythonw.exe en Scripts/
        venv_pythonw = os.path.join(venv_dir, "Scripts", "pythonw.exe")
        if not os.path.exists(venv_pythonw):
            venv_pythonw = venv_python

        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [venv_pythonw, punto_rojo_path],
            cwd=app_dir,
            env=env,
            creationflags=DETACHED_PROCESS,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        log("Iniciado en segundo plano en Windows. Puedes cerrar esta consola.")
    else:
        log("Plataforma no soportada para segundo plano.")


def main():
    app_dir = obtener_ruta_app()
    venv_dir = obtener_ruta_venv()

    # 1. Instalar dependencias en el venv aislado
    venv_python = instalar_dependencias(venv_dir)

    # 2. Descargar código limpio
    descargar_y_extraer_codigo(app_dir)

    # 3. Lanzar proceso desvinculado usando el python del venv
    ejecutar_en_segundo_plano(app_dir, venv_python)


if __name__ == "__main__":
    main()
