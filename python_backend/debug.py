from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    root_debug = project_root / "debug.py"
    runpy.run_path(str(root_debug), run_name="__main__")
