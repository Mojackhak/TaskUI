# Rhythm build scripts

This folder contains PyInstaller-based recipes to bundle the Rhythm GUI for macOS and Windows.

## Prerequisites
- Python 3 (same version you run the app with)
- PyInstaller installed in the current environment: `pip install pyinstaller`
- Pillow installed for Windows icon conversion: `pip install pillow`

## Build
### macOS (.app)
From the repository root:
```bash
chmod +x build/rhythm/build_rhythm_mac.sh
./build/rhythm/build_rhythm_mac.sh
```
This produces `build/rhythm/dist/Rhythm.app`. All build artifacts stay under `build/rhythm/`.

### Windows (.exe)
From the repository root with your environment activated (e.g., `conda activate ui`):
```powershell
.\build\rhythm\build_rhythm_win.ps1
```
This produces `build/rhythm/dist/Rhythm.exe` as a single-file GUI executable. The script auto-converts `rhythm/icon/icon.png` to `build/rhythm/icon.ico` (requires Pillow); if conversion fails or you provide your own `build/rhythm/icon.ico`, PyInstaller falls back accordingly.

## Notes
- The macOS script bundles the PNG icon at `rhythm/icon/icon.png`. If you have a macOS `.icns`, update `ICON_SRC` in the script and adjust the path.
- The Windows script auto-detects the active conda env (or `-PythonPath`), clears `PYTHONPATH` for the build to avoid contaminating PyInstaller, verifies PyInstaller is available, converts `rhythm/icon/icon.png` to `build/rhythm/icon.ico` when Pillow is installed, bundles the PNG via `--add-data` for the in-app window icon, and uses that `.ico` (or any existing `build/rhythm/icon.ico`). If none are available, PyInstaller falls back to the default icon.
- Sound playback must be available in your Python environment before running the build.
- The entry point is `rhythm/gui/gui.py`; adjust `ENTRYPOINT` in the script if you rename the launcher.
