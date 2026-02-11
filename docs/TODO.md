# PromptAnywhere TODO

> Personal feature tracker. Append new features, check off tasks, keep moving.

### Format guide

Each feature is a self-contained block. Use this template:

```
---

### F<N>: <Short name>
**Status:** active | paused | done
**Created:** YYYY-MM-DD
**Updated:** YYYY-MM-DD

#### Now (current sprint — do these first)
- [ ] Task description

#### Next (queued — pick up when Now is clear)
- [ ] Task description

#### Later (ideas / low-priority)
- [ ] Task description

#### Done
- [x] Task (YYYY-MM-DD)

#### Session log
- **YYYY-MM-DD** — What happened, what's next.
```

**Rules:**
- One feature per block. Don't merge unrelated work.
- Move tasks between Now/Next/Later freely. Keep Now short (3-5 items max).
- When you finish a task, move it to Done with the date. Don't delete it.
- Session log is append-only.
- Agents: do NOT reorder or renumber existing features. Append new ones at the bottom.

---

### F0: Message UX (copy, code blocks, streaming)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] “Copy last answer” control (only latest assistant msg gets actions)
- [ ] Code block detection + “Copy code” button per block (ChatGPT-style)
- [ ] Streaming scroll policy: only autoscroll if user is at bottom; show “Jump to bottom” when scrolled up

#### Next
- [ ] Message bubbles (user/assistant) instead of single giant QTextEdit blob
- [ ] Basic markdown-ish rendering (headings/bullets) without breaking copy

#### Later
- [ ] “Copy as markdown” + “Copy as plain text” toggles
- [ ] “Save snippet” / pin message

#### Done
_(empty)_

#### Session log
- **2026-02-11** — Seeded tasks from UI feedback; keep controls minimal (latest msg + code blocks).

---

### F1: Context attachments (clipboard/selection/active window/screenshot)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] “Attachment chips” row under input (Clipboard/Selection/Screenshot/Active App) with remove + preview
- [ ] Ensure screenshot drag-select actually feeds bytes into agent context (instrument + fix)
- [ ] Attach clipboard button + hotkey (only when clipboard has text)

#### Next
- [ ] “Attach active window info” (title + process) and show as chip
- [ ] “Attach project folder/cwd” control (manual pick now; auto-detect later)

#### Later
- [ ] OCR screenshot → attach recognized text as separate chip
- [ ] Context bundle button: attach clipboard + active window + optional screenshot in one click

#### Done
_(empty)_

#### Session log
- **2026-02-11** — Plan: treat context as explicit attachments, never invisible prompt stuffing.

---

### F2: Toolbar/button rethink (make buttons uniquely useful)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] Decide final v1 toolbar (6–8 buttons max) and remove/rename low-signal ones
- [ ] Rename concepts:
  - [ ] Google Search → Web Search (tool)
  - [ ] Search Files → Find in Project
  - [ ] Maximize Chat → Focus Mode (drawer locked open)
  - [ ] New Terminal → Run Command (purposeful)

#### Next
- [ ] Add streaming “Stop” button (visible only while streaming)

#### Later
- [ ] Context-aware buttons (show/hide based on current state: clipboard present, screenshot present, etc.)

#### Done
_(empty)_

#### Session log
- **2026-02-11** — Goal: buttons should be AI workflow glue, not random utilities.

---

### F3: Web Search as a cross-agent tool (Gemini-only backend)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] Implement Web Search flow:
  - [ ] run search via Gemini backend
  - [ ] show “tool receipt” in transcript (sources + summary)
  - [ ] pass sources/summary to current agent and continue answering

#### Next
- [ ] Cache recent search results per session to avoid re-search spam

#### Later
- [ ] “Open sources” button list (no embeds) + one-click open in browser

#### Done
_(empty)_

#### Session log
- **2026-02-11** — Principle: search is a tool, not a mental model switch.

---

### F4: Shell/Drawer polish (jitter, layout stability)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] Fix drawer jitter: prompt area should stay anchored; drawer expands upward between shell header and prompt
- [ ] Ensure closing/collapsing drawer always shrinks shell height (no “inherited tall” state)

#### Next
- [ ] Unify chrome: shell owns title/border/background; embedded prompt/result hide their own chrome

#### Later
- [ ] Focus/keyboard rules: ESC collapses drawer; Enter sends; Ctrl+Enter newline; Ctrl+K command palette

#### Done
- [x] Add shell window + collapsible drawer scaffold (2026-02-10)

#### Session log
- **2026-02-11** — Promote shell to sole chrome owner; embedded widgets should become content-only.

---

### F5: Agent Host integration (prewarm, sessions, streaming)
**Status:** active
**Created:** 2026-02-11
**Updated:** 2026-02-11

#### Now
- [ ] UI: detect host running via `/health`; add tray/debug action “Start host”
- [ ] Host: SSE streaming endpoint for prompt responses (token/final/error)

#### Next
- [ ] Prewarm selected agents on UI start (config-driven)
- [ ] Cancellation endpoint + UI Stop button wired through host

#### Later
- [ ] True persistent PTY sessions (ConPTY) if CLIs support interactive mode; defer until UX is locked

#### Done
- [x] Scaffold host skeleton (FastAPI + /health + prewarm stub) (2026-02-10)

#### Session log
- **2026-02-11** — Focus on “persistent service” first; only chase PTY persistence if it’s worth it.
