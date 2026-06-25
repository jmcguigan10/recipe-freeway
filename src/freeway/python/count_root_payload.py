#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

import ROOT


def load_muse_libraries() -> None:
    roots = []
    cookerhome = os.environ.get("COOKERHOME")
    if cookerhome:
        roots.append(Path(cookerhome) / "muse" / "lib")
    roots.append(Path.cwd() / ".local" / "bin" / "muse" / "lib")
    roots.append(Path.cwd() / ".install" / "build" / "muse" / "lib")

    names = [
        "libPlugin",
        "libmusetree",
        "libsctools",
        "libBH",
        "libSPS",
        "libVETO",
        "libBM",
        "libVertexRecon",
        "libPathLength",
        "libTracklet",
        "libGEM_tracks",
        "libcs",
    ]
    suffixes = [".1.1.0.so", ".1.1.0.dylib", ".so", ".dylib", ""]

    for root in roots:
        if root.exists():
            ROOT.gSystem.AddDynamicPath(str(root))
    for name in names:
        loaded = -1
        for root in roots:
            for suffix in suffixes:
                candidate = root / f"{name}{suffix}"
                if candidate.exists() and ROOT.gSystem.Load(str(candidate)) >= 0:
                    loaded = 0
                    break
            if loaded >= 0:
                break
        if loaded < 0:
            ROOT.gSystem.Load(name)


def value_size(value) -> int:
    try:
        return len(value)
    except TypeError:
        pass
    try:
        return int(value.size())
    except AttributeError:
        return 0


def object_payload_size(obj, field: str) -> int:
    value = obj
    for part in field.split("."):
        value = getattr(value, part)
    return value_size(value)


def parse_args():
    parser = argparse.ArgumentParser(description="Count payload objects in a ROOT tree branch.")
    parser.add_argument("root_file")
    parser.add_argument("tree")
    parser.add_argument("branch")
    parser.add_argument("field", nargs="?", default="hits")
    parser.add_argument("--min-total", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ROOT.gROOT.SetBatch(True)
    load_muse_libraries()

    root_file = ROOT.TFile.Open(args.root_file, "READ")
    if not root_file or root_file.IsZombie():
        print(f"Could not open ROOT file: {args.root_file}", file=sys.stderr)
        return 1

    tree = root_file.Get(args.tree)
    if not tree or not tree.InheritsFrom("TTree"):
        print(f"Missing ROOT tree {args.tree!r}: {args.root_file}", file=sys.stderr)
        root_file.Close()
        return 1
    if not tree.GetBranch(args.branch):
        print(f"Missing ROOT branch {args.branch!r} in {args.tree}: {args.root_file}", file=sys.stderr)
        root_file.Close()
        return 1

    total = 0
    nonempty = 0
    entries = int(tree.GetEntries())
    for index in range(entries):
        tree.GetEntry(index)
        try:
            count = object_payload_size(getattr(tree, args.branch), args.field)
        except AttributeError as exc:
            print(
                f"Could not read {args.tree}.{args.branch}.{args.field}: {exc}",
                file=sys.stderr,
            )
            root_file.Close()
            return 1
        if count:
            nonempty += 1
            total += count

    root_file.Close()
    print(
        f"{args.tree}.{args.branch}.{args.field}: "
        f"entries={entries} nonempty_events={nonempty} total_items={total}"
    )
    if total < args.min_total:
        print(
            f"Payload total {total} is below required minimum {args.min_total}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
