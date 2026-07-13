@echo off
REM GitHelper Build Script
REM Requires: pip install pyinstaller
echo Building GitHelper...
pyinstaller --name GitHelper --windowed --icon resources/icons/githelper.ico --add-data "resources;resources" src/githelper/__main__.py
echo Build complete. Output in dist/GitHelper/
