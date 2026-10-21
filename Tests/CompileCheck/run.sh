#!/usr/bin/env bash
# Offline in-game compile check for a mod's Scripts/Simulation and Scripts/Client (see CompileCheck.csproj).
# Copied from an earlier prototype's run.sh and extended (project choice, --mod).
#
# The game's DLLs are win-x64 ReadyToRun images that the Linux .NET runtime refuses (BadImageFormatException),
# so the checker runs on Windows .NET 9 under wine, in a PRIVATE wine prefix under ~/.cache. It only READS
# the game install and the game's Proton prefix (to copy its Windows .NET runtime once); nothing under
# ~/.steam is written.
#
#   usage: Tests/CompileCheck/run.sh [Simulation|Client|all] [--mod <dir>] [--docs] [dump-dir]
#          Tests/CompileCheck/run.sh probe <file.csx>
#     Simulation   compile Scripts/Simulation
#     Client|all   compile Scripts/Simulation, then Scripts/Client against its image (the game's order); default all
#     --mod <dir>  the mod folder holding the .vrgproj (default: this mod), e.g. Tests/CompileCheck/ApiProbe
#     --docs       also list the missing-XML-doc warnings (CS1591, KN035), which are otherwise only counted
#     dump-dir     write the generated sources there, one sub-folder per project
#     probe <csx>  compile an in-game probe (se-mcp's wrapper and usings) against the game's assemblies, e.g.
#                  Source/Model/review/probe_scripts.csx; compile only, nothing runs
#   Prints "<Name>.<Sub>: OK: 0 errors, N warning(s)" per project; exits non-zero on any error.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mod="$(cd "$here/../.." && pwd)"
project=all
dump=""
docs=0
while [ $# -gt 0 ]; do
  case "$1" in
    Simulation|Client|all) project="$1" ;;
    probe) [ $# -ge 2 ] || { echo "probe needs a .csx file" >&2; exit 2; }
           project=probe; dump="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift ;;
    --mod) [ $# -ge 2 ] || { echo "--mod needs a directory" >&2; exit 2; }
           mod="$(cd "$2" && pwd)"; shift ;;
    --docs) docs=1 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) dump="$1" ;;
  esac
  shift
done
ls "$mod"/*.vrgproj >/dev/null 2>&1 || { echo "no .vrgproj in $mod" >&2; exit 2; }

steamapps="${SE2_STEAMAPPS:-$HOME/.steam/debian-installation/steamapps}"
game2="$steamapps/common/SpaceEngineers2/Game2"
src_dotnet="$steamapps/compatdata/1133870/pfx/drive_c/Program Files/dotnet"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/se2-compilecheck"
winpath() { echo "Z:$(echo "$1" | sed 's|/|\\|g')"; }

command -v dotnet >/dev/null || { echo "dotnet SDK not found" >&2; exit 4; }
command -v wine >/dev/null || { echo "wine not found" >&2; exit 4; }
[ -d "$game2" ] || { echo "game not found: $game2" >&2; exit 4; }

if [ ! -f "$cache/dotnet/dotnet.exe" ]; then
  rt="$(ls "$src_dotnet/shared/Microsoft.NETCore.App" | sort -V | tail -1)"
  echo "copying Windows .NET $rt from the game's Proton prefix to $cache/dotnet (once)"
  mkdir -p "$cache/dotnet/shared/Microsoft.NETCore.App"
  cp -r "$src_dotnet/dotnet.exe" "$src_dotnet/host" "$cache/dotnet/"
  cp -r "$src_dotnet/shared/Microsoft.NETCore.App/$rt" "$cache/dotnet/shared/Microsoft.NETCore.App/"
fi

if ! out="$(dotnet build "$here/CompileCheck.csproj" -c Release -nologo -v quiet -p:Game2="$game2" 2>&1)"; then
  echo "$out" >&2; echo "CompileCheck itself failed to build" >&2; exit 5
fi
dll="$here/bin/Release/net9.0/CompileCheck.dll"
args=("$(winpath "$mod")" "$project")
if [ "$project" = probe ]; then args+=("$(winpath "$dump")")
elif [ -n "$dump" ]; then args+=("$(winpath "$(mkdir -p "$dump" && cd "$dump" && pwd)")"); fi
WINEPREFIX="$cache/pfx" WINEDEBUG=-all DOTNET_ROLL_FORWARD=Major SE2_GAME2="$(winpath "$game2")" CC_DOCS="$docs" \
  wine "$cache/dotnet/dotnet.exe" "$(winpath "$dll")" "${args[@]}"
