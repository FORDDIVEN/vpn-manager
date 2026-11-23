"""Punto de entrada de la aplicación de escritorio."""
import os
import sqlite3
import sys


def main() -> int:
    if os.geteuid() == 0:
        print("VPN Manager debe ejecutarse como usuario normal, sin elevación de permisos.", file=sys.stderr)
        return 1
    from PySide6.QtWidgets import QApplication, QMessageBox
    from vpn_manager.gui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("VPN Manager")
    app.setDesktopFileName("vpn-manager")
    from vpn_manager.gui.desktop import SingleInstance, DesktopIntegration
    try:
        instance = SingleInstance(app)
        if not instance.acquire():
            if instance.activate_existing():
                return 0
            QMessageBox.warning(None, "VPN Manager", "Ya hay una instancia abierta, pero no responde. Espera y vuelve a intentarlo.")
            return 1
    except OSError:
        QMessageBox.critical(None, "VPN Manager", "No se pudo crear el bloqueo privado de la aplicación.")
        return 1
    try:
        window = MainWindow()
    except (OSError, sqlite3.Error):
        QMessageBox.critical(None, "VPN Manager", "No se pudo abrir la biblioteca local. Revisa los permisos y el espacio disponible.")
        instance.close()
        return 1
    desktop = DesktopIntegration(window, app)
    instance.activated.connect(desktop.show_window)
    app.aboutToQuit.connect(instance.close)
    window.show()
    try:
        return app.exec()
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
