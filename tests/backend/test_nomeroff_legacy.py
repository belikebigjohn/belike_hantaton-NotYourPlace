"""Exercise the restricted checkpoint path used by Intel macOS PyTorch 2.2."""
from pathlib import Path

import pytest
import torch

from backend.nomeroff_ru import load_checkpoint


def test_pinned_checkpoint_loads_without_safe_globals(monkeypatch):
    weights = Path(__file__).resolve().parents[2] / "models/nomeroff-ru.ckpt"
    if not weights.is_file():
        pytest.skip("Run models/setup_models.py before the model smoke test")
    monkeypatch.delattr(torch.serialization, "safe_globals", raising=False)
    checkpoint = load_checkpoint(weights)
    assert isinstance(checkpoint["state_dict"], dict)
    assert checkpoint["state_dict"]
