"""Helpers de exportação ONNX.

Modelo treinado vai sempre pra CPU antes de exportar — alguns ops do
MPS não têm suporte no exporter ONNX, e a release final roda inferência
em CPU via onnxruntime de qualquer maneira.
"""

from __future__ import annotations

from pathlib import Path

import torch

from .model import PolicyNet


def export_onnx(
    model: PolicyNet,
    out_path: Path,
    *,
    img_size: int = 128,
    opset: int = 17,
) -> None:
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size)
    # ``dynamo=False`` força o exporter legado (TorchScript). Mais estável
    # e dispensa o pacote ``onnxscript`` (que infla o instalador em ~50MB
    # sem ganho prático pra um modelo simples como este).
    torch.onnx.export(
        model.cpu(),
        dummy,
        str(out_path),
        input_names=["frame"],
        output_names=["action_logits"],
        opset_version=opset,
        dynamic_axes={
            "frame": {0: "batch"},
            "action_logits": {0: "batch"},
        },
        dynamo=False,
    )
