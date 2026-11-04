@echo off
title CloudOps Intel - Enable Auto-Start
powershell -Command "Start-Process powershell -ArgumentList '-NoExit -ExecutionPolicy Bypass -NoProfile -File \"%~dp0scripts\enable_autostart.ps1\"' -Verb RunAs"
