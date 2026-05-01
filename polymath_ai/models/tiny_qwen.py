"""Tiny Qwen-shape transformer for CI / smoke tests.

This is a faithful structural mimic of the Qwen2.5-1.5B layer block (RMSNorm,
SwiGLU MLP, RoPE-style rotary embeddings on Q/K, GQA, residual stream) at
toy dimensions. It exists so the ELO Stage 1 training loop, freeze-plan
hashing, checkpoint resume, and adapter contracts can all be exercised
end-to-end on a Mac laptop in seconds without downloading ~3 GB of weights.

It is intentionally minimal:

* No dropout (training in deterministic mode for tests).
* No flash-attention / sdpa - plain matmul; correctness over speed.
* Tied or untied lm_head (default tied).
* Configurable layer count so we can match the PRD's first/last freeze plan
  on a 6-layer toy and still have 4 frozen middle layers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional


def _torch():
    import torch  # local import - tests can run without torch only for
    return torch  # documentation; ELO tests hard-require torch


@dataclass
class TinyQwenConfig:
    vocab_size: int = 257  # tiny BPE-like vocab (256 bytes + EOS)
    hidden_size: int = 32
    intermediate_size: int = 64  # 2x hidden for SwiGLU
    num_hidden_layers: int = 6
    num_attention_heads: int = 4
    num_key_value_heads: int = 2  # GQA: 4Q heads, 2KV heads (2:1)
    head_dim: int = 8
    max_position_embeddings: int = 128
    rope_theta: float = 10_000.0
    rms_norm_eps: float = 1e-6
    # Default: untied. Qwen2.5-1.5B and SmolLM3-3B both have separate
    # ``lm_head.weight`` and ``model.embed_tokens.weight``; mirroring that
    # here keeps the freeze-plan contract identical between tiny and real
    # models. ``tie_word_embeddings=True`` is reachable as an ablation.
    tie_word_embeddings: bool = False


def _build_module():
    """Lazy module construction so this file imports without torch."""
    torch = _torch()
    nn = torch.nn

    class RMSNorm(nn.Module):
        def __init__(self, hidden_size: int, eps: float = 1e-6):
            super().__init__()
            self.weight = nn.Parameter(torch.ones(hidden_size))
            self.eps = eps

        def forward(self, x):
            v = x.float()
            n = v.pow(2).mean(-1, keepdim=True)
            v = v * torch.rsqrt(n + self.eps)
            return (v * self.weight.float()).to(x.dtype)

    def rotate_half(x):
        x1, x2 = x.chunk(2, dim=-1)
        return torch.cat([-x2, x1], dim=-1)

    def rotary_emb(x, sin, cos):
        # HF/Qwen form: q' = q * cos + rotate_half(q) * sin
        # sin/cos are full head_dim (built by duplicating half-size freqs).
        return x * cos + rotate_half(x) * sin

    def build_rope_cache(seq_len: int, head_dim: int, theta: float, device):
        # Match Qwen's even-pair scheme: build freqs at head_dim/2, then
        # duplicate so the cache aligns with the full head_dim tensor.
        half = head_dim // 2
        inv_freq = 1.0 / (theta ** (torch.arange(0, half, device=device).float() / half))
        t = torch.arange(seq_len, device=device).float()
        freqs = torch.einsum("i,j->ij", t, inv_freq)  # (seq, half)
        emb = torch.cat([freqs, freqs], dim=-1)  # (seq, head_dim)
        return emb.sin(), emb.cos()

    class TinyQwenAttention(nn.Module):
        def __init__(self, cfg: TinyQwenConfig):
            super().__init__()
            self.cfg = cfg
            self.q_proj = nn.Linear(cfg.hidden_size, cfg.num_attention_heads * cfg.head_dim, bias=False)
            self.k_proj = nn.Linear(cfg.hidden_size, cfg.num_key_value_heads * cfg.head_dim, bias=False)
            self.v_proj = nn.Linear(cfg.hidden_size, cfg.num_key_value_heads * cfg.head_dim, bias=False)
            self.o_proj = nn.Linear(cfg.num_attention_heads * cfg.head_dim, cfg.hidden_size, bias=False)

        def forward(self, x, sin, cos):
            B, S, _ = x.shape
            q = self.q_proj(x).view(B, S, self.cfg.num_attention_heads, self.cfg.head_dim).transpose(1, 2)
            k = self.k_proj(x).view(B, S, self.cfg.num_key_value_heads, self.cfg.head_dim).transpose(1, 2)
            v = self.v_proj(x).view(B, S, self.cfg.num_key_value_heads, self.cfg.head_dim).transpose(1, 2)

            q = rotary_emb(q, sin[None, None], cos[None, None])
            k = rotary_emb(k, sin[None, None], cos[None, None])

            # GQA: repeat KV heads to match Q.
            repeats = self.cfg.num_attention_heads // self.cfg.num_key_value_heads
            k = k.repeat_interleave(repeats, dim=1)
            v = v.repeat_interleave(repeats, dim=1)

            scale = 1.0 / math.sqrt(self.cfg.head_dim)
            attn_logits = torch.einsum("bhsd,bhtd->bhst", q, k) * scale
            mask = torch.triu(torch.full((S, S), float("-inf"), device=x.device), diagonal=1)
            attn_logits = attn_logits + mask[None, None]
            attn = attn_logits.softmax(dim=-1)
            out = torch.einsum("bhst,bhtd->bhsd", attn, v)
            out = out.transpose(1, 2).contiguous().view(B, S, -1)
            return self.o_proj(out)

    class TinyQwenMLP(nn.Module):
        """SwiGLU."""

        def __init__(self, cfg: TinyQwenConfig):
            super().__init__()
            self.gate_proj = nn.Linear(cfg.hidden_size, cfg.intermediate_size, bias=False)
            self.up_proj = nn.Linear(cfg.hidden_size, cfg.intermediate_size, bias=False)
            self.down_proj = nn.Linear(cfg.intermediate_size, cfg.hidden_size, bias=False)

        def forward(self, x):
            return self.down_proj(nn.functional.silu(self.gate_proj(x)) * self.up_proj(x))

    class TinyQwenBlock(nn.Module):
        def __init__(self, cfg: TinyQwenConfig):
            super().__init__()
            self.input_layernorm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)
            self.self_attn = TinyQwenAttention(cfg)
            self.post_attention_layernorm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)
            self.mlp = TinyQwenMLP(cfg)

        def forward(self, x, sin, cos):
            x = x + self.self_attn(self.input_layernorm(x), sin, cos)
            x = x + self.mlp(self.post_attention_layernorm(x))
            return x

    class TinyQwenForCausalLM(nn.Module):
        """Top-level ``TinyQwenForCausalLM`` matching the structural slots
        ELO needs: ``model.embed_tokens``, ``model.layers[i]``, ``model.norm``,
        ``lm_head``.
        """

        def __init__(self, cfg: TinyQwenConfig):
            super().__init__()
            self.config = cfg
            # Inner ``model`` namespace mirrors HF Qwen layout so freeze
            # selectors `model.layers[0]`, `model.layers[-1]`, `lm_head`
            # work without alias glue.
            self.model = nn.Module()
            self.model.embed_tokens = nn.Embedding(cfg.vocab_size, cfg.hidden_size)
            self.model.layers = nn.ModuleList([TinyQwenBlock(cfg) for _ in range(cfg.num_hidden_layers)])
            self.model.norm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)
            self.lm_head = nn.Linear(cfg.hidden_size, cfg.vocab_size, bias=False)
            if cfg.tie_word_embeddings:
                self.lm_head.weight = self.model.embed_tokens.weight

        def forward(self, input_ids, labels=None):
            B, S = input_ids.shape
            sin, cos = build_rope_cache(S, self.config.head_dim, self.config.rope_theta, input_ids.device)
            x = self.model.embed_tokens(input_ids)
            for blk in self.model.layers:
                x = blk(x, sin, cos)
            x = self.model.norm(x)
            logits = self.lm_head(x)
            if labels is None:
                return logits
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = nn.functional.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_labels.view(-1),
            )
            return logits, loss

    return TinyQwenForCausalLM


def TinyQwenForCausalLM(cfg: Optional[TinyQwenConfig] = None):  # noqa: N802 - mirror class name
    """Factory: build a fresh tiny model. Lazy-imports torch."""
    cls = _build_module()
    return cls(cfg or TinyQwenConfig())


# ---------- Adapter wrapping the tiny model ----------


class TinyQwenShapeAdapter:
    """ModelAdapter implementation for the tiny smoke model.

    Acts as a stand-in for ``Qwen25_15BAdapter`` in CI / smoke tests. The
    contract is the same so swapping the model is a config flag.
    """

    model_id: str = "tiny.qwen.shape"
    model_family: str = "qwen-shape"
    license_id: str = "internal/research-only"

    def __init__(self, cfg: Optional[TinyQwenConfig] = None) -> None:
        self.cfg = cfg or TinyQwenConfig()
        self._model = None

    def load(self, revision: str = "tiny", dtype: str = "fp32", device: str = "cpu"):
        torch = _torch()
        cls = _build_module()
        m = cls(self.cfg)
        if dtype == "fp16":
            m = m.half()
        elif dtype == "bf16":
            m = m.to(torch.bfloat16)
        m = m.to(device)
        self._model = m
        return m

    def model(self):
        if self._model is None:
            self.load()
        return self._model

    # ELO-shaped helpers ---------------------------------------------------

    def freeze_policy(self, policy_name: str = "elo_first_last") -> "FreezePlan":
        from polymath_ai.models.adapters import FreezePlan
        if policy_name == "elo_first_last":
            n = self.cfg.num_hidden_layers
            return FreezePlan(
                trainable_layer_indices=(0, n - 1),
                freeze_embeddings=True,  # default per PRD; ablation can flip
                train_lm_head=True,
                policy_name=policy_name,
            )
        if policy_name == "all":
            n = self.cfg.num_hidden_layers
            return FreezePlan(
                trainable_layer_indices=tuple(range(n)),
                freeze_embeddings=False,
                train_lm_head=True,
                policy_name=policy_name,
            )
        raise ValueError(f"unknown policy {policy_name!r}")

    def trainable_parameters(self, freeze_plan: "FreezePlan") -> List[str]:
        from polymath_ai.models.adapters import apply_freeze_plan
        m = self.model()
        apply_freeze_plan(m, freeze_plan)
        return [n for n, p in m.named_parameters() if p.requires_grad]

    def frozen_parameter_names(self, freeze_plan: "FreezePlan") -> List[str]:
        from polymath_ai.models.adapters import apply_freeze_plan
        m = self.model()
        apply_freeze_plan(m, freeze_plan)
        return [n for n, p in m.named_parameters() if not p.requires_grad]
