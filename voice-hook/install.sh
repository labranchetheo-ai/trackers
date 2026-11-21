#!/bin/bash
# Installs the voice hook in ~/.claude (macOS). Run: bash voice-hook/install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.claude/hooks
cp "$DIR/speak.py" ~/.claude/hooks/speak.py
chmod +x ~/.claude/hooks/speak.py
touch ~/.claude/voice_on

# Adds the Stop hook to ~/.claude/settings.json without touching the rest (backup first).
python3 - <<'EOF'
import json, os, shutil
p = os.path.expanduser("~/.claude/settings.json")
s = {}
if os.path.exists(p):
    shutil.copy(p, p + ".bak")
    with open(p) as f:
        s = json.load(f)
cmd = "python3 ~/.claude/hooks/speak.py"
stop = s.setdefault("hooks", {}).setdefault("Stop", [])
if not any(h.get("command") == cmd for g in stop for h in g.get("hooks", [])):
    stop.append({"hooks": [{"type": "command", "command": cmd, "async": True}]})
with open(p, "w") as f:
    json.dump(s, f, indent=2)
print("Hook Stop ajouté dans", p)
EOF

if [ -z "$ELEVENLABS_API_KEY" ]; then
  echo "Il manque ELEVENLABS_API_KEY : ajoute-la à ~/.zshrc puis ouvre un nouveau terminal."
fi
echo "Installé. Voix : ON (rm ~/.claude/voice_on pour couper)."
