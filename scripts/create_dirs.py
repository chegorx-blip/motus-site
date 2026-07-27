import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

paths = [
    os.path.join(BASE, "docs", "docs1"),
    os.path.join(BASE, "scripts"),
]

for path in paths:
    os.makedirs(path, exist_ok=True)
    print(f"created: {path}")
