# gr-stubuddy

An Electron application with Vue and TypeScript

## Recommended IDE Setup

- [VSCode](https://code.visualstudio.com/) + [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint) + [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar)

## Project Setup

### Install

```bash
$ npm install
$ npm run python:setup
```

The Python environment is project-local. It provides the screenshot backend and PyInstaller used by
the packaging commands.

### Test

```bash
$ npm run lint
$ npm run typecheck
$ npm run test:python
```

### Development

```bash
$ npm run dev
```

### Build

Packaging builds the Python backend before electron-builder runs. Build each platform package on its
target operating system because PyInstaller does not cross-compile.

```bash
# For windows
$ npm run build:win

# For macOS
$ npm run build:mac

# For Linux
$ npm run build:linux
```
