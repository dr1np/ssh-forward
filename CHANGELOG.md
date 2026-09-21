# Changelog

## [0.2.3] - 2026-09-22

### Changed

- Replaced the native SSH host datalist with a themed, searchable host picker.
- The host picker now opens with all concrete SSH hosts and rotates its toggle icon while expanded.

### Fixed

- SSH Config discovery now exposes all concrete hosts from the local configuration; wildcard template hosts remain filtered out.
- The host picker closes reliably when focus leaves it.
- Added padding around the form scroll area so focus rings are not clipped by the editor card.

### Verification

- The local SSH configuration resolves 22 concrete hosts on the development machine.
- Frontend check and production build pass.
- Rust unit and runtime integration tests pass.

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
