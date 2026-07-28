# Rigor mobile editor architecture

## Current implementation

The first native practice slice uses React Native `TextInput` as a controlled multiline monospace editor. This keeps the initial mobile workspace native, lightweight, and testable while preserving selection, copy/paste, multiline editing, undo behavior supplied by the OS, draft autosave, and keyboard-safe navigation.

The editor is not presented as a Monaco-equivalent IDE.

## Why Monaco was not blindly ported

Monaco is browser-oriented. Shipping the entire app as a WebView would weaken native navigation/lifecycle/accessibility and create a second browser shell. If syntax highlighting, richer indentation, diagnostics, or code-navigation requirements justify it, a future **editor-only** WebView surface may host a narrowly scoped browser editor while the rest of Rigor stays native.

## Data ownership

The editor owns temporary text only. Local text is persisted to SQLite and synchronized to the canonical FastAPI practice session. Run/Submit never execute on the device for authoritative evaluation.

## Upgrade criteria

Adopt a richer editor only after measuring actual native usability and proving:

- keyboard and selection behavior on iOS/Android;
- accessible focus/labels;
- bounded memory for large drafts;
- reliable state transfer between native shell and editor surface;
- no token/credential exposure to editor HTML/JavaScript;
- no new execution path on the device.
