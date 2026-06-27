import multiprocessing
import time
import sys

def run_backend():
    from sao.backend.server import serve
    serve()

def run_frontend():
    from sao.frontend.app import main
    main()

if __name__ == "__main__":
    # Start backend process
    backend_process = multiprocessing.Process(target=run_backend, daemon=True)
    backend_process.start()
    
    # Give backend a moment to start
    time.sleep(1)
    
    # Start frontend in main thread (PyQt requires main thread)
    run_frontend()
    
    backend_process.terminate()
