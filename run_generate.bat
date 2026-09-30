@echo off
cd /d "%~dp0"
python generate.py 10 >> log.txt 2>&1
