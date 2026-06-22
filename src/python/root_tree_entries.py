#!/usr/bin/env python
import sys

import ROOT


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: root_tree_entries.py <root-file> <tree>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    tree_name = sys.argv[2]

    ROOT.gROOT.SetBatch(True)
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        print(f"Could not open ROOT file: {path}", file=sys.stderr)
        return 1

    tree = root_file.Get(tree_name)
    if not tree or not tree.InheritsFrom("TTree"):
        print(f"Missing ROOT tree {tree_name!r}: {path}", file=sys.stderr)
        root_file.Close()
        return 1

    print(int(tree.GetEntries()))
    root_file.Close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
