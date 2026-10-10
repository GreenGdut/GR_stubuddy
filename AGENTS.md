# Repository Guide

## Product Direction

- This is a desktop application with a frontend-heavy architecture and a small, simple backend surface.
- The stack is TypeScript, Vue, Electron, Vite, and Python.
- Python backend code lives in `backend/`; Electron invokes it as a short-lived JSON CLI rather than a server. In development it uses `.venv`, while packaged apps load the PyInstaller binary from `resources/backend`.
- Keep product UI minimalist and use red and white as the primary visual theme.

## Tooling and Commands

- Use npm and keep `package-lock.json`; do not introduce another package manager or lockfile.
- Install with `npm install`. The `postinstall` hook runs `electron-builder install-app-deps`.
- Set up the project-local Python environment with `npm run python:setup`; run its unit tests with `npm run test:python`.
- Run the app in development with `npm run dev`; preview a completed build with `npm run start`.
- Run `npm run lint`, `npm run typecheck`, and `npm run test:python` for routine verification. There is no renderer test suite.
- Use `npm run typecheck:node` for main/preload changes and `npm run typecheck:web` for renderer-only changes.
- `npm run build` already runs the full typecheck before `electron-vite build`.
- Package with `npm run build:unpack`, `npm run build:win`, `npm run build:mac`, or `npm run build:linux`.
- Packaging now builds the Python executable first. PyInstaller is not a cross-compiler, so each platform package must be built on that platform.
- `npm run format` rewrites the whole repository; do not use it as a format-check command. `npm run lint` may create the ignored `.eslintcache` file.
- Keep the committed Electron download mirrors in `.npmrc` unless explicitly asked to change them.

## Process Boundaries

- `src/main/index.ts` owns Electron lifecycle and windows; workspace IPC and Python process orchestration live in `src/main/workspace.ts`.
- `src/preload/index.ts` is the renderer bridge. When adding an API, update its exposure and `src/preload/index.d.ts` together with the main-process handler.
- `src/renderer/src/main.ts` is the Vue entrypoint. Renderer code must reach Node/Electron capabilities through preload rather than importing them directly.
- The `@renderer/*` alias is renderer-only and maps to `src/renderer/src/*`; keep `electron.vite.config.ts` and `tsconfig.web.json` aligned if it changes.
- `out/` and `dist/` are generated and ignored. Change sources under `src/`, not generated output.

## Electron and Packaging

- Development loads `ELECTRON_RENDERER_URL`; production loads the built `renderer/index.html`.
- The current window deliberately uses `sandbox: false`. Do not change that security boundary without checking preload compatibility.
- External links are denied as new app windows and opened through `shell.openExternal`.
- `package.json` and `electron-builder.yml` still contain template values such as `example.com` and the example update URL. Do not treat them as approved release settings.

## Linux Wayland Behavior

- The workspace and screenshot flow was manually accepted on Ubuntu 24.04, GNOME Shell 46, and Wayland on 2026-10-10.
- Keep Electron on native Wayland. Do not force XWayland: it did not make global shortcut registration available and caused `XGetWindowAttributes failed for window 1` and GPU-process errors.
- `backend/capture_wayland.py` deliberately uses local D-Bus introspection definitions. System portal introspection on the accepted environment contains the invalid member name `power-saver-enabled`, which `dbus-next` rejects.
- GNOME's version 2 Screenshot Portal may complete an interactive screenshot without returning the required `uri`; it saves the image under the XDG pictures directory's `Screenshots/` folder instead. The backend snapshots that folder before capture and copies only the newly created or changed PNG into the current project as `input_NNN.png`.
- The accepted GNOME portal does not expose `org.freedesktop.portal.GlobalShortcuts`, so Electron global shortcut registration is unavailable in that environment. Preserve the clickable screenshot-card fallback unless shortcut support is redesigned for this desktop.
- Temporary Electron and Python diagnostics append to `/tmp/stubuddy/log`; logging failures must never break application actions.
