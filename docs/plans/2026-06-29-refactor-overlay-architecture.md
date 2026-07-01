# Overlay Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the overlay app into focused modules so capture, change detection, and platform UI each have a single responsibility.

**Architecture:** Keep pure logic in small testable modules under `src/hakunamatata/`. Put screen capture and bitmap parsing in one module, hash and color logic in another, and platform UI in separate macOS/Windows modules. `punto_rojo.py` should become a thin entry point that dispatches to the right platform implementation.

**Tech Stack:** Python 3.12, `uv`, standard library, `tkinter` on Windows, `PyObjC` on macOS.

### Task 1: Extract pure detection logic

**Files:**
- Create: `src/hakunamatata/detection.py`
- Modify: `punto_rojo.py`
- Test: `tests/test_detection.py`

**Step 1: Write the failing test**

Add tests for `crear_huella_visual`, `color_desde_paso`, and `actualizar_estado`.

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_detection -v`
Expected: FAIL because module does not exist yet.

**Step 3: Write minimal implementation**

Move the exact-hash and color functions into `src/hakunamatata/detection.py`.

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_detection -v`
Expected: PASS.

### Task 2: Extract capture helpers

**Files:**
- Create: `src/hakunamatata/capture.py`
- Modify: `punto_rojo.py`
- Test: `tests/test_capture.py`

**Step 1: Write the failing test**

Add tests for `ocultar_region()` and any pixel-to-BMP parsing helper that can be tested with a tiny synthetic BMP.

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_capture -v`
Expected: FAIL because module does not exist yet.

**Step 3: Write minimal implementation**

Move `leer_bmp`, `ocultar_region`, and capture helpers into `capture.py`.

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_capture -v`
Expected: PASS.

### Task 3: Split platform UI

**Files:**
- Create: `src/hakunamatata/ui/macos.py`
- Create: `src/hakunamatata/ui/windows.py`
- Create: `src/hakunamatata/ui/__init__.py`
- Modify: `punto_rojo.py`

**Step 1: Write the failing test**

Add a small test for platform dispatch if practical, or keep this task verified by import/run only.

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest discover -s tests -v`
Expected: existing tests still pass, imports fail until the new modules exist.

**Step 3: Write minimal implementation**

Move macOS AppKit code to `ui/macos.py` and Windows Tkinter code to `ui/windows.py`.

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest discover -s tests -v`
Expected: PASS.

### Task 4: Thin entrypoint and verification

**Files:**
- Modify: `punto_rojo.py`
- Modify: `README.md` if command changes

**Step 1: Write the failing test**

No extra test required; use runtime verification.

**Step 2: Run test to verify it fails**

Run: `uv run python punto_rojo.py`
Expected: the app should still launch; failure means imports or dispatch are broken.

**Step 3: Write minimal implementation**

Make `punto_rojo.py` only call the platform launcher.

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest discover -s tests -v && uv run python punto_rojo.py`
Expected: tests pass and app launches.
