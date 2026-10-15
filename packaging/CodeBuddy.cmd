@echo off
rem Start CodeBuddy: the overlay starts the brain and stops it when you quit (right-click, Esci).
start "" "%~dp0overlay\codebuddy-overlay.exe" --start-brain "\"%~dp0brain\buddy.exe\" serve"
