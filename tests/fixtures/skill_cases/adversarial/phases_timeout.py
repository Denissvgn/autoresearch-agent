import json
import sys
import time

json.load(sys.stdin)
time.sleep(600)
print(json.dumps({"schema": "phase-advancement-plugin.v1", "advance": True}))
sys.exit(0)
