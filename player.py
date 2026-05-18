#!/usr/bin/env python3
"""Full-screen PyQt5 digital signage player."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QStackedWidget, QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


class ImageView(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: black;")
        self._pixmap: QPixmap | None = None

    def set_image(self, path: Path) -> bool:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        self._pixmap = pixmap
        self._rescale()
        return True

    def resizeEvent(self, event):  # noqa: N802 - Qt API name
        self._rescale()
        super().resizeEvent(event)

    def _rescale(self) -> None:
        if not self._pixmap:
            return
        scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.setPixmap(scaled)


class SignagePlayer(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_json(CONFIG_PATH, {})
        self.playlist_path = BASE_DIR / self.config.get("playlist_file", "playlist.json")
        self.global_duration_ms = int(self.config.get("global_duration_seconds", 15)) * 1000
        self.fallback_path = BASE_DIR / self.config.get("fallback_image", "media/fallback.png")
        self.url_timeout_ms = int(self.config.get("url_load_timeout_seconds", 10)) * 1000

        self.items: list[dict[str, str]] = []
        self.index = -1
        self.waiting_for_url = False

        self.stack = QStackedWidget()
        self.image_view = ImageView()
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.NoContextMenu)
        self.web_view.loadFinished.connect(self._web_load_finished)

        self.stack.addWidget(self.image_view)
        self.stack.addWidget(self.web_view)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.setLayout(layout)
        self.setCursor(Qt.BlankCursor)

        self.advance_timer = QTimer(self)
        self.advance_timer.setSingleShot(True)
        self.advance_timer.timeout.connect(self.next_item)

        self.url_timeout_timer = QTimer(self)
        self.url_timeout_timer.setSingleShot(True)
        self.url_timeout_timer.timeout.connect(self._url_timeout)

        self.reload_playlist()
        QTimer.singleShot(0, self.next_item)

    def reload_playlist(self) -> None:
        raw = load_json(self.playlist_path, [])
        if not isinstance(raw, list):
            raw = []
        self.items = [
            {"type": str(item.get("type")), "source": str(item.get("source"))}
            for item in raw
            if isinstance(item, dict) and item.get("type") in {"image", "url"} and item.get("source")
        ]

    def next_item(self) -> None:
        if not self.items:
            self.show_fallback()
            self.advance_timer.start(self.global_duration_ms)
            return

        # Reload once at the start of every full cycle.
        self.index += 1
        if self.index >= len(self.items):
            self.reload_playlist()
            self.index = 0

        if not self.items:
            self.show_fallback()
            self.advance_timer.start(self.global_duration_ms)
            return

        attempts = 0
        while attempts < len(self.items):
            item = self.items[self.index]
            if self.show_item(item):
                return
            self.index = (self.index + 1) % len(self.items)
            attempts += 1

        self.show_fallback()
        self.advance_timer.start(self.global_duration_ms)

    def show_item(self, item: dict[str, str]) -> bool:
        if item["type"] == "image":
            image_path = BASE_DIR / item["source"]
            if not image_path.exists():
                return False
            if not self.image_view.set_image(image_path):
                return False
            self.stack.setCurrentWidget(self.image_view)
            self.advance_timer.start(self.global_duration_ms)
            return True

        if item["type"] == "url":
            self.waiting_for_url = True
            self.stack.setCurrentWidget(self.web_view)
            self.web_view.load(QUrl(item["source"]))
            self.url_timeout_timer.start(self.url_timeout_ms)
            return True

        return False

    def show_fallback(self) -> None:
        if self.fallback_path.exists() and self.image_view.set_image(self.fallback_path):
            self.stack.setCurrentWidget(self.image_view)
        else:
            self.image_view.setText("No signage content available")
            self.stack.setCurrentWidget(self.image_view)

    def _web_load_finished(self, ok: bool) -> None:
        if not self.waiting_for_url:
            return
        self.waiting_for_url = False
        self.url_timeout_timer.stop()
        if ok:
            self.advance_timer.start(self.global_duration_ms)
        else:
            # Failed URLs are skipped.
            QTimer.singleShot(0, self.next_item)

    def _url_timeout(self) -> None:
        if self.waiting_for_url:
            self.waiting_for_url = False
            self.web_view.stop()
            QTimer.singleShot(0, self.next_item)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    player = SignagePlayer()
    player.showFullScreen()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
