import os

CODE_EXTENSIONS = {
    ".py", ".js",
    ".java",
    ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs",
    ".php", ".rb", ".swift",
    ".kt", ".kts"
    # KHÔNG có .ts, .tsx
}

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules",
    "venv", ".venv", "dist", "build"
}

def print_tree(path, prefix=""):
    try:
        items = sorted(os.listdir(path))
    except PermissionError:
        return

    filtered_items = []
    for item in items:
        full_path = os.path.join(path, item)

        if os.path.isdir(full_path):
            if item in IGNORE_DIRS:
                continue
            filtered_items.append(item)

        elif os.path.splitext(item)[1] in CODE_EXTENSIONS:
            filtered_items.append(item)

    for i, item in enumerate(filtered_items):
        full_path = os.path.join(path, item)
        is_last = (i == len(filtered_items) - 1)

        connector = "└── " if is_last else "├── "
        print(prefix + connector + item)

        if os.path.isdir(full_path):
            extension = "    " if is_last else "│   "
            print_tree(full_path, prefix + extension)

# Usage
print_tree(r"D:\dev\yt_manage_app")
