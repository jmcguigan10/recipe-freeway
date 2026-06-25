from __future__ import annotations

import torch


def print_cuda_banner(device: torch.device) -> None:
    name = torch.cuda.get_device_name(device)
    print("=" * 80)
    print(f"USING CUDA: {device} - {name}")
    print("=" * 80)


def print_epoch(row: dict[str, float | int]) -> None:
    print(
        "epoch={epoch} train_loss={train_loss:.6f} val_loss={val_loss:.6f} "
        "val_macro_f1={val_macro_f1:.6f}".format(**row)
    )
