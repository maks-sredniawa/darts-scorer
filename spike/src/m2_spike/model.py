import timm
import torch
import torch.nn.functional as F
from torch import nn

from m2_spike.synth import NUM_CALIBRATION

CHANNELS = NUM_CALIBRATION + 1
STRIDE = 4


class PointNet(nn.Module):
    def __init__(self, backbone: str = "mobilenetv4_conv_small.e2400_r224_in1k", width: int = 96, pretrained: bool = True):
        super().__init__()
        self.backbone = timm.create_model(backbone, pretrained=pretrained, features_only=True, out_indices=(1, 2, 3, 4))
        dims = self.backbone.feature_info.channels()
        self.lateral = nn.ModuleList(nn.Conv2d(d, width, 1) for d in dims)
        self.smooth = nn.Sequential(
            nn.Conv2d(width, width, 3, padding=1), nn.BatchNorm2d(width), nn.ReLU(inplace=True),
            nn.Conv2d(width, width, 3, padding=1), nn.BatchNorm2d(width), nn.ReLU(inplace=True),
        )
        self.heatmap = nn.Conv2d(width, CHANNELS, 1)
        self.offset = nn.Conv2d(width, 2, 1)
        nn.init.constant_(self.heatmap.bias, -4.6)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(x)
        top = self.lateral[-1](features[-1])
        for lateral, feature in zip(reversed(self.lateral[:-1]), reversed(features[:-1])):
            top = lateral(feature) + F.interpolate(top, size=feature.shape[-2:], mode="nearest")
        top = self.smooth(top)
        return self.heatmap(top), self.offset(top)


def focal_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    pred = torch.sigmoid(logits).clamp(1e-4, 1 - 1e-4)
    positive = target.eq(1).float()
    pos = -torch.log(pred) * (1 - pred) ** 2 * positive
    neg = -torch.log(1 - pred) * pred**2 * (1 - target) ** 4 * (1 - positive)
    return (pos.sum() + neg.sum()) / positive.sum().clamp(min=1)
