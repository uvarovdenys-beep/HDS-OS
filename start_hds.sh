#!/bin/bash
# start_hds.sh — single entry point for HDS OS.
# Replaces the start_hds{,_audio,_silent} matrix: pick mode + voice by flag
# instead of having a separate script per combination.
#
# Usage:
#   start_hds.sh [--mode daemons|agent|full|dashboard] [--voice on|off]
#                [--monitor|--once] [--dry-run]
#   defaults: --mode full --voice off
#
# Modes:   daemons   = background daemons only
#          agent     = the agent loop only
#          full      = daemons (background) + agent   [default]
#          dashboard = full stack + web GUI :3000 + API
# Voice:   on = spoken status (agent_audio) · off = silent (agent_silent)
set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE=full; VOICE=off; RUN=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --mode)    MODE="$2"; shift 2;;
    --voice)   VOICE="$2"; shift 2;;
    --monitor|--once) RUN="$1"; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \?//'; exit 0;;
    *) echo "unknown arg: $1 (try --help)"; exit 1;;
  esac
done

case "$VOICE" in
  on)  AGENT="start_hds_agent_audio.sh";;
  off) AGENT="start_hds_agent_silent.sh";;
  *)   echo "unknown --voice '$VOICE' (on|off)"; exit 1;;
esac

go() {  # run a child launcher, or just print it in --dry-run
  if [ "$DRY" = 1 ]; then echo "DRY: bash $*"; else bash "$BASE_DIR/$1" "${@:2}"; fi
}

echo "HDS OS — mode=$MODE voice=$VOICE ${RUN:+($RUN)}"
case "$MODE" in
  daemons)   go start_hds_daemons.sh;;
  agent)     go "$AGENT" $RUN;;
  dashboard) go start_hds_with_dashboard.sh;;
  full)
    if [ "$DRY" = 1 ]; then
      echo "DRY: bash start_hds_daemons.sh & ; sleep 3 ; bash $AGENT $RUN"
    else
      bash "$BASE_DIR/start_hds_daemons.sh" &
      DAEMON_PID=$!
      trap "kill $DAEMON_PID 2>/dev/null; exit" INT TERM
      sleep 3
      bash "$BASE_DIR/$AGENT" $RUN
    fi;;
  *) echo "unknown --mode '$MODE' (daemons|agent|full|dashboard)"; exit 1;;
esac
