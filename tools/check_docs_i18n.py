#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that every prose document and diagram has a Chinese version.

The project rule is: every document ships with a `.zh-CN.md` mirror, and every
diagram ships with a `.zh-CN.svg` and `.zh-CN.png`. This script is intentionally
dependency-free so CI can run it before installing the package.

Exit code 0 means the coverage is complete; 1 lists what is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# English source -> Chinese mirror.
PAIRS = {
    "README.md": "README.zh-CN.md",
    "CHANGELOG.md": "CHANGELOG.zh-CN.md",
    "CONTRIBUTING.md": "CONTRIBUTING.zh-CN.md",
    "docs/README.md": "docs/README.zh-CN.md",
    "docs/algorithm.md": "docs/algorithm.zh-CN.md",
    "docs/api.md": "docs/api.zh-CN.md",
    "docs/architecture.md": "docs/architecture.zh-CN.md",
    "docs/benchmarks.md": "docs/benchmarks.zh-CN.md",
    "docs/defensive-publication.md": "docs/defensive-publication.zh-CN.md",
    "docs/related-work.md": "docs/related-work.zh-CN.md",
    "docs/articles/why-per-bucket-queries-are-slow.md":
        "docs/articles/why-per-bucket-queries-are-slow.zh-CN.md",
    "skills/README.md": "skills/README.zh-CN.md",
    "skills/hybrid-recursive-ladder/SKILL.md":
        "skills/hybrid-recursive-ladder/SKILL.zh-CN.md",
    "skills/hybrid-recursive-ladder/reference.md":
        "skills/hybrid-recursive-ladder/reference.zh-CN.md",
    "packages/hybrid-recursive-ladder-mcp/README.md":
        "packages/hybrid-recursive-ladder-mcp/README.zh-CN.md",
}

# Chinese-only documents: they satisfy the rule by themselves.
CHINESE_ONLY = {
    "LICENSE.zh-CN.md",
    "docs/prior-art-search.zh-CN.md",
    "docs/publishing.md",
}

# Data files with an explicit Chinese mirror.
DATA_PAIRS = {
    "docs/prior-art-matrix.csv": "docs/prior-art-matrix.zh-CN.csv",
}

# The English LICENSE is plain text; it cannot carry a markdown switcher.
NO_SWITCHER_CHECK = {"LICENSE"}

ASSET_LANGUAGES = {
    "ar", "de", "es", "fr", "hi", "ja", "ko", "pt-BR", "ru", "zh-CN",
}

# README translations already exist for these; they are not English sources.
README_TRANSLATIONS = {
    "README.ar.md", "README.de.md", "README.es.md", "README.fr.md",
    "README.hi.md", "README.ja.md", "README.ko.md", "README.pt-BR.md",
    "README.ru.md", "README.zh-CN.md",
}

SKIP_DIRS = {".git", ".pytest_cache", ".ruff_cache", "dist", "dist-pypi",
             "build", "__pycache__", "node_modules"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    errors: list[str] = []

    for english, chinese in PAIRS.items():
        en_path = ROOT / english
        zh_path = ROOT / chinese
        if not en_path.is_file():
            errors.append(f"missing English document: {english}")
            continue
        if not zh_path.is_file():
            errors.append(f"missing Chinese mirror: {chinese}")
            continue
        if english not in NO_SWITCHER_CHECK and "简体中文" not in _read(en_path):
            errors.append(f"{english}: no 简体中文 language link")
        if "English" not in _read(zh_path):
            errors.append(f"{chinese}: no English language link")

    for chinese in CHINESE_ONLY:
        if not (ROOT / chinese).is_file():
            errors.append(f"missing Chinese-only document: {chinese}")
        elif "简体中文" not in _read(ROOT / chinese):
            errors.append(f"{chinese}: no 简体中文 language marker")

    for english, chinese in DATA_PAIRS.items():
        if not (ROOT / english).is_file():
            errors.append(f"missing data file: {english}")
        if not (ROOT / chinese).is_file():
            errors.append(f"missing Chinese data mirror: {chinese}")

    # Any new markdown file must be registered as a pair, a Chinese-only doc,
    # or a translated README; otherwise the coverage rule would silently slip.
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS or part.startswith(".venv")
               for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in PAIRS or rel in PAIRS.values() or rel in CHINESE_ONLY:
            continue
        if rel in README_TRANSLATIONS:
            continue
        errors.append(
            f"unregistered document: {rel} "
            "(add it to PAIRS or CHINESE_ONLY in tools/check_docs_i18n.py)"
        )

    # Every diagram without a language suffix needs a Chinese SVG and PNG.
    assets = ROOT / "docs" / "assets"
    if assets.is_dir():
        for svg in sorted(assets.glob("*.svg")):
            stem = svg.name[:-4]
            parts = stem.split(".")
            if len(parts) > 1 and parts[-1] in ASSET_LANGUAGES:
                continue
            for suffix in (".zh-CN.svg", ".zh-CN.png"):
                candidate = assets / f"{stem}{suffix}"
                if not candidate.is_file():
                    errors.append(f"missing Chinese diagram asset: {candidate.relative_to(ROOT)}")

    if errors:
        print("Documentation i18n check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"Documentation i18n OK: {len(PAIRS)} paired documents, "
        f"{len(DATA_PAIRS)} paired data files, "
        f"{len(CHINESE_ONLY)} Chinese-only documents, diagrams covered."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
