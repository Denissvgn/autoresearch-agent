import json
import sys

json.load(sys.stdin)
print(json.dumps({"schema": "some-other-schema.v9", "advance": True}))
