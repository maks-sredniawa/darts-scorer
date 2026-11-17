from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import mobilenet_v3_large

from .board import CALIBRATION_POINTS

STRIDE = 4
CALIBRATION_CHANNELS = len(CALIBRATION_POINTS)
ENTRY_CHANNEL = CALIBRATION_CHANNELS
HEATMAPS = CALIBRATION_CHANNELS + 1
OUTPUTS = HEATMAPS + 2
_TAPS = (3, 6, 12, 16)
_WIDTH = 96


class KeypointNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.backbone = mobilenet_v3_large(weights=None).features
        channels = [self.backbone[i].out_channels for i in _TAPS]
        self.lateral = nn.ModuleList(nn.Conv2d(c, _WIDTH, 1) for c in channels)
        self.smooth = nn.Sequential(
            nn.Conv2d(_WIDTH, _WIDTH, 3, padding=1),
            nn.BatchNorm2d(_WIDTH),
            nn.ReLU(inplace=True),
        )
        self.out = nn.Conv2d(_WIDTH, OUTPUTS, 1)
        nn.init.constant_(self.out.bias[:HEATMAPS], -4.6)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        taps = []
        x = image
        for index, layer in enumerate(self.backbone):
            x = layer(x)
            if index in _TAPS:
                taps.append(x)
        merged = self.lateral[-1](taps[-1])
        for lateral, tap in zip(reversed(self.lateral[:-1]), reversed(taps[:-1]), strict=True):
            merged = F.interpolate(merged, size=tap.shape[-2:], mode="nearest") + lateral(tap)
        return self.out(self.smooth(merged))
