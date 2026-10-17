"""
PySide6 Desktop Application Interface for Falcon AI Assistant.
Provides a modern dark-themed Windows 11 interface for chat, voice indicators,
task workflow progress, and system metrics.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import sys
import threading
from typing import Optional

from falcon import __app_name__, __author__, __version__
from falcon.config.settings import load_settings
from falcon.core.controller import FalconCore
from falcon.ui.ui_bridge import get_qt_signals_adapter

try:
    from PySide6.QtCore import Qt, QTimer, Slot
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


class FalconWindow(QMainWindow):
    """Main desktop window for Falcon AI Desktop Assistant."""

    def __init__(self, core: FalconCore):
        super().__init__()
        self.core = core
        self.signals = get_qt_signals_adapter(self.core)
        self.init_ui()
        self._bind_signals()

    def init_ui(self):
        self.setWindowTitle(f"{__app_name__} v{__version__} — Developed by {__author__}")
        self.resize(850, 650)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #12141A;
            }
            QLabel {
                color: #E2E8F0;
                font-family: 'Segoe UI', sans-serif;
            }
            QTextEdit {
                background-color: #1A1D24;
                color: #F8FAFC;
                border: 1px solid #2D3748;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-family: 'Segoe UI', sans-serif;
            }
            QLineEdit {
                background-color: #1A1D24;
                color: #FFFFFF;
                border: 1px solid #3B82F6;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QProgressBar {
                border: 1px solid #2D3748;
                border-radius: 4px;
                text-align: center;
                color: #FFFFFF;
                background-color: #1A1D24;
            }
            QProgressBar::chunk {
                background-color: #10B981;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(f"⚡ {__app_name__}")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header_layout.addWidget(title_label)

        self.status_label = QLabel("● Ready")
        self.status_label.setStyleSheet("color: #10B981; font-weight: bold;")
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        main_layout.addLayout(header_layout)

        # Chat Transcript Area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display, stretch=1)

        # Task Progress Bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Input Area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Falcon anything or instruct desktop automation... (English / Hindi / Hinglish)")
        self.input_field.returnPressed.connect(self.on_send_clicked)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.on_send_clicked)
        input_layout.addWidget(self.send_btn)

        main_layout.addLayout(input_layout)

        # Welcome message
        self.append_message("Falcon", "Namaste! I am Falcon, your Windows 11 desktop AI assistant developed by HarshGuruJi. How can I help you today?")

    def _bind_signals(self):
        if not self.signals:
            return
        self.signals.assistant_ready.connect(lambda d: self.status_label.setText("● Online"))
        self.signals.response_completed.connect(self._on_response_completed)
        self.signals.task_progress.connect(self._on_task_progress)
        self.signals.task_completed.connect(lambda d: self.progress_bar.setVisible(False))

    def append_message(self, sender: str, text: str):
        color = "#38BDF8" if sender == "Falcon" else "#34D399"
        self.chat_display.append(f"<b style='color:{color}'>{sender}:</b> {text}<br>")

    def on_send_clicked(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.append_message("You", text)
        self.status_label.setText("● Thinking...")

        # Run process_message on background loop
        asyncio.create_task(self.core.process_message(text))

    def _on_response_completed(self, data: dict):
        text = data.get("text", "")
        self.append_message("Falcon", text)
        self.status_label.setText("● Ready")

    def _on_task_progress(self, data: dict):
        self.progress_bar.setVisible(True)
        percent = int(data.get("progress_percent", 0))
        self.progress_bar.setValue(percent)


def run_gui_app(core: FalconCore):
    """Start the PySide6 desktop GUI."""
    if not PYSIDE_AVAILABLE:
        print("[Error] PySide6 is not installed. Install via: pip install PySide6")
        return
    app = QApplication.instance() or QApplication(sys.argv)
    window = FalconWindow(core)
    window.show()
    app.exec()
