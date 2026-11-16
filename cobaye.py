#!/usr/bin/env python3
"""cobaye: run the code samples of a course, README or exercise bank in a throwaway container and check
that each one prints what the text says it prints.

Samples come from Markdown (a ```c / ```ocaml / ```python / ```sh block followed by an ```output block) or from
JSON ([{"lang": "c", "code": "...", "expected": "..."}]). Everything runs in one Alpine container built once
and cached (`cobaye:<hash>`), started with no network, a read-only root, 256 MB of memory and a 5 s timeout
per sample. Outputs are compared with whitespace collapsed.

    python3 cobaye.py notes.md exercises.json
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

__version__ = "0.1.0"

# language -> (Alpine packages, file extension, shell command run in /w for file $f, output in $o)
LANGS = {
    "c": ("gcc musl-dev", "c", 'gcc -std=c99 -w -o /tmp/a.out "$f" > "$o" 2>&1 && timeout 5 /tmp/a.out >> "$o" 2>&1'),
    "ocaml": ("ocaml", "ml", 'timeout 5 ocaml -w -a -color=never -noprompt -nopromptcont < "$f" > "$o" 2>&1'),
    "python": ("python3", "py", 'timeout 5 python3 "$f" > "$o" 2>&1'),
    "sh": ("", "sh", 'timeout 5 sh "$f" > "$o" 2>&1'),
}
ALIASES = {"ml": "ocaml", "caml": "ocaml", "py": "python", "python3": "python", "bash": "sh", "shell": "sh"}
# OCaml toplevel banners and error position lines: not part of the answer a course shows
NOISE = re.compile(r"^(OCaml version|Enter #help|The OCaml toplevel|Line \d+|Characters \d+|\s*\d+ \||\s*\^+\s*$)")
FENCE = re.compile(r"^```[ \t]*([\w+-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)


def norm(text):
    lines = [x for x in text.splitlines() if x.strip() and not NOISE.match(x)]
    return " ".join(" ".join(lines).split())


def from_markdown(text, origin="?"):
    """Samples of a Markdown text: each code block in a known language directly followed by an `output` block."""
    blocks = [(m.group(1).lower(), m.group(2), text.count("\n", 0, m.start()) + 1) for m in FENCE.finditer(text)]
    out = []
    for (lang, code, line), (nxt, expected, _) in zip(blocks, blocks[1:]):
        lang = ALIASES.get(lang, lang)
        if lang in LANGS and nxt == "output":
            out.append({"lang": lang, "code": code, "expected": expected, "where": f"{origin}:{line}"})
    return out


def load(path):
    p = Path(path)
    if p.suffix == ".json":
        items = json.loads(p.read_text())
        return [{**x, "lang": ALIASES.get(x["lang"], x["lang"]), "where": x.get("where", f"{p}[{i}]")}
                for i, x in enumerate(items)]
    return from_markdown(p.read_text(), str(p))


def image(langs, docker="docker"):
    """Tag of a local image with the packages of `langs`; built once, then reused."""
    pkgs = " ".join(sorted({p for lang in langs for p in LANGS[lang][0].split()}))
    tag = "cobaye:" + hashlib.sha1(pkgs.encode()).hexdigest()[:10]
    if subprocess.run([docker, "image", "inspect", tag], capture_output=True).returncode:
        dockerfile = "FROM alpine:3.20\n" + (f"RUN apk add --no-cache {pkgs}\n" if pkgs else "")
        subprocess.run([docker, "build", "-q", "-t", tag, "-"], input=dockerfile.encode(), check=True,
                       stdout=subprocess.DEVNULL)
    return tag


def run(samples, docker="docker"):
    """Run every sample; returns the list of (sample, output) that do not match."""
    unknown = sorted({s["lang"] for s in samples} - set(LANGS))
    if unknown:
        raise ValueError(f"unknown language(s): {', '.join(unknown)} (known: {', '.join(LANGS)})")
    if not samples:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for i, s in enumerate(samples):
            ext, cmd = LANGS[s["lang"]][1], LANGS[s["lang"]][2]
            Path(tmp, f"{i:04}.{ext}").write_text(s["code"] if s["code"].endswith("\n") else s["code"] + "\n")
            lines.append(f'f=/w/{i:04}.{ext}; o=/w/{i:04}.out; {cmd}')
        Path(tmp, "run.sh").write_text("\n".join(lines) + "\n")
        subprocess.run([docker, "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:exec",
                        "--memory", "256m", "--pids-limit", "64", "-v", f"{tmp}:/w",
                        image({s["lang"] for s in samples}, docker), "sh", "/w/run.sh"], check=False)
        bad = []
        for i, s in enumerate(samples):
            out = Path(tmp, f"{i:04}.out")
            got = out.read_text() if out.exists() else ""
            if norm(got) != norm(s["expected"]):
                bad.append((s, got))
        return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help="Markdown or JSON files")
    ap.add_argument("--docker", default="docker", help="container command (docker or podman)")
    ap.add_argument("--list", action="store_true", help="only list the samples found")
    a = ap.parse_args(argv)
    samples = [s for f in a.files for s in load(f)]
    if a.list:
        for s in samples:
            print(f"{s['where']}  {s['lang']}")
        return 0
    bad = run(samples, a.docker)
    for s, got in bad:
        print(f"✗ {s['where']} ({s['lang']})\n--- expected\n{s['expected'].strip()}\n--- got\n{got.strip()}\n")
    print(f"{len(samples) - len(bad)}/{len(samples)} samples OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
