# HDS OS — First Run

Quick-start for a machine that has never run HDS OS.

## 1. Prerequisites

```bash
python3 --version   # 3.10+
ollama serve        # or LM Studio on :1234
```

Optional (for language validators):
```bash
python3 -m lang._toolchain   # shows what is present and how to install the rest
```

Optional but recommended (real execution isolation — Docker via colima, no root, no brew):
```bash
python3 -m sandbox.provision            # status: is isolation available?
python3 -m sandbox.provision --install  # auto-install lima+colima+docker CLI into ~/.local
```
Without it the sandbox degrades to `SubprocessBackend` (`isolated=False`) and every
`SandboxRunner` start emits an `isolation_missing` event with this exact command.

## 2. Start

```bash
cd HDS_CORE

# Full stack (daemons + webhook API + agent):
bash start_hds.sh

# Or with web dashboard on :3000:
bash start_hds.sh --mode dashboard
```

`start_hds.sh` picks up whatever local model `ollama`/LM Studio is serving — no
model name is hardcoded. Run `python3 agent/model_scan.py` to see what is available.

## 3. Verify the cage

```bash
# Should PASS (clean data write):
echo '{"op":"write","path":"storage/hello.txt","content":"ok"}' | python3 scribe.py - --size s

# Should REJECT (code at sandbox grade):
echo '{"op":"write","path":"storage/x.py","content":"x=1"}' | python3 scribe.py - --size s

# Should REJECT (eval in JS):
echo '{"op":"write","path":"storage/x.js","content":"eval(\"x\")"}' | python3 scribe.py - --size l
```

## 4. Connect a server AI (optional)

```bash
export OPENAI_API_KEY="sk-..."   # or GEMINI_API_KEY
# start produces: Webhook API: http://localhost:<PORT>
# use that port:
curl http://localhost:<PORT>/api/v1/external/connect \
  -H "Authorization: Bearer $HDS_API_KEY"
```

See `ORCHESTRATION.md` for the full API contract.

## 5. Run tests

```bash
python3 -m pytest tests/ -x -q                    # all tests (skip live AI)
HDS_LIVE_TESTS=1 python3 -m pytest tests/test_live_cage.py   # needs running model
```

## Common problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `R-PATH: escapes project root` | Path written outside HDS_CORE | Call `scribe.configure(root=...)` to re-anchor |
| `R-CAP: protocol 's' may not write code` | Code file at wrong grade | Use `protocol_size='l'` for `.py/.js/.html/...` |
| `toolchain_missing` warning | `node`/`php`/`dotnet` not installed | Run `python3 -m lang._toolchain` for install commands |
| Webhook not reachable | Port is dynamic, not :8080 | Read port from launcher output or `ai-mind/deployment/port_registry.json` |
