import multiprocessing
import time
import sys

def run_backend(shutdown_event):
    from sao.backend.server import serve
    serve(shutdown_event)

def run_frontend():
    from sao.frontend.app import main
    main()

if __name__ == "__main__":
    # Start backend process
    backend_shutdown = multiprocessing.Event()
    backend_process = multiprocessing.Process(target=run_backend, args=(backend_shutdown,), daemon=True)
    backend_process.start()
    try:
        # Give backend a moment to start
        time.sleep(1)

        # Start frontend in main thread (PyQt requires main thread)
        run_frontend()
    finally:
        if backend_process.is_alive():
            backend_shutdown.set()
            backend_process.join(timeout=10)
        if backend_process.is_alive():
            backend_process.kill()
            backend_process.join(timeout=5)
