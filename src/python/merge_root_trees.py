#!/usr/bin/env python
import sys

import ROOT


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def load_muse_dictionaries() -> None:
    ROOT.gROOT.SetBatch(True)
    for library in ("libmusetree", "libRunInfo"):
        ROOT.gSystem.Load(library)


def copy_run_info(output_file, first_input) -> None:
    run_info = first_input.Get("RunInfo")
    if run_info:
        output_file.cd()
        run_info.Write("RunInfo", ROOT.TObject.kOverwrite)


def main() -> int:
    if len(sys.argv) < 4:
        return fail("usage: merge_root_trees.py <output.root> <tree-name> <input.root> [input.root ...]")

    output_path = sys.argv[1]
    tree_name = sys.argv[2]
    input_paths = sys.argv[3:]

    load_muse_dictionaries()

    first_input = ROOT.TFile.Open(input_paths[0], "READ")
    if not first_input or first_input.IsZombie():
        return fail(f"could not open first ROOT input: {input_paths[0]}")

    chain = ROOT.TChain(tree_name)
    for input_path in input_paths:
        input_file = ROOT.TFile.Open(input_path, "READ")
        if not input_file or input_file.IsZombie():
            return fail(f"could not open ROOT input: {input_path}")
        tree = input_file.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            return fail(f"ROOT input is missing expected tree {tree_name!r}: {input_path}")
        input_file.Close()
        chain.Add(input_path)

    output_file = ROOT.TFile.Open(output_path, "RECREATE")
    if not output_file or output_file.IsZombie():
        return fail(f"could not create ROOT output: {output_path}")

    copy_run_info(output_file, first_input)
    output_file.cd()
    merged_tree = chain.CloneTree(-1, "fast")
    if not merged_tree:
        return fail(f"failed to clone tree {tree_name!r}")
    merged_tree.SetName(tree_name)
    merged_tree.Write(tree_name, ROOT.TObject.kOverwrite)
    output_file.Write()
    output_file.Close()
    first_input.Close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
