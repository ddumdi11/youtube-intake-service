"""Import-Reinheit: der Core darf fastapi/uvicorn NICHT mitziehen.

Wir starten einen frischen Interpreter, damit das Ergebnis unabhaengig davon ist,
was der Test-Runner sonst bereits importiert hat.
"""

import subprocess
import sys


def test_core_does_not_import_server_stack():
    code = (
        "import youtube_intake_core, sys; "
        "assert 'fastapi' not in sys.modules, 'fastapi wurde mitgeladen'; "
        "assert 'uvicorn' not in sys.modules, 'uvicorn wurde mitgeladen'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Core ist nicht server-frei.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
