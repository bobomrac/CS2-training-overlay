@echo on
pyinstaller --noconsole --windowed ^
--name "CS2 Training Overlay" ^
--add-data "overlay_config.json;." ^
--hidden-import PyQt5.sip ^
--collect-all keyboard ^
overlay.py
pause