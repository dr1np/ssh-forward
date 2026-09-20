# Changelog

## [0.2.2] - 2026-09-20

### Changed

- Refined the SSH Forward logo into a centered single-line `S` mark.
- Added two visible ochre endpoint dots to represent point-to-point port forwarding.
- Replaced the previous logo assets in the desktop titlebar, sidebar, Windows ICO, macOS ICNS, and PNG icon set.

### Fixed

- Removed the logo image baseline shadow that produced a gray edge below the mark.
- Kept the editor action area free of the hard divider and gradient edge introduced during the v0.2.1 layout refinement.

### Verification

- Frontend type and accessibility checks pass.
- Frontend production build passes.
- Windows Tauri release build passes.

## [0.2.1] - 2026-09-20

- Added page-level navigation for creating forwards, running forwards, favorites, and logs.
- Added the local runtime status popover and consolidated sidebar status display.
- Removed the native white titlebar with a custom frameless titlebar.
