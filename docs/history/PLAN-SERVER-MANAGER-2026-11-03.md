# A visible processing server on Windows and Linux

The server must be an application people can find and control, rather than only a background process. Use one native Electron manager on both platforms: status, client connection address/code, open workspace, start/stop/restart, log and login startup. Closing hides to a tray icon where the desktop supports one. The tray's explicit Quit server action stops only our processing server, never existing ComfyUI/Ollama.

The packaged server edition owns its processing child. The existing Linux home install is attached through a small local configuration and controls only its named user systemd service. Both use the same manager window and loopback HTTP controller. Installation creates a Start/Applications entry; the Linux home deployment also creates a desktop shortcut and user login launcher. All remote writes stay under /home/roy. No operating-system packages, existing engine settings, training processes, or system-wide services are changed.

(2026-11-05: pairing codes are gone. The manager's "Connect a client" card shows the address and a Copy address button; a computer on the network types the address and is in. See PLAN-PERFECT.MD decision 7.)

Acceptance: exercise start/stop/restart against an isolated backend, check IPC sender/loopback boundaries, build the Windows server installer, deploy and verify the Linux Applications/tray manager on the actual GPU server, and inspect the shared manager layout. Keep native UI limitations separate from process/API checks.
