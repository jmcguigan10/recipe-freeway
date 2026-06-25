#!/usr/bin/env python
import sys

import ROOT


def main() -> int:
    path = sys.argv[1]
    expected_tree = sys.argv[2] if len(sys.argv) > 2 else ""

    ROOT.gROOT.SetBatch(True)
    try:
        root_file = ROOT.TFile.Open(path, "READ")
    except OSError as exc:
        print(f"Could not open ROOT file: {path}: {exc}", file=sys.stderr)
        return 1
    if not root_file:
        print(f"Could not open ROOT file: {path}", file=sys.stderr)
        return 1
    if root_file.IsZombie():
        print(f"ROOT file is zombie/corrupt: {path}", file=sys.stderr)
        root_file.Close()
        return 1

    keys = [key.GetName() for key in root_file.GetListOfKeys()]
    if not keys:
        print(f"ROOT file has no keys: {path}", file=sys.stderr)
        root_file.Close()
        return 1

    if expected_tree:
        obj = root_file.Get(expected_tree)
        if not obj:
            print(
                f"ROOT file is missing expected tree {expected_tree!r}: {path}",
                file=sys.stderr,
            )
            print(f"Available keys: {', '.join(keys)}", file=sys.stderr)
            root_file.Close()
            return 1
        if not obj.InheritsFrom("TTree"):
            print(
                f"Expected key {expected_tree!r} is not a TTree in {path}",
                file=sys.stderr,
            )
            root_file.Close()
            return 1

    root_file.Close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
