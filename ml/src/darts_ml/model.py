from __future__ import annotations

import math
from typing import NamedTuple

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import mobilenet_v3_large

from .board import CALIBRATION_POINTS

BOARD_STRIDE = 4
ENTRY_STRIDE = 2
ENTRY_STRIDES = (2, 4)
CALIBRATION_CHANNELS = len(CALIBRATION_POINTS)
ENTRY_POINT = CALIBRATION_CHANNELS
BOARD_OFFSETS = slice(CALIBRATION_CHANNELS, CALIBRATION_CHANNELS + 2)
ENTRY_HEAT = 0
ENTRY_OFFSETS = slice(1, 3)
PRIOR = 0.01
PRIOR_LOGIT = math.log(PRIOR / (1 - PRIOR))
_TAPS = (3, 6, 12, 16)
_ENTRY_TAP = 1
_WIDTH = 96
_ENTRY_WIDTH = 32
_STRIDE4_OUTPUTS = CALIBRATION_CHANNELS + 5


class Heads(NamedTuple):
    """board: the Calibration heatmaps then their two offsets, at BOARD_STRIDE; entry: the Entry heatmap
    then its two offsets, at the model's entry stride."""
    board: torch.Tensor
    entry: torch.Tensor


def entry_stride_of(heads: Heads) -> int:
    return BOARD_STRIDE * heads.board.shape[-1] // heads.entry.shape[-1]


class KeypointNet(nn.Module):
    def __init__(self, entry_stride: int = ENTRY_STRIDE) -> None:
        super().__init__()
        if entry_stride not in ENTRY_STRIDES:
            raise ValueError(f"entry stride {entry_stride} is not one of {ENTRY_STRIDES}")
        self.entry_stride = entry_stride
        self.backbone = mobilenet_v3_large(weights=None).features
        channels = [self.backbone[i].out_channels for i in _TAPS]
        self.lateral = nn.ModuleList(nn.Conv2d(c, _WIDTH, 1) for c in channels)
        self.smooth = nn.Sequential(
            nn.Conv2d(_WIDTH, _WIDTH, 3, padding=1),
            nn.BatchNorm2d(_WIDTH),
            nn.ReLU(inplace=True),
        )
        if entry_stride == BOARD_STRIDE:
            # The layout C and D were trained with: one 1×1 conv for both kinds, so their weights load as saved.
            self.out = nn.Conv2d(_WIDTH, _STRIDE4_OUTPUTS, 1)
            nn.init.constant_(self.out.bias[:CALIBRATION_CHANNELS + 1], PRIOR_LOGIT)
            return
        self.out = nn.Conv2d(_WIDTH, CALIBRATION_CHANNELS + 2, 1)
        nn.init.constant_(self.out.bias[:CALIBRATION_CHANNELS], PRIOR_LOGIT)
        self.entry_reduce = nn.Conv2d(_WIDTH, _ENTRY_WIDTH, 1)
        self.entry_lateral = nn.Conv2d(self.backbone[_ENTRY_TAP].out_channels, _ENTRY_WIDTH, 1)
        self.entry_smooth = nn.Sequential(
            nn.Conv2d(_ENTRY_WIDTH, _ENTRY_WIDTH, 3, padding=1),
            nn.BatchNorm2d(_ENTRY_WIDTH),
            nn.ReLU(inplace=True),
        )
        self.entry_out = nn.Conv2d(_ENTRY_WIDTH, 3, 1)
        nn.init.constant_(self.entry_out.bias[ENTRY_HEAT], PRIOR_LOGIT)

    def forward(self, image: torch.Tensor) -> Heads:
        taps = []
        fine = None
        x = image
        for index, layer in enumerate(self.backbone):
            x = layer(x)
            if index == _ENTRY_TAP:
                fine = x
            if index in _TAPS:
                taps.append(x)
        merged = self.lateral[-1](taps[-1])
        for lateral, tap in zip(reversed(self.lateral[:-1]), reversed(taps[:-1]), strict=True):
            merged = F.interpolate(merged, size=tap.shape[-2:], mode="nearest") + lateral(tap)
        features = self.smooth(merged)
        out = self.out(features)
        if self.entry_stride == BOARD_STRIDE:
            c = CALIBRATION_CHANNELS
            return Heads(torch.cat([out[:, :c], out[:, c + 1:c + 3]], 1), torch.cat([out[:, c:c + 1], out[:, c + 3:]], 1))
        up = F.interpolate(self.entry_reduce(features), size=fine.shape[-2:], mode="bilinear", align_corners=False)
        return Heads(out, self.entry_out(self.entry_smooth(up + self.entry_lateral(fine))))


def stride_of_weights(state: dict[str, torch.Tensor]) -> int:
    return BOARD_STRIDE if state["out.weight"].shape[0] == _STRIDE4_OUTPUTS else ENTRY_STRIDE


def from_stride4(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """A stride-4 run's weights with its shared output conv cut down to the Calibration rows, which is what
    a stride-2 model's `out` holds; its Entry rows have no place in the stride-2 Entry head."""
    c = CALIBRATION_CHANNELS
    rows = [*range(c), c + 1, c + 2]
    return {**state, "out.weight": state["out.weight"][rows], "out.bias": state["out.bias"][rows]}


def load_matching(model: KeypointNet, state: dict[str, torch.Tensor]) -> list[str]:
    if model.entry_stride != BOARD_STRIDE and stride_of_weights(state) == BOARD_STRIDE:
        state = from_stride4(state)
    own = model.state_dict()
    taken = {k: v for k, v in state.items() if k in own and own[k].shape == v.shape}
    model.load_state_dict(taken, strict=False)
    return sorted(set(own) - set(taken))
