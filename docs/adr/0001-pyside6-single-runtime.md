# ADR 0001: PySide6 single-runtime desktop shell

Date: 2026-11-11

## Status
Accepted

## Context
SAMT is a PyTorch research pipeline (torch + MONAI + SimpleITK + skimage). The user asked for a Windows/macOS desktop wrapper with bilingual UI. Options: PySide6 in-process, Electron + Python sidecar, Tauri + Python sidecar.

## Decision
Build the UI with PySide6 in the same Python process that runs inference. Inference runs on a QThread; the heavy core (torch, MONAI) stays in one runtime.

## Consequences
- One packaging toolchain (PyInstaller) for both OSes.
- No IPC layer to version or secure.
- UI must respect CPU-bound GIL pressure: long preprocessing is moved off the UI thread, but any pure-Python work in the core blocks the UI only through cooperative yields.
- Replacing the UI later means rewriting in Qt or adding a sidecar; accepted for v1 scope.
