"""
policyswarm.extraction_llm
===========================
Tier 1: Schema-driven LLM policy extraction.

Replaces the hardcoded keyword pipeline in extraction.py with structured
extraction via an open-source instruction-tuned model. The schema YAML defines
policy dimensions, ideology sensitivities, and violator semantics — switching
domain requires only swapping the YAML file.

Backends
--------
OllamaBackend
    Calls a locally running Ollama server (https://ollama.com).
    Uses Ollama's native JSON mode for reliable structured output.
    Recommended models:
        ollama pull llama3.2:3b          # fast, good JSON compliance
        ollama pull mistral:7b-instruct  # higher quality, ~7 GB
        ollama pull phi3:mini            # smallest footprint, ~2 GB

HuggingFaceBackend
    Runs inference via the transformers library. No server required.
    Recommended models:
        microsoft/Phi-3-mini-4k-instruct   # 3.8 B, excellent JSON compliance
        google/gemma-2-2b-it               # 2 B, fast on CPU
    Optional: set load_in_4bit=True on GPUs with < 8 GB VRAM.

Usage
-----
    from policyswarm.extraction_llm import LLMPolicyExtractor

    # Ollama (recommended for development — start with: ollama serve)
    extractor = LLMPolicyExtractor.from_yaml(
        "schemas/ai_policy.yaml",
        backend="ollama",
        model="llama3.2:3b",
    )

    # Text input
    policy = extractor.extract_text("The government introduces...")

    # PDF input
    policy = extractor.extract("eu_ai_act.pdf")

    # HuggingFace (no server required)
    extractor = LLMPolicyExtractor.from_yaml(
        "schemas/healthcare_policy.yaml",
        backend="huggingface",
        model="microsoft/Phi-3-mini-4k-instruct",
    )

    # Domain-agnostic: SimConfig.opinion_dim must match policy.dim
    from policyswarm.config import SimConfig
    sim_config = SimConfig(opinion_dim=policy.dim)

Dependencies
------------
    pip install pyyaml requests          # always required
    pip install pdfplumber               # PDF ingestion (recommended)
    pip install pypdf                    # PDF ingestion (fallback)
    pip install transformers torch       # HuggingFace backend only
    pip install bitsandbytes             # 4-bit quantization (optional)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import yaml

from .config import Policy, unit_to_centred

log = logging.getLogger("policyswarm.extraction_llm")


# ---------------------------------------------------------------------------
# Schema dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DimensionSpec:
    """Single policy dimension loaded from a schema YAML."""
    name                 : str
    description          : str
    ideology_sensitivity : float = 0.0


@dataclass
class PolicySchema:
    """
    Fully loaded and validated policy schema.

    Attributes
    ----------
    domain : str
    dimensions : list of DimensionSpec
    narrative_frames : list of str
    lag_prompt : str
        Instruction for estimating enforcement_lag from document text.
    violator_dimension : str
        Name of the dimension used for violator detection in Simulation.
    violator_threshold : float
    """
    domain              : str
    dimensions          : List[DimensionSpec]
    narrative_frames    : List[str]
    lag_prompt          : str
    violator_dimension  : str
    violator_threshold  : float

    @property
    def n_dims(self) -> int:
        return len(self.dimensions)

    @property
    def dimension_names(self) -> List[str]:
        return [d.name for d in self.dimensions]

    @property
    def dimension_salience(self) -> np.ndarray:
        return np.array([d.ideology_sensitivity for d in self.dimensions])

    @property
    def violator_dim_index(self) -> int:
        names = self.dimension_names
        if self.violator_dimension not in names:
            raise ValueError(
                f"violator_dimension '{self.violator_dimension}' "
                f"not found in schema dimensions: {names}"
            )
        return names.index(self.violator_dimension)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> PolicySchema:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

        dimensions = [
            DimensionSpec(
                name=d["name"],
                description=d["description"].strip(),
                ideology_sensitivity=float(d.get("ideology_sensitivity", 0.0)),
            )
            for d in raw["dimensions"]
        ]

        first_dim = dimensions[0].name
        return cls(
            domain=raw.get("domain", "Unknown"),
            dimensions=dimensions,
            narrative_frames=raw.get("narrative_frames", []),
            lag_prompt=raw.get(
                "lag_prompt",
                "Estimate enforcement lag as an integer between 0 and 40.",
            ),
            violator_dimension=raw.get("violator_dimension", first_dim),
            violator_threshold=float(raw.get("violator_threshold", 0.8)),
        )


# ---------------------------------------------------------------------------
# JSON repair utilities
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text)
    return text.replace("```", "").strip()


def _extract_first_object(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def _repair_and_parse(raw: str) -> dict:
    """
    Attempt to parse raw LLM output as JSON using successive repair passes.
    Raises json.JSONDecodeError if all passes fail.
    """
    text = raw.strip()
    for fn in [
        lambda t: t,
        _strip_fences,
        _extract_first_object,
        lambda t: _extract_first_object(_strip_fences(t)),
    ]:
        try:
            return json.loads(fn(text))
        except (json.JSONDecodeError, TypeError):
            continue

    raise json.JSONDecodeError(
        f"Cannot parse LLM output as JSON after all repair attempts.\n"
        f"Raw output (first 500 chars):\n{raw[:500]}",
        raw, 0,
    )


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

class OllamaBackend:
    """
    Calls a locally running Ollama server.

    Install:  https://ollama.com/download
    Start:    ollama serve
    Pull:     ollama pull llama3.2:3b

    Parameters
    ----------
    model : str
        Ollama model tag. Default "llama3.2:3b".
    base_url : str
        Server URL. Default "http://localhost:11434".
    timeout : int
        Request timeout in seconds. Default 120.
    """

    def __init__(
        self,
        model    : str = "llama3.2:3b",
        base_url : str = "http://localhost:11434",
        timeout  : int = 120,
    ):
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._verify_server()

    def _verify_server(self) -> None:
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            available = [m["name"] for m in r.json().get("models", [])]
            base_name = self.model.split(":")[0]
            if not any(base_name in m for m in available):
                log.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available: {available}\n"
                    f"Pull it with: ollama pull {self.model}"
                )
        except Exception as e:
            raise RuntimeError(
                f"Ollama server not reachable at {self.base_url}.\n"
                f"Start it with: ollama serve\n"
                f"Error: {e}"
            )

    def generate(self, prompt: str, system: str) -> str:
        import requests
        payload = {
            "model"   : self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "format"  : "json",    # Ollama native JSON mode
            "stream"  : False,
            "options" : {"temperature": 0.1, "num_predict": 1024},
        }
        r = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


# ---------------------------------------------------------------------------
# HuggingFace backend
# ---------------------------------------------------------------------------

class HuggingFaceBackend:
    """
    Runs inference locally via HuggingFace transformers. No server required.

    Parameters
    ----------
    model_name : str
        HuggingFace model ID.
        Default "microsoft/Phi-3-mini-4k-instruct".
        Also works well: "google/gemma-2-2b-it", "mistralai/Mistral-7B-Instruct-v0.3"
    device : str, optional
        "cuda", "mps", or "cpu". Auto-detected if None.
    max_new_tokens : int
        Token generation budget. Default 512.
    load_in_4bit : bool
        Use bitsandbytes 4-bit quantization. Default False.
        Set True on GPUs with < 8 GB VRAM.
    """

    def __init__(
        self,
        model_name     : str            = "microsoft/Phi-3-mini-4k-instruct",
        device         : Optional[str]  = None,
        max_new_tokens : int            = 512,
        load_in_4bit   : bool           = False,
    ):
        self.model_name     = model_name
        self.max_new_tokens = max_new_tokens
        self._pipeline      = self._load(model_name, device, load_in_4bit)

    def _load(self, model_name, device, load_in_4bit):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            if device is None:
                device = (
                    "cuda" if torch.cuda.is_available()
                    else "mps" if torch.backends.mps.is_available()
                    else "cpu"
                )
            log.info(f"Loading {model_name} on {device} ...")

            kwargs: dict = {}
            if load_in_4bit:
                from transformers import BitsAndBytesConfig
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                kwargs["device_map"] = "auto"
            else:
                kwargs["device_map"] = device

            dtype = torch.float16 if device != "cpu" else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                torch_dtype=dtype,
                **kwargs,
            )
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            return pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                do_sample=False,
                temperature=None,
                max_new_tokens=self.max_new_tokens,
            )
        except ImportError as e:
            raise ImportError(
                "HuggingFace backend requires:\n"
                "  pip install transformers torch\n"
                f"Error: {e}"
            )

    def generate(self, prompt: str, system: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        try:
            out = self._pipeline(messages, return_full_text=False)
            return out[0]["generated_text"]
        except Exception:
            # Fallback to Llama-style manual formatting for older models
            formatted = (
                f"<s>[INST] <<SYS>>\n{system}\n<</SYS>>\n\n{prompt} [/INST]"
            )
            out = self._pipeline(formatted, return_full_text=False)
            return out[0]["generated_text"]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(schema: PolicySchema) -> str:
    dim_defs = "\n".join(
        f'    "{d.name}": {d.description}'
        for d in schema.dimensions
    )
    dim_keys_dims = "\n    ".join(
        f'"{d.name}": <float 0.0–1.0>,' for d in schema.dimensions
    )
    dim_keys_conf = "\n    ".join(
        f'"{d.name}": <float 0.0–1.0>,' for d in schema.dimensions
    )
    frame_keys = "\n    ".join(
        f'"{f}": <float 0.0–1.0>,' for f in schema.narrative_frames
    )

    return f"""You are a policy analysis assistant specialised in: {schema.domain}.

