@echo off
title CloudOps Intel - Automated Server Setup
powershell -Command "Start-Process powershell -ArgumentList '-NoExit -ExecutionPolicy Bypass -NoProfile -File \"%~dp0scripts\setup_server.ps1\" -ProjectRoot \"%~dp0.\"' -Verb RunAs"
