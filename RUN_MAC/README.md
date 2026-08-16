# Running HDS OS

Two folders, one per platform, with the same contents:

    RUN_MAC/   double-click a .command file (macOS / Linux: `bash <file>`)
    RUN_WIN/   double-click a .bat file (Windows)

Every launcher cds to the project root on its own, so it works from anywhere.

## Grouped by what you are doing, not by what the file is

    AGENT/   the agent itself
      start-agent   run the daemon (kills any previous instance first —
                    ONE model in memory is a hard rule)
      stop-agent    stop it
      console       live console: plan, pipeline control, dialogue   :8114

    API/     ways to drive HDS from other tools
      mcp-server    MCP server, 14 tools. This is the bridge to Cursor,
                    VS Code, Cline and anything else that speaks MCP.
      webhook       plain HTTP API for submitting tasks               :8110

    CHECK/   is it healthy, and how well is it doing
      doctor        isolation, toolchains, served models, free RAM
      tests         full suite + the three structural audits + cage benchmark
      stats         generation quality, failure reasons, telemetry
      skills        the orchestrator skills and their triggers

    WEB/     the interfaces
      agent-ui      agent interface: live plan rail + dialogue        :8253
      site          the public site, 5 languages                      :8231

## Order on a fresh machine

1. `CHECK/doctor` — confirms Docker, toolchains and a served model.
2. `AGENT/start-agent` — one instance, never two.
3. `AGENT/console` or `WEB/agent-ui` — watch it work.

## Windows notes

The OS itself is pure Python plus Docker, so it runs on Windows: RAM
monitoring, port checks and voice all have explicit Windows branches. Use
Docker Desktop instead of Colima. The `.sh` creator tooling (propagate) is not
part of the shipped OS and needs Git Bash or WSL.
