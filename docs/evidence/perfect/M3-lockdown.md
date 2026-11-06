# M3: what Claude on the person's computer can touch (found and fixed 2026-11-05)

Claude Code 2.1.314 on this PC, `--model sonnet`, logged in with a claude.ai account. Every row below was run for real.

## Before: the app's own `direct` flags
The flags were `-p --output-format stream-json --verbose --no-session-persistence --disable-slash-commands --strict-mcp-config --mcp-config <file> --allowedTools mcp__video-tool__*`. The run inherited the app's working folder. A harmless test from an empty folder, asking for four small tasks:

| Task | What happened |
|---|---|
| `Bash`: `echo SHELL-WORKS` | **ran**, printed `SHELL-WORKS` |
| `Read` a file inside the working folder | **ran**, returned the file |
| `Grep` the working folder | **ran**, returned matches |
| `Read` a file outside the working folder | refused ("requested permissions ... but you haven't granted it yet") |

The init line offered 33 built-in tools (Bash, PowerShell, Read, Grep, Glob, Edit, Write, WebSearch, ...). So the constraint "only this server's MCP tools" in the code comment was not true. A transcript or web page is untrusted text, so this was a real hole. The earlier session logs of `direct` runs are gone, so what the `PowerShell`, `Read` and `Grep` calls did then cannot be read back; the test above shows what they were allowed to do.

## After: `--tools ""`, an empty working folder, the key beside it
- the planning session (`run`): init line offers **0 built-in tools and 43 Video Tool tools**; `list_projects` ran; shell, read and search all answered "No such tool available".
- `ask` without pictures: `--tools ""`, no `--allowedTools`; with pictures: `--tools Read --allowedTools "Read(./**)"`, in a new temporary folder that holds only `system.txt` and the pictures.

`node test-live-lockdown.js http://192.168.123.47:8790 ../../dist/recording-run/key.txt` (real program, not part of `npm test`):

```
1. ask with one picture:  {"ok":true,"text":"{\"word\":\"BANANA\"}", ..."seconds":5.4}
2. ask told to read a file outside its folder and to run a command:  {"read_result":"REFUSED","command_result":"REFUSED"}
3. run told to use a shell, read and search, and to call a Video Tool tool:
   init {"model":"claude-sonnet-5-5","builtIn":[]}, calls [list_projects: ran, Bash: refused, Read: refused, Grep: refused]
live lockdown: ok
```
The denial of the outside file also shows in the program's own `permission_denials` list.

## Not tested against the real program
Codex: it is not on this PC's PATH (only the Codex app's own `codex.exe`, 0.166.0-alpha.5.1, which I used to read `codex exec --help`). Its `ask` is tested against a stand-in only. Its read-only sandbox still lets a shell read files the user can read, and there is no switch to turn the shell off in that build, so a hostile transcript could try to read local files through Codex and put them in its answer. That answer goes to the person's own server. Step F8 must test prompt injection for Codex separately and say so.
