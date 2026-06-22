#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mine_repos.py
=============
Minerador de repositorios git para os dois artigos do CTIC-ES (CBSoft 2026).

Le um manifesto (repos_manifest.csv, gerado pelo clone_all.py) para saber qual
pasta pertence a qual grupo. Grupos com VARIOS repositorios sao SOMADOS.
Se nao houver manifesto, cada pasta vira um grupo.

Saidas (pasta --out):
  - colaboracao.csv         (Tema 1: por aluno, anonimizado)
  - colaboracao_grupos.csv  (Tema 1: resumo por grupo: Gini, % do maior, etc.)
  - tecnologias.csv         (Tema 2: linguagens + ferramentas por grupo)
  - commits_por_semana.csv  (Tema 1: serie temporal por grupo)
  - resumo.json             (tudo junto, util pra graficos)
  - _chave_privada.csv      (NAO publicar: Aluno N -> email/nome reais)

USO:
    python mine_repos.py ./repos --out ./resultados
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict, Counter
from datetime import datetime

MARKDOWN_EXTS = {".md", ".markdown", ".rst", ".txt"}

LANG_BY_EXT = {
    ".py": "Python", ".ipynb": "Jupyter",
    ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin",
    ".c": "C", ".h": "C/C++ header", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".ino": "Arduino/C++", ".cs": "C#", ".go": "Go", ".rs": "Rust",
    ".php": "PHP", ".rb": "Ruby", ".swift": "Swift", ".dart": "Dart",
    ".html": "HTML", ".css": "CSS", ".scss": "CSS", ".sql": "SQL",
    ".sh": "Shell", ".r": "R", ".m": "MATLAB/Obj-C", ".vhd": "VHDL", ".v": "Verilog",
}

TOOL_SIGNATURES = {
    "package.json": "Node.js / npm", "yarn.lock": "Yarn",
    "requirements.txt": "Python (pip)", "pyproject.toml": "Python (poetry/pep517)",
    "Pipfile": "Python (pipenv)", "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)", "Cargo.toml": "Rust (Cargo)",
    "go.mod": "Go modules", "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)", "platformio.ini": "PlatformIO (IoT/embarcado)",
    "CMakeLists.txt": "CMake (C/C++)", "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose", "docker-compose.yaml": "Docker Compose",
    ".github/workflows": "GitHub Actions (CI)", "tsconfig.json": "TypeScript",
    "vite.config.js": "Vite", "vite.config.ts": "Vite",
    "next.config.js": "Next.js", "tailwind.config.js": "Tailwind CSS",
    "Makefile": "Make", "firebase.json": "Firebase", "supabase": "Supabase",
}

# pastas de dependencia que NAO devem contar como codigo dos alunos
VENDOR_DIRS = ("node_modules/", "venv/", ".venv/", "dist/", "build/",
               "vendor/", "site-packages/", ".git/")


def is_markdown(path):
    return os.path.splitext(path)[1].lower() in MARKDOWN_EXTS


def is_vendor(path):
    p = path.replace("\\", "/")
    return any(d in p for d in VENDOR_DIRS)


def new_author():
    return {"name": "", "commits": 0, "code_add": 0, "code_del": 0,
            "doc_add": 0, "doc_del": 0, "dates": []}


def run_git(repo, args):
    try:
        out = subprocess.run(["git", "-C", repo] + args,
                             capture_output=True, text=True, errors="replace")
        return out.stdout
    except FileNotFoundError:
        sys.exit("ERRO: 'git' nao encontrado. Instale o git e tente de novo.")


def gini(values):
    vals = sorted(v for v in values if v >= 0)
    n = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    cum = sum(i * v for i, v in enumerate(vals, start=1))
    return (2 * cum) / (n * sum(vals)) - (n + 1) / n


def parse_commits_into(repo, authors, weekly):
    """Acumula estatisticas de commits de UM repo nos dicionarios passados."""
    SEP = "\x01"
    fmt = f"@@@%H{SEP}%ae{SEP}%an{SEP}%ad"
    raw = run_git(repo, ["log", "--no-merges", "--date=short",
                         f"--pretty=format:{fmt}", "--numstat"])
    cur = None
    for line in raw.splitlines():
        if line.startswith("@@@"):
            _, email, name, date = line[3:].split(SEP)
            cur = email.strip().lower()
            a = authors[cur]
            a["name"] = name
            a["commits"] += 1
            a["dates"].append(date)
            try:
                iso = datetime.strptime(date, "%Y-%m-%d").isocalendar()
                weekly[f"{iso[0]}-W{iso[1]:02d}"] += 1
            except ValueError:
                pass
        elif line.strip() and cur is not None:
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            if added == "-" or deleted == "-" or is_vendor(path):
                continue
            a = authors[cur]
            if is_markdown(path):
                a["doc_add"] += int(added)
                a["doc_del"] += int(deleted)
            else:
                a["code_add"] += int(added)
                a["code_del"] += int(deleted)


