#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clone_all.py
============
Clona varios repositorios git de uma vez e grava um manifesto (pasta -> grupo)
que o mine_repos.py usa para juntar grupos com mais de um repositorio.

FORMATO DO repos.txt
--------------------
Uma entrada por linha:
    https://github.com/usuario/projeto --> grupo 1
    https://github.com/usuario/outro   --> grupo 1   (mesmo grupo, 2 repos: OK)

Quando houver "--> rotulo", o rotulo eh o nome do grupo. Dois repos com o mesmo
rotulo serao SOMADOS pelo minerador. Linhas em branco / iniciadas por # sao ignoradas.

Corrige automaticamente URLs com /tree/... ou /blob/... e fragmentos (#...).

USO
---
    python clone_all.py repos.txt --dest ./repos
    python mine_repos.py ./repos --out ./resultados
"""

import argparse
import csv
import os
import re
import subprocess
import sys
from urllib.parse import urlparse


def parse_line(line):
    label = None
    m = re.split(r"\s*-+>\s*", line, maxsplit=1)
    url_part = m[0].strip()
    if len(m) > 1:
        label = m[1].strip()
    url = url_part.split()[0] if url_part.split() else ""
    url = url.split("#")[0].rstrip("/")
    for marker in ("/tree/", "/blob/"):
        if marker in url:
            url = url.split(marker)[0]
    return url, label


def safe_name(s):
    s = re.sub(r'[<>:"/\\|?*]', "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s or "repo"


def repo_name_from_url(url):
    path = urlparse(url).path if "://" in url else url
    name = path.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"


def repo_looks_valid(url):
    path = urlparse(url).path.strip("/")
    return url.startswith("http") and len(path.split("/")) >= 2


def load_entries(list_file):
    entries = []
    with open(list_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                entries.append(parse_line(line))
    return entries


def main():
    ap = argparse.ArgumentParser(description="Clona varios repos git de uma lista.")
    ap.add_argument("list_file")
    ap.add_argument("--dest", default="./repos")
    args = ap.parse_args()

    if not os.path.isfile(args.list_file):
        sys.exit(f"Arquivo nao encontrado: {args.list_file}")

    entries = load_entries(args.list_file)
    if not entries:
        sys.exit("Nenhuma URL valida no arquivo.")

    os.makedirs(args.dest, exist_ok=True)
    used = set()
    ok, skipped, failed = 0, 0, 0
    problems = []
    manifest = []   # (pasta, grupo)

    for url, label in entries:
        if not repo_looks_valid(url):
            print(f"[!] URL parece NAO ser de um repositorio (falta usuario/projeto?): {url}")
            problems.append(url)
            failed += 1
            continue

        group = label.strip() if label else repo_name_from_url(url)
        base = safe_name(group)
        final = base
        i = 2
        while final in used:
            final = f"{base}_{i}"
            i += 1
        used.add(final)

        target = os.path.join(args.dest, final)
        manifest.append((final, group))

        if os.path.isdir(os.path.join(target, ".git")):
            print(f"[=] ja existe, pulando: {final}")
            skipped += 1
            continue

        print(f"[+] clonando {url} -> {final}  (grupo: {group})")
        result = subprocess.run(["git", "clone", "--quiet", url, target])
        if result.returncode == 0:
            ok += 1
        else:
            print(f"    [!] FALHOU: {url} (repo privado? URL errada?)")
            problems.append(url)
            failed += 1

    # grava o manifesto pasta -> grupo
    man_path = os.path.join(args.dest, "repos_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pasta", "grupo"])
        w.writerows(manifest)

    print(f"\n[OK] clonados: {ok} | pulados: {skipped} | falharam: {failed}")
    print(f"[OK] manifesto salvo em {man_path}")
    if problems:
        print("\nURLs com problema (corrija no repos.txt e rode de novo):")
        for p in problems:
            print(f"   - {p}")


if __name__ == "__main__":
    main()
