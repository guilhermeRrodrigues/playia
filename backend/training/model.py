"""Policy network — CNN simples (~350k params).

3 convs strided 2 (128→64→32→16) + AdaptiveAvgPool 4x4 + 2 FC.
Output: logits do tamanho ``action_dim`` (sigmoid para binárias,
regressão direta para mouse_dx/dy).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class PolicyNet(nn.Module):
    def __init__(self, *, action_dim: int, dropout: float = 0.2) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 32, kernel_size=5, stride=2, padding=2)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=5, stride=2, padding=2)
        self.conv3 = nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1)
        self.pool = nn.AdaptiveAvgPool2d((4, 4))
        self.fc1 = nn.Linear(64 * 4 * 4, 256)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(256, action_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = self.pool(x)
        x = x.flatten(1)
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x
