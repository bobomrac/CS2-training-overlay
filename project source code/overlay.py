import sys
import ctypes
import json
import keyboard
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QPropertyAnimation
from PyQt5.QtGui import QRegion, QFont, QColor, QPainter
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel

CONFIG_FILE = Path("overlay_config.json")

class HotkeyWorker(QObject):
    toggle_signal = pyqtSignal()
    close_signal = pyqtSignal()
    adjust_opacity = pyqtSignal(int)
    adjust_width = pyqtSignal(int)
    adjust_height = pyqtSignal(int)

    def run(self):
        keyboard.add_hotkey('b', self.toggle_signal.emit)  # Toggle overlay
        keyboard.add_hotkey('f12', self.close_signal.emit)  # Close
        
        # Opacity controls
        keyboard.add_hotkey('ctrl+page up', lambda: self.adjust_opacity.emit(10))
        keyboard.add_hotkey('ctrl+page down', lambda: self.adjust_opacity.emit(-10))
        
        # Size controls
        keyboard.add_hotkey('ctrl+right', lambda: self.adjust_width.emit(10))
        keyboard.add_hotkey('ctrl+left', lambda: self.adjust_width.emit(-10))
        keyboard.add_hotkey('ctrl+up', lambda: self.adjust_height.emit(10))
        keyboard.add_hotkey('ctrl+down', lambda: self.adjust_height.emit(-10))
        
        keyboard.wait()

class Overlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.overlay_visible = True
        self.central_width = self.config.get('width', 300)
        self.central_height = self.config.get('height', 200)
        self.bg_opacity = self.config.get('opacity', 190)
        self.init_ui()
        self.init_hotkeys()
        self.set_click_through()
        
        # Help text
        self.help_label = QLabel(
            "B: Toggle | F12: Exit\n"
            "Ctrl+Page Up/Down: Opacity\n"
            "Ctrl+Arrows: Resize",
            self
        )
        self.help_label.setStyleSheet("""
            color: white; 
            background-color: rgba(0, 0, 0, 0.7);
            padding: 8px;
            border-radius: 4px;
            font-family: Arial;
            font-size: 12px;
        """)
        self.help_label.adjustSize()
        self.help_label.move(20, 20)

        # Status message
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("""
            color: lime; 
            font-size: 14px; 
            background-color: rgba(0, 0, 0, 0.7);
            padding: 4px;
        """)
        self.status_label.hide()

    def load_config(self):
        try:
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
        return {'width': 300, 'height': 200, 'opacity': 190}

    def save_config(self):
        CONFIG_FILE.write_text(json.dumps({
            'width': self.central_width,
            'height': self.central_height,
            'opacity': self.bg_opacity
        }))

    def init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 
                       QApplication.primaryScreen().size().width(),
                       QApplication.primaryScreen().size().height())
        self.update_mask()

    def update_mask(self):
        self.central_rect = self.rect().adjusted(
            self.width()//2 - self.central_width//2,
            self.height()//2 - self.central_height//2,
            -self.width()//2 + self.central_width//2,
            -self.height()//2 + self.central_height//2
        )
        mask = QRegion(self.rect()) - QRegion(self.central_rect)
        self.setMask(mask)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self.bg_opacity))
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(self.central_rect, Qt.transparent)

    def init_hotkeys(self):
        self.hotkey_thread = QThread()
        self.hotkey_worker = HotkeyWorker()
        self.hotkey_worker.moveToThread(self.hotkey_thread)
        
        self.hotkey_worker.toggle_signal.connect(self.toggle_overlay)
        self.hotkey_worker.close_signal.connect(self.close_overlay)
        self.hotkey_worker.adjust_opacity.connect(self.change_opacity)
        self.hotkey_worker.adjust_width.connect(self.change_width)
        self.hotkey_worker.adjust_height.connect(self.change_height)
        
        self.hotkey_thread.started.connect(self.hotkey_worker.run)
        self.hotkey_thread.start()

    def set_click_through(self):
        hwnd = int(self.winId())
        ctypes.windll.user32.SetWindowLongW(
            hwnd,
            -20,
            ctypes.windll.user32.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20
        )

    def change_opacity(self, delta):
        self.bg_opacity = max(30, min(255, self.bg_opacity + delta))
        self.show_status(f"Opacity: {int((self.bg_opacity/255)*100)}% (Ctrl+Page Up/Down)")
        self.update()

    def change_width(self, delta):
        self.central_width = max(100, min(800, self.central_width + delta))
        self.show_status(f"Width: {self.central_width}px (Ctrl+←/→)")
        self.update_mask()

    def change_height(self, delta):
        self.central_height = max(100, min(600, self.central_height + delta))
        self.show_status(f"Height: {self.central_height}px (Ctrl+↑/↓)")
        self.update_mask()

    def show_status(self, text):
        self.status_label.setText(text)
        self.status_label.adjustSize()
        self.status_label.move(
            self.width() - self.status_label.width() - 20,
            self.height() - 40
        )
        self.status_label.show()
        anim = QPropertyAnimation(self.status_label, b"windowOpacity")
        anim.setDuration(2000)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.start()

    def toggle_overlay(self):
        self.overlay_visible = not self.overlay_visible
        self.setVisible(self.overlay_visible)
        if self.overlay_visible:
            self.raise_()
            self.activateWindow()
            self.set_click_through()

    def close_overlay(self):
        self.save_config()
        self.hotkey_thread.quit()
        self.close()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    sys.exit(app.exec_())