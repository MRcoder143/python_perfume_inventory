import os
import sys
import streamlit.web.cli as stcli

if __name__ == "__main__":
    # FIXED: sys.argv[0] gets the true directory where the user clicked the .exe file
    exe_dir = os.path.dirname(sys.argv[0])
    script_path = os.path.join(exe_dir, "app.py")
    
    # Check if app.py is missing and show a helpful warning if it is
    if not os.path.exists(script_path):
        print(f"CRITICAL ERROR: 'app.py' not found at: {script_path}")
        print("Please ensure app.py is placed in the exact same folder as this executable.")
        input("Press Enter to close...")
        sys.exit(1)

    sys.argv = ["streamlit", "run", script_path, "--global.developmentMode=false"]
    sys.exit(stcli.main())
