# Changelog

## [0.2.5] - 2026-09-23

### Changed

- Unified the user-facing product brand as `SSHForward`: the packaged executable is now `SSHForward.exe`, and portable directories, archives, and launchers use `SSHForward`, while the legacy `SSHForwarder.exe` launch path and existing `SSHForwarder` data directory remain supported for compatibility.
- Disabled the WebView's native context menu while using the desktop app.
- Added a favorite-copy action that opens an editable draft with a collision suffix when needed before saving it as a new favorite.
- Improved the editor bottom action area so its actions share the available width, keep rounded corners, and keep the surface and shadow within the editor card.

### Verification

- `npm run check` passes with 0 errors and 0 warnings; the frontend production build completes with 132 transformed modules.
- All 21 Rust unit tests pass, and the isolated Windows release build succeeds.
- The packaged Windows executable reports ProductVersion and FileVersion 0.2.5.
- The native app was visually checked after the action-area fix; its buttons fill the two-column layout and the rounded action panel remains inside the editor card.
- The favorite-copy flow was checked with isolated data: repeated copies receive distinct suffixes, and editing/saving the second copy leaves both earlier profiles unchanged.

## [0.2.4] - 2026-09-23

### Changed

- Made the desktop window surface continuous by removing the standalone dark titlebar, extending the light main surface into the top control area, and moving the custom window controls into the main content corner.
- Added explicit new/edit mode messaging in the profile editor; saving a new profile creates a fresh favorite, while editing preserves the selected favorite's identity.
- Refined form presentation and interaction details with a wider create layout, separated connection tabs, improved editor scroll/action surfaces, disabled browser autofill for connection and port fields, and `ssh-forwarder` as Cargo's default run target.

### Fixed

- Opening “新建转发” or finishing a save now resets the editor to a blank new profile, preventing subsequent saves from overwriting the previous favorite.
- “启动并保存” now starts the exact profile returned by the save operation, so it uses the persisted configuration after the editor reset.
- Removed the dark right-side corner artifacts by letting the main surface run to the window's right and bottom edges; narrow layouts keep desktop controls in a fixed top strip while content scrolls.
- Port-change input no longer invites browser autofill.

### Verification

- `npm run check` passes with 0 errors and 0 warnings.
- The frontend production build completes successfully with 132 transformed modules.
- All 21 Rust unit tests pass, and the isolated Windows release build completes successfully.
- The packaged Windows executable reports ProductVersion and FileVersion 0.2.4.
- The executable was launched and visually checked at the target desktop layout; the light workspace reaches the top and right window edges, and the integrated controls remain unobstructed.

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
