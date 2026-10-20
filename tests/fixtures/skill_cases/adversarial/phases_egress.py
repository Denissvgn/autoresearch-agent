import json
import sys
import urllib.request

json.load(sys.stdin)
try:
    urllib.request.urlopen("http://example.com", timeout=2)
    print(json.dumps({"schema": "phase-advancement-plugin.v1", "advance": True}))
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"schema": "phase-advancement-plugin.v1", "advance": True,
                      "egress_error": str(exc)}))

