# DDE-069 Desktop Dependency Security Closure

Date: 2026-09-07

## Scope

The standalone DDE Code desktop package carried 15 npm advisories: 1 moderate, 13 high and 1 critical. The vulnerable graph included direct `electron` / `electron-builder` dependencies plus transitive `tar`, `extract-zip`, `node-gyp` and builder families.

## Change

- `electron` upgraded from `^33.2.1` to `^44.2.0`.
- `electron-builder` upgraded from `^25.1.8` to `^26.15.3`.
- The lockfile was regenerated from those admitted versions.
- Electron 44's asynchronous `clipboard.readText()` contract is awaited at both secret-ingress boundaries. Existing safeStorage/session-token custody is unchanged.

## Verification

- desktop `npm audit`: **0 vulnerabilities**
- Ruff / formatting / mypy: **PASS**
- Python unit + contract + recovery: **1491 passed / 6 skipped**
- contract-only rerun: **220 passed**
- VS Code extension: **77 passed**
- desktop TypeScript: **PASS**
- Windows x64 unpacked package via electron-builder 26.15.3: **PASS**
- React TypeScript + Vite production build: **PASS**
- generated contracts, design tokens and binding matrix drift checks: **PASS**

This closes the desktop dependency vulnerability tranche only. It does not claim code signing, packaged VS Code-host browser E2E, AD-039 pixel-reference conformance or live R2 certification.
