import requests
import json

with open("backend/last_request.json", "r") as f:
    req_data = json.load(f)

res = requests.post("http://localhost:8000/api/simulate", json=req_data)
data = res.json()

if "data" in data and "Mach" in data["data"]:
    machs = data["data"]["Mach"]
    has_shock = False
    for i in range(1, len(machs)):
        if machs[i-1] > 1.0 and machs[i] < 1.0:
            print(f"Shock detected in API response at Mach drop from {machs[i-1]:.2f} to {machs[i]:.2f}")
            has_shock = True
    
    if not has_shock:
        print("No shock detected in the API response!")
    print("Warnings:", data.get("warnings", []))
else:
    print("Error in API response:", data)
