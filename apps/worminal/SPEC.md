# Worminal specification

## Outcome

Worminal opens an interactive Linux shell on the computer running the app, directly in a browser.
The walking skeleton is a local operator tool, not a remotely deployable shell service.

## Walking skeleton

FastAPI serves one self-contained Preact artifact and owns one ephemeral pseudoterminal per browser
WebSocket. The PTY starts the server user's default shell in the Worminal app directory. The xterm.js
frontend forwards input and terminal dimensions and renders the byte stream.

Only loopback clients may open a shell. Existing same-origin WebSocket protection also applies. A
disconnect terminates the shell's process group and closes its PTY; sessions, output, and command
history are not persisted or reconnectable. The first version has one draggable, resizable terminal
window and no file transfer,
clipboard integration, tabs, or command-history UI.

The terminal interaction is product-defining and therefore app-owned; MonoForm is unsuitable.

## Interaction contracts

- Opening the page connects automatically and reports connecting, connected, exited, or failed.
- The terminal window can be dragged by its title bar and resized from its lower-right handle while
  remaining inside the visible browser workspace. Arrow keys move a focused title bar.
- Browser input is written to the PTY without command interpretation by the application.
- Resize messages set positive terminal row and column counts; malformed messages are ignored.
- Ctrl+C is ordinary terminal input and interrupts the foreground process through PTY semantics.
- Disconnect, shell exit, or transport failure performs idempotent process-group and descriptor
  cleanup. No child process may remain attributable to a closed session.
- A non-loopback peer is refused before a shell process is created.

## Real-world validation

The app-owned suite proves that a browser can run `pwd` and `printf`, resize the terminal, interrupt
`sleep` with Ctrl+C, and close the page without leaving its shell process. Wide and narrow checks
must keep the terminal usable without introducing a second product surface.
