from __future__ import annotations

import os
import sys
import subprocess
import urllib.request
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


def instalar_dependencias():
    log("Verificando dependencias necesarias...")
    libs = ["google-genai", "Pillow"]
    if sys.platform == "darwin":
        libs.extend(["pyobjc-core", "pyobjc-framework-Cocoa"])

    for lib in libs:
        try:
            if lib == "Pillow":
                import PIL
            elif lib == "google-genai":
                import google.genai
            elif lib.startswith("pyobjc"):
                import objc
            else:
                __import__(lib)
        except ImportError:
            log(f"Instalando {lib}...")
            # Usar sys.executable para correr pip del entorno actual
            subprocess.run([sys.executable, "-m", "pip", "install", lib], check=True)


def descargar_y_extraer_codigo(app_dir: str):
    log("Descargando código fuente desde GitHub...")
    zip_url = "https://github.com/AndresGaibor/aliware-calidad/archive/refs/heads/main.zip"

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")

        # Descargar zip
        urllib.request.urlretrieve(zip_url, zip_path)

        # Extraer en el directorio temporal
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # El directorio extraído es aliware-calidad-main
        extracted_dir = os.path.join(tmpdir, "aliware-calidad-main")
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


def ejecutar_en_segundo_plano(app_dir: str):
    punto_rojo_path = os.path.join(app_dir, "punto_rojo.py")
    src_dir = os.path.join(app_dir, "src")

    # Preparar el PYTHONPATH para incluir 'src'
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.pathsep.join([src_dir, env.get("PYTHONPATH", "")])

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

        # Cambiar directorio de trabajo y ejecutar
        os.chdir(app_dir)
        sys.path.insert(0, src_dir)

        from hakunamatata.gemini import crear_cliente
        from hakunamatata.ui import main

        try:
            cliente = crear_cliente()
        except Exception:
            cliente = None

        main(cliente)

    elif sys.platform.startswith("win"):
        log("Lanzando en segundo plano para Windows...")
        pythonw = sys.executable.lower().replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable

        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [pythonw, punto_rojo_path],
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
    instalar_dependencias()
    descargar_y_extraer_codigo(app_dir)
    ejecutar_en_segundo_plano(app_dir)


if __name__ == "__main__":
    main()
