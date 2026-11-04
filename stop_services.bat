@echo off
title CloudOps Intel - Stop Services
powershell -Command "Start-Process powershell -ArgumentList '-NoExit -ExecutionPolicy Bypass -NoProfile -File \"%~dp0scripts\stop_services.ps1\"' -Verb RunAs"
