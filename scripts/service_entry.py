"""PyInstaller entry point; no GUI or external Python installation required."""
from ssh_forwarder.service import BackendService

if __name__ == "__main__":
    BackendService().run()
