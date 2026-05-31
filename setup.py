build_exe_options = {
    "packages": [
        "streamlit", 
        "sqlite3", 
        "pandas", 
        "datetime", 
        "io",
        "uvicorn",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        # 👑 CRITICAL FIXED PACKAGES FOR PANDAS TABLES
        "pyarrow",
        "pyarrow.vendored",
        "pyarrow.vendored.version"
    ],
    "excludes": [],
    "include_files": [
        ("app.py", "app.py"),
        ("inventory.db", "inventory.db")
    ],
    "zip_include_packages": [], 
    "zip_exclude_packages": ["*"] 
}
