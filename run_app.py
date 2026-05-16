import os
import sys

# 🛑 CRITICAL WORKAROUND: Force PyInstaller to capture Streamlit runtime dependencies
import streamlit.runtime
import streamlit.runtime.scriptrunner
import streamlit.runtime.scriptrunner.magic_funcs
import streamlit.web.cli as stcli

def get_resource_path():
    """ Resolves absolute path to resource, working for dev and PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(__file__)

if __name__ == '__main__':
    base_path = get_resource_path()
    script_path = os.path.join(base_path, 'app.py')
    
    sys.argv = ["streamlit", "run", script_path, "--global.developmentMode=false"]
    sys.exit(stcli.main())
