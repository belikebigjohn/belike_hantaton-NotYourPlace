"""Russian OCR inference adapter for Nomeroff Net's published ShuffleNet weights.

Inference network structure adapted from ria-com/nomeroff-net NPOcrNet,
GPL-3.0, https://github.com/ria-com/nomeroff-net/blob/master/nomeroff_net/nnmodels/ocr_model.py
See models/NOMEROFF_LICENSE.txt. Training and Lightning are deliberately excluded.
"""
from __future__ import annotations

import json
import hashlib
import pickle
import types
from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np
import torch
from fast_alpr.base import BaseOCR, OcrResult
from torch import nn
from torchvision.models import shufflenet_v2_x2_0


class LabelMetadata:
    """Inert deserialization holder; never invokes Nomeroff checkpoint code."""


def load_checkpoint(weights: Path):
    """Read the pinned Nomeroff checkpoint on modern and legacy Intel macOS Torch."""
    if hasattr(torch.serialization, "safe_globals"):
        with torch.serialization.safe_globals([(LabelMetadata, "nomeroff_net.tools.ocr_tools.StrLabelConverter"), shufflenet_v2_x2_0]):
            return torch.load(weights, map_location="cpu", weights_only=True)

    # Torch 2.2 is the last Intel macOS build and lacks safe_globals. Its
    # weights-only unpickler cannot allowlist the checkpoint's two metadata
    # globals. Verify the exact pinned artifact, then restrict pickle GLOBALs.
    expected = json.loads((Path(__file__).resolve().parents[1] / "models/checksums.reference.json").read_text(encoding="utf-8"))["nomeroff-ru.ckpt"]
    digest = hashlib.sha256()
    with weights.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise RuntimeError("Nomeroff checkpoint checksum mismatch")

    allowed = {
        ("collections", "OrderedDict"): OrderedDict,
        ("torch._utils", "_rebuild_tensor_v2"): torch._utils._rebuild_tensor_v2,
        ("torch", "FloatStorage"): torch.FloatStorage,
        ("torch", "LongStorage"): torch.LongStorage,
        ("nomeroff_net.tools.ocr_tools", "StrLabelConverter"): LabelMetadata,
        ("torchvision.models.shufflenetv2", "shufflenet_v2_x2_0"): shufflenet_v2_x2_0,
    }

    class RestrictedUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            try:
                return allowed[(module, name)]
            except KeyError as error:
                raise pickle.UnpicklingError(f"Unsupported checkpoint global: {module}.{name}") from error

    restricted = types.ModuleType("restricted_nomeroff_pickle")
    restricted.Unpickler = RestrictedUnpickler
    restricted.load = lambda handle, **kwargs: RestrictedUnpickler(handle, **kwargs).load()
    return torch.load(weights, map_location="cpu", weights_only=False, pickle_module=restricted)


class Recurrent(nn.Module):
    def __init__(self, input_size, hidden_size):
        super().__init__()
        self.rnn = nn.LSTM(input_size, hidden_size, bidirectional=True, batch_first=True)

    def forward(self, inputs, combine=False):
        outputs, _ = self.rnn(inputs)
        if combine:
            width = outputs.size(2) // 2
            outputs = outputs[:, :, :width] + outputs[:, :, width:]
        return outputs


class RussianOCRNet(nn.Module):
    def __init__(self, config):
        super().__init__()
        backbone = shufflenet_v2_x2_0(weights=None)
        self.conv_nn = nn.Sequential(*list(backbone.children())[:-3])
        self.conv_nn.eval()
        with torch.no_grad():
            feature = self.conv_nn(torch.zeros(1, 3, config["height"], config["width"]))
        channels, height = feature.shape[1:3]
        self.linear1 = nn.Linear(channels * height, config["linear_size"])
        self.recurrent_layer1 = Recurrent(config["linear_size"], config["hidden_size"])
        self.recurrent_layer2 = Recurrent(config["hidden_size"], config["hidden_size"])
        self.linear2 = nn.Linear(config["hidden_size"] * 2, len(config["letters"]) + 1)

    def forward(self, inputs):
        features = self.conv_nn(inputs).permute(0, 3, 1, 2)
        features = features.reshape(features.size(0), features.size(1), -1)
        sequence = self.linear1(features)
        sequence = self.recurrent_layer1(sequence, combine=True)
        sequence = self.recurrent_layer2(sequence)
        return self.linear2(sequence).permute(1, 0, 2)


class NomeroffRussianOCR(BaseOCR):
    def __init__(self, weights: Path, config_path: Path):
        self.config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        checkpoint = load_checkpoint(weights)
        self.model = RussianOCRNet(self.config)
        self.model.load_state_dict(checkpoint["state_dict"], strict=True)
        self.model.eval()

    def predict(self, cropped_plate: np.ndarray) -> OcrResult | None:
        if cropped_plate is None or cropped_plate.size == 0:
            return None
        # Nomeroff's training preprocessing uses RGB resize and per-image minmax.
        rgb = cv2.cvtColor(cropped_plate, cv2.COLOR_BGR2RGB)
        image = cv2.resize(rgb, (self.config["width"], self.config["height"]))
        image = cv2.normalize(image, None, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_32F)
        tensor = torch.from_numpy(np.moveaxis(image, 2, 0).copy()).unsqueeze(0)
        with torch.inference_mode():
            probabilities = self.model(tensor)[:, 0, :].softmax(-1)
            scores, indexes = probabilities.max(-1)
        text, confidence, previous = [], [], None
        for index, score in zip(indexes.tolist(), scores.tolist()):
            if index != previous and index != 0:
                text.append(self.config["letters"][index - 1])
                confidence.append(score)
            previous = index
        if not text:
            return None
        return OcrResult(text="".join(text), confidence=float(np.mean(confidence)))
