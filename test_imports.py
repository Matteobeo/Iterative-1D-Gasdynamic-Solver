import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    print("Testing imports...")
    from app.routes.simulate import simulate
    from app.models import SimulationRequest
    print("Imports successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Test finished.")
