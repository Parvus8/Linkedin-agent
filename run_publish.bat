@echo off
cd /d "%~dp0"
python publish.py >> log.txt 2>&1
