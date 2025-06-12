# D:\Project2\test_import.py
import sys
import os

print("--- test_import.py sys.path ---")
print(sys.path)
print("--- test_import.py CWD ---")
print(os.getcwd())
print("------------------------------")

print("Attempting import...")
try:
    # Try importing the specific module directly using the package path
    from backend.routers import auth
    print("SUCCESS: Imported backend.routers.auth")

    # Optionally try importing the module main depends on
    # import backend.main # This might trigger the error if it's deep inside main.py
    # print("SUCCESS: Imported backend.main (which should import routers)")

except ModuleNotFoundError as e:
    print(f"FAILED: Could not import - {e}")
except ImportError as e:
    print(f"FAILED: Could not import (ImportError) - {e}")