def scan_tech_into(repo, langs, tools):
    for f in run_git(repo, ["ls-files"]).splitlines():
        if is_vendor(f):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in LANG_BY_EXT:
            langs[LANG_BY_EXT[ext]] += 1
        base = os.path.basename(f)
        for sig, tool in TOOL_SIGNATURES.items():
            if base == sig or sig in f:
                tools.add(tool)


def anonymize(authors, group_label):
    ordered = sorted(authors.items(), key=lambda kv: -kv[1]["commits"])
    anon, key_rows = {}, []
    for i, (email, data) in enumerate(ordered, start=1):
        label = f"Aluno {i}"
        anon[email] = label
        key_rows.append({"grupo": group_label, "anon": label, "email": email,
                         "nome": data["name"], "commits": data["commits"]})
    return anon, key_rows


def list_groups(root):
    """Devolve {grupo: [pasta_repo, ...]} usando o manifesto se existir."""
    folder_to_group = {}
    man = os.path.join(root, "repos_manifest.csv")
    if os.path.isfile(man):
        with open(man, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                folder_to_group[row["pasta"]] = row["grupo"]
    groups = defaultdict(list)
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, ".git")):
            groups[folder_to_group.get(name, name)].append(full)
    return groups


def main():
    ap = argparse.ArgumentParser(description="Minera repos git para o CTIC-ES.")
    ap.add_argument("root")
    ap.add_argument("--out", default="./resultados")
    args = ap.parse_args()

    groups = list_groups(args.root)
    if not groups:
        sys.exit(f"Nenhum repo git encontrado em {args.root}.")
    os.makedirs(args.out, exist_ok=True)

    collab_rows, group_rows, tech_rows, weekly_rows, key_rows_all = [], [], [], [], []
    full = {}

    for group_label in sorted(groups):
        repos = groups[group_label]
        print(f"[+] {group_label}: {len(repos)} repo(s)")
        authors = defaultdict(new_author)
        weekly = Counter()
        langs = Counter()
        tools = set()
        for repo in repos:
            parse_commits_into(repo, authors, weekly)
            scan_tech_into(repo, langs, tools)

        anon, key_rows = anonymize(authors, group_label)
        key_rows_all.extend(key_rows)

        total = sum(a["commits"] for a in authors.values())
        counts = [a["commits"] for a in authors.values()]
        top_pct = (max(counts) / total * 100) if total else 0.0
        g = gini(counts)

        for email, data in authors.items():
            collab_rows.append({
                "grupo": group_label, "autor": anon[email],
                "commits": data["commits"],
                "pct_commits": round(data["commits"] / total * 100, 1) if total else 0,
                "linhas_codigo_add": data["code_add"], "linhas_codigo_del": data["code_del"],
                "linhas_doc_add": data["doc_add"], "linhas_doc_del": data["doc_del"],
            })

        group_rows.append({
            "grupo": group_label, "n_repos": len(repos), "n_autores": len(authors),
            "total_commits": total, "pct_maior_contribuidor": round(top_pct, 1),
            "gini_commits": round(g, 3),
        })

        for lang, n in langs.most_common():
            tech_rows.append({"grupo": group_label, "tipo": "linguagem", "item": lang, "n_arquivos": n})
        for tool in sorted(tools):
            tech_rows.append({"grupo": group_label, "tipo": "ferramenta", "item": tool, "n_arquivos": ""})
        for week, n in sorted(weekly.items()):
            weekly_rows.append({"grupo": group_label, "semana": week, "commits": n})

        full[group_label] = {"resumo": group_rows[-1], "linguagens": dict(langs),
                             "ferramentas": sorted(tools)}

    def write_csv(name, rows, fields):
        path = os.path.join(args.out, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"    -> {path}")

    write_csv("colaboracao.csv", collab_rows,
              ["grupo", "autor", "commits", "pct_commits",
               "linhas_codigo_add", "linhas_codigo_del", "linhas_doc_add", "linhas_doc_del"])
    write_csv("colaboracao_grupos.csv", group_rows,
              ["grupo", "n_repos", "n_autores", "total_commits",
               "pct_maior_contribuidor", "gini_commits"])
    write_csv("tecnologias.csv", tech_rows, ["grupo", "tipo", "item", "n_arquivos"])
    write_csv("commits_por_semana.csv", weekly_rows, ["grupo", "semana", "commits"])
    write_csv("_chave_privada.csv", key_rows_all, ["grupo", "anon", "email", "nome", "commits"])

    with open(os.path.join(args.out, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    print(f"    -> {os.path.join(args.out, 'resumo.json')}")
    print("\n[OK] Pronto. NAO publique o _chave_privada.csv (tem nome/email reais).")


if __name__ == "__main__":
    main()
