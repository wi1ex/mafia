from __future__ import annotations
import argparse
import os
from pathlib import Path

SKIP_DIRS_DEFAULT = {"node_modules", "public", "assets", ".git", ".idea"}
SKIP_FILES_DEFAULT = {"package-lock.json"}
SEPARATOR = "__________________________________"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Собирает весь код проекта в один текстовый файл и пишет сводку по строкам.")
    p.add_argument("-o", "--output", default="project_code.txt", help="Путь к выходному файлу (по умолчанию: project_code.txt)")
    p.add_argument("--skip", nargs="*", default=[], help="Дополнительные имена папок для пропуска (через пробел).")
    p.add_argument("--skip-files", nargs="*", default=[], help="Дополнительные имена файлов для пропуска (через пробел).")
    p.add_argument("--sort", choices=["path", "lines"], default="path", help="Порядок файлов в основной части: path|lines (по умолчанию path).")
    return p.parse_args()

def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return True

def walk_project(root: Path, skip_dirs: set[str], skip_files: set[str]) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if name in skip_files:
                continue
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            files.append(p)
    return files

def main() -> None:
    args = parse_args()
    root = Path.cwd().resolve()
    out_path = (root / args.output).resolve()
    skip_dirs = set(SKIP_DIRS_DEFAULT) | set(args.skip)
    skip_files = set(SKIP_FILES_DEFAULT) | set(args.skip_files)

    files = walk_project(root, skip_dirs, skip_files)
    files = [p for p in files if p.resolve() != out_path]

    entries: list[tuple[str, str, int]] = []
    for p in files:
        if is_binary(p):
            continue
        rel = p.relative_to(root).as_posix()
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        line_count = len(content.splitlines())
        entries.append((rel, content, line_count))

    if args.sort == "path":
        entries.sort(key=lambda t: t[0])
    else:
        entries.sort(key=lambda t: (-t[2], t[0]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as out:
        for rel, content, line_count in entries:
            out.write(f"{rel}:\n\n")
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write("\n")
            out.write(SEPARATOR)
            out.write("\n\n")

if __name__ == "__main__":
    main()
