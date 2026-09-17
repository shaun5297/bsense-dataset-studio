from __future__ import annotations

import torch
from torch import nn


class EEGNet(nn.Module):
    """Compact 250 Hz EEGNet variant; input N x 2 x 1000, output logits.

    Based on Lawhern et al. (2018), DOI 10.1088/1741-2552/aace8c.
    Kernels are fixed before evaluation, not tuned on the held-out test set.
    """

    def __init__(self, channel_scale: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer("channel_scale", channel_scale.reshape(1, 2, 1))
        frequencies = torch.fft.rfftfreq(1000, 1 / 250)
        self.register_buffer(
            "band_mask", ((frequencies >= 1) & (frequencies <= 40)).float()
        )
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 8, (1, 125), padding=(0, 62), bias=False),
            nn.BatchNorm2d(8),
            nn.Conv2d(8, 16, (2, 1), groups=8, bias=False),
            nn.BatchNorm2d(16),
            nn.ELU(),
            nn.AvgPool2d((1, 4)),
            nn.Dropout(0.5),
            nn.Conv2d(16, 16, (1, 31), padding=(0, 15), groups=16, bias=False),
            nn.Conv2d(16, 16, (1, 1), bias=False),
            nn.BatchNorm2d(16),
            nn.ELU(),
            nn.AvgPool2d((1, 8)),
            nn.Dropout(0.5),
            nn.Flatten(),
            nn.Linear(16 * 31, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Filter and train-derived scaling travel with the exported model.
        x = x - x.mean(dim=-1, keepdim=True)
        spectrum = torch.fft.rfft(x, dim=-1) * self.band_mask
        x = torch.fft.irfft(spectrum, n=1000, dim=-1)
        return self.encoder((x / self.channel_scale).unsqueeze(1))


class InferenceModel(nn.Module):
    def __init__(self, model: EEGNet, temperature: float) -> None:
        super().__init__()
        self.model = model
        self.register_buffer("temperature", torch.tensor(temperature))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.model(x) / self.temperature, dim=-1)
