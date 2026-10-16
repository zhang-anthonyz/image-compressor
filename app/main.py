"""PixelPress entry point.

``--headless`` runs the packaging self-check and exits without opening a window
(see app/cli.py). Anything else starts the GUI.
"""
from __future__ import annotations

import os
import sys


def _configure_qt() -> None:
    """Set process-wide Qt attributes before QApplication exists."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def run_gui(argv: list[str]) -> int:
    from PySide6.QtWidgets import QApplication

    from .core.settings_store import SettingsStore
    from .ui import theme
    from .ui.main_window import MainWindow

    app = QApplication(argv)
    app.setApplicationName("PixelPress")
    app.setOrganizationName("PixelPress")
    # applicationDisplayName is intentionally left unset: Qt appends it to every
    # window title, which produced "PixelPress · … - PixelPress".

    store = SettingsStore().load()
    resolved = theme.apply_app_theme(app, store.theme_mode)

    window = MainWindow(store)
    window.set_theme(store.theme_mode, resolved)
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _configure_qt()

    if "--headless" in argv:
        # Never let the self-check raise: a frozen windowed build would answer an
        # unhandled exception with a modal traceback dialog, the process would
        # stay alive, and an automated acceptance run would look like a pass.
        try:
            from .cli import main as headless_main
        except Exception as exc:  # noqa: BLE001 - the point is to swallow it
            print(f"自检模块加载失败：{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        try:
            return headless_main(argv[1:])
        except Exception as exc:  # noqa: BLE001
            print(f"自检异常：{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    return run_gui(argv)


if __name__ == "__main__":
    sys.exit(main())