Extract structured information from the policy document provided.
Respond with a single valid JSON object ONLY. No explanation, no preamble, no markdown.

Required JSON structure:
{{
    "dimensions": {{
        {dim_keys_dims}
    }},
    "confidence": {{
        {dim_keys_conf}
    }},
    "narrative_frames": {{
        {frame_keys}
    }},
    "enforcement_lag": <integer 0–40>,
    "reasoning": "<one sentence: most important dimension and why>"
}}

Dimension definitions (domain: {schema.domain}):
{dim_defs}

Scoring rules:
  0.0 = minimum / most permissive / least restrictive extreme for this dimension
  1.0 = maximum / most restrictive / most demanding extreme
  0.5 = neutral, ambiguous, or not explicitly addressed

Confidence rules:
  1.0 = document directly and explicitly addresses this dimension
  0.5 = indirect evidence or inference required
  0.1 = dimension not mentioned; default assumed

{schema.lag_prompt}"""


def _build_user_prompt(text: str, max_chars: int = 4000) -> str:
    body = text[:max_chars]
    if len(text) > max_chars:
        body += "\n[... document truncated ...]"
    return f"Extract policy dimensions from the following policy document:\n\n{body}"


# ---------------------------------------------------------------------------
# LLMPolicyExtractor
# ---------------------------------------------------------------------------

class LLMPolicyExtractor:
    """
    Schema-driven LLM policy extractor. Produces Policy objects compatible
    with the full Simulation pipeline.

    Parameters
    ----------
    schema : PolicySchema
    backend : OllamaBackend or HuggingFaceBackend
    max_retries : int
        Number of LLM call attempts before falling back. Default 3.
    fallback_to_keywords : bool
        Fall back to keyword extraction on total LLM failure. Default True.
        Fallback only produces sensible results for the AI policy domain.
    """

    def __init__(
        self,
        schema                : PolicySchema,
        backend               : Union[OllamaBackend, HuggingFaceBackend],
        max_retries           : int  = 3,
        fallback_to_keywords  : bool = True,
    ):
        self.schema               = schema
        self.backend              = backend
        self.max_retries          = max_retries
        self.fallback_to_keywords = fallback_to_keywords
        self._system_prompt       = _build_system_prompt(schema)

    @classmethod
    def from_yaml(
        cls,
        schema_path : Union[str, Path],
        backend     : str           = "ollama",
        model       : Optional[str] = None,
        **backend_kwargs,
    ) -> LLMPolicyExtractor:
        """
        Convenience constructor.

        Parameters
        ----------
        schema_path : str or Path
            Path to a schema YAML file (e.g. "schemas/ai_policy.yaml").
        backend : str
            "ollama" (default) or "huggingface".
        model : str, optional
            Model name/tag. Defaults:
                ollama       → "llama3.2:3b"
                huggingface  → "microsoft/Phi-3-mini-4k-instruct"
        **backend_kwargs
            Forwarded to the backend constructor (e.g. base_url, load_in_4bit).
        """
        schema = PolicySchema.from_yaml(schema_path)

        if backend == "ollama":
            _backend = OllamaBackend(
                model=model or "llama3.2:3b",
                **backend_kwargs,
            )
        elif backend == "huggingface":
            _backend = HuggingFaceBackend(
                model_name=model or "microsoft/Phi-3-mini-4k-instruct",
                **backend_kwargs,
            )
        else:
            raise ValueError(
                f"Unknown backend: {backend!r}. Choose 'ollama' or 'huggingface'."
            )

        return cls(schema=schema, backend=_backend)

    # ------------------------------------------------------------------
    # PDF ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def _read_pdf(path: Union[str, Path]) -> str:
        """Extract full text from a PDF. Tries pdfplumber, then pypdf."""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n\n".join(pages)
        except ImportError:
            pass

        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except ImportError:
            raise ImportError(
                "PDF extraction requires one of:\n"
                "  pip install pdfplumber   (recommended)\n"
                "  pip install pypdf"
            )

    def extract(self, pdf_path: Union[str, Path]) -> Policy:
        """Extract a Policy from a PDF file."""
        text = self._read_pdf(pdf_path)
        return self.extract_text(text)

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def extract_text(self, text: str) -> Policy:
        """
        Extract a Policy from raw text.

        Runs up to max_retries LLM calls with exponential backoff.
        Falls back to keyword extraction if all attempts fail.
        """
        user_prompt = _build_user_prompt(text)
        last_error  = None

        for attempt in range(self.max_retries):
            try:
                raw    = self.backend.generate(user_prompt, self._system_prompt)
                parsed = _repair_and_parse(raw)
                policy = self._parsed_to_policy(parsed)
                log.info(
                    f"LLM extraction succeeded (attempt {attempt + 1}). "
                    f"Domain: {self.schema.domain}, dims: {self.schema.n_dims}"
                )
                return policy

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                last_error = e
                wait = 2 ** attempt
                log.warning(
                    f"LLM extraction attempt {attempt + 1}/{self.max_retries} "
                    f"failed: {e}. Retrying in {wait}s ..."
                )
                time.sleep(wait)

        log.error(f"All LLM attempts failed. Last error: {last_error}")

        if self.fallback_to_keywords:
            log.warning("Falling back to keyword extraction.")
            return self._keyword_fallback(text)

        raise RuntimeError(
            f"LLM policy extraction failed after {self.max_retries} attempts.\n"
            f"Last error: {last_error}"
        )

    def _parsed_to_policy(self, parsed: dict) -> Policy:
        """Convert parsed LLM JSON to a Policy object."""
        dims_raw = parsed.get("dimensions", {})
        conf_raw = parsed.get("confidence", {})
        narr_raw = parsed.get("narrative_frames", {})

        vector     = np.zeros(self.schema.n_dims, dtype=float)
        confidence = np.full(self.schema.n_dims, 0.5, dtype=float)

        for i, dim in enumerate(self.schema.dimensions):
            if dim.name not in dims_raw:
                log.warning(
                    f"LLM did not return dimension '{dim.name}'. Using 0.5."
                )
                vector[i] = 0.5
            else:
                vector[i] = float(np.clip(dims_raw[dim.name], 0.0, 1.0))

            if dim.name in conf_raw:
                confidence[i] = float(np.clip(conf_raw[dim.name], 0.0, 1.0))

        narrative = {
            frame: float(np.clip(narr_raw.get(frame, 0.5), 0.0, 1.0))
            for frame in self.schema.narrative_frames
        }

        lag = int(np.clip(parsed.get("enforcement_lag", 10), 0, 40))

        # LLM output and schema thresholds are on the unit interval; the
        # simulation works in the centred [-1, 1] space.
        return Policy(
            vector             = unit_to_centred(vector),
            dimension_names    = self.schema.dimension_names,
            confidence         = confidence,
            dimension_salience = self.schema.dimension_salience,
            violator_dim_index = self.schema.violator_dim_index,
            violator_threshold = unit_to_centred(self.schema.violator_threshold),
            lag                = lag,
            narrative          = narrative,
        )

    def _keyword_fallback(self, text: str) -> Policy:
        """
        Keyword-based fallback for when the LLM fails.

        Produces meaningful output only for the 4-dim AI policy domain.
        For other domains, returns a uniform 0.5 vector with low confidence.
        """
        from .extraction import policy_from_text as _kw

        ai_indicator_keywords = {"deployment", "enforcement", "transparency", "audit"}
        hits = sum(1 for k in ai_indicator_keywords if k in text.lower())

        if hits >= 2 and self.schema.n_dims == 4:
            kw_policy = _kw(text)
            return Policy(
                vector             = kw_policy.as_vector(),   # already centred
                dimension_names    = self.schema.dimension_names,
                confidence         = np.full(4, 0.3),  # low: keyword match only
                dimension_salience = self.schema.dimension_salience,
                violator_dim_index = self.schema.violator_dim_index,
                violator_threshold = unit_to_centred(self.schema.violator_threshold),
                lag                = kw_policy.lag,
                narrative          = kw_policy.narrative,
            )

        log.warning(
            f"Keyword fallback not applicable for domain '{self.schema.domain}'. "
            "Returning uniform prior."
        )
        return Policy(
            vector             = np.zeros(self.schema.n_dims),  # neutral
            dimension_names    = self.schema.dimension_names,
            confidence         = np.full(self.schema.n_dims, 0.1),
            dimension_salience = self.schema.dimension_salience,
            violator_dim_index = self.schema.violator_dim_index,
            violator_threshold = unit_to_centred(self.schema.violator_threshold),
            lag                = 10,
            narrative          = {f: 0.5 for f in self.schema.narrative_frames},
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe(self, text: str) -> str:
        """Human-readable extraction summary. Analogous to describe_extraction()."""
        policy = self.extract_text(text)
        lines  = [
            f"=== LLM Extraction Summary ===",
            f"Domain   : {self.schema.domain}",
            f"Backend  : {type(self.backend).__name__}",
            f"Dims     : {self.schema.n_dims}",
            "",
            "Extracted Policy Vector:",
        ]
        for name, val, conf, sal in zip(
            policy.dimension_names,
            policy.vector,
            policy.confidence,
            policy.dimension_salience,
        ):
            lines.append(
                f"  {name:<22} = {val:.3f}  "
                f"(conf={conf:.2f}, salience={sal:+.3f})"
            )
        lines.append(f"\n  enforcement_lag  = {policy.lag}")
        lines.append(f"\nNarrative frames : {policy.narrative}")
        lines.append(f"\nViolator dim     : {policy.dimension_names[policy.violator_dim_index]}"
                     f" > {policy.violator_threshold}")
        return "\n".join(lines)
