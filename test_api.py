import urllib.request
import json

payload = {
  "P0": 500000,
  "T0": 600,
  "P_amb": 101325,
  "gamma": 1.4,
  "R": 287.0,
  "components": [
    {
      "type": "convergent",
      "params": {
        "d_in": 0.1,
        "d_out": 0.05,
        "length": 0.1
      }
    }
  ],
  "solver_type": "analytical"
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request("http://localhost:8000/api/simulate", data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as f:
        print(f"Status: {f.getcode()}")
        resp = json.loads(f.read().decode('utf-8'))
        if "data" in resp and resp["data"]:
            print("Fields in data:", list(resp["data"].keys()))
        else:
            print("Response:", resp)
except Exception as e:
    print(f"Error: {e}")
