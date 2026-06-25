import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def main() -> int:
    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        print("PyInstaller ist nicht installiert. Installiere zuerst requirements.txt.")
        return 1

    command = [
        pyinstaller,
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "youtube-intake-service",
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "youtube_transcript_api",
        str(PROJECT_ROOT / "main.py"),
    ]

    print("Starte Build:")
    print(" ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if result.returncode == 0:
        print(f"Build erfolgreich. Ausgabe liegt in: {DIST_DIR}")
    else:
        print(f"Build fehlgeschlagen. Prüfe Build-Artefakte in: {BUILD_DIR}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
