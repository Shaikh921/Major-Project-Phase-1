@echo off
title CloudOps Intel - Restart Services
powershell -Command "Start-Process powershell -ArgumentList '-NoExit -ExecutionPolicy Bypass -NoProfile -File \"%~dp0scripts\restart_services.ps1\"' -Verb RunAs"
