import time

from python_backend.api.auth.scheduler import start_scheduler, stop_scheduler
from python_backend.bootstrap import initialize_app_state
from python_backend.config import load_env


def main() -> None:
    load_env()
    initialize_app_state()
    start_scheduler()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop_scheduler()


if __name__ == "__main__":
    main()
