import multiprocessing
import subprocess
import time
import sys
import os
from dotenv import load_dotenv

def run_backend(shutdown_event):
    from sao.backend.server import serve
    serve(shutdown_event)

def run_pyqt_frontend():
    from sao.frontend.app import main
    main()

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    
    frontend_mode = os.environ.get("SAO_FRONTEND", "pyqt").lower()

    # Start backend process
    backend_shutdown = multiprocessing.Event()
    backend_process = multiprocessing.Process(target=run_backend, args=(backend_shutdown,), daemon=True)
    backend_process.start()
    try:
        # Give backend a moment to start
        time.sleep(1)

        if frontend_mode == "streamlit":
            print("Starting Streamlit frontend...")
            # Use subprocess to run streamlit
            subprocess.run([sys.executable, "-m", "streamlit", "run", "sao/frontend/streamlit_app.py"])
        else:
            print("Starting PyQt frontend...")
            # Start frontend in main thread (PyQt requires main thread)
            run_pyqt_frontend()
    except KeyboardInterrupt:
        pass
    finally:
        if backend_process.is_alive():
            backend_shutdown.set()
            backend_process.join(timeout=10)
        if backend_process.is_alive():
            backend_process.kill()
            backend_process.join(timeout=5)
