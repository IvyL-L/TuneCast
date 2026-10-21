"""Точка входа для сборки TuneCast.exe (PyInstaller)."""

import sys

if sys.platform == "win32" and sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from tunecast.app import main  # noqa: E402

if __name__ == "__main__":
    main()
