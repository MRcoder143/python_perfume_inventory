import os
import sys
import streamlit.web.cli as stcli

if __name__ == "__main__":
    # Point directly to the location of the unzipped app file next to the EXE
    current_dir = os.path.dirname(sys.executable)
    app_path = os.path.join(current_dir, "app.py")

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
