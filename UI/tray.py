from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

log = logging.getLogger(__name__)


class TrayController:
    """Owns Windows system tray integration."""

    def __init__(self, app_name: str = "Jarvis", on_show: Callable[[], None] | None = None, on_quit: Callable[[], None] | None = None) -> None:
        self.app_name = app_name
        self.on_show = on_show
        self.on_quit = on_quit
        self.tray: QSystemTrayIcon | None = None

    def start(self) -> None:
        """Create and show the Windows notification-area icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("Windows system tray is not available in this session")

        self.tray = QSystemTrayIcon(self._create_icon())
        self.tray.setToolTip(self.app_name)
        self.tray.activated.connect(self._activated)

        menu = QMenu()
        show_action = QAction("Show Jarvis", menu)
        show_action.triggered.connect(self._show_requested)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit_requested)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()
        self.tray.showMessage(self.app_name, "Jarvis is running in the background.", QSystemTrayIcon.Information, 2500)
        log.info("System tray icon started")

    def stop(self) -> None:
        """Hide the tray icon."""
        if self.tray:
            self.tray.hide()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick}:
            self._show_requested()

    def _show_requested(self) -> None:
        if self.on_show:
            self.on_show()

    def _quit_requested(self) -> None:
        if self.on_quit:
            self.on_quit()
        QApplication.quit()

    def _create_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor("#3b82f6"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(6, 6, 52, 52)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(28, 14, 8, 8)
        painter.drawRoundedRect(18, 28, 28, 16, 7, 7)
        painter.end()
        return QIcon(pixmap)
