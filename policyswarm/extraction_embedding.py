"""
policyswarm.extraction_embedding
=================================
Tier 2: Corpus-driven embedding-based policy extraction.

Instead of defining policy dimensions by hand (Tier 1 schema YAML), this
module discovers latent policy axes from a corpus of policy documents using
PCA on mean-pooled sentence embeddings. The N principal components become
the opinion dimensions, with interpretation provided by PCA loadings.

Pipeline
--------
1. Fit phase (one-time, offline):
   - Ingest K policy PDFs from a corpus directory
   - Chunk each document into 256-token overlapping windows
   - Embed each chunk via SentenceTransformer (all-MiniLM-L6-v2, 384-dim)
   - Mean-pool chunk embeddings to get one K×384 matrix
   - Fit PCA → n_dims principal components
   - Fit MinMaxScaler to map projections to [0, 1]^n_dims
   - Compute dimension_salience via cosine similarity between each PC
     loading and a "pro-regulation" probe embedding
   - Serialize encoder to disk (pickle)

2. Encode phase (per-document, online):
   - Read PDF → extract text
   - Chunk → embed → mean-pool → project via PCA → scale to [0, 1]
   - Confidence = variance_explained_ratio per axis (normalized)
   - Return Policy object

CLI
---
    # Fit a corpus encoder (one-time)
    python -m policyswarm.tools.fit_encoder \
        --corpus-dir data/policy_corpus/ \
        --n-dims 6 \
        --output models/corpus_encoder.pkl

    # Use in experiments (see run_all.py --policy-source embedding)
    from policyswarm.extraction_embedding import EmbeddingPolicyExtractor
    extractor = EmbeddingPolicyExtractor.load("models/corpus_encoder.pkl")
    policy = extractor.extract("data/new_regulation.pdf")

Dependencies
------------
    pip install sentence-transformers scikit-learn pdfplumber

Critical limitation (document in paper)
----------------------------------------
PCA axes are corpus-relative. A policy from a domain not represented in the
corpus may project into the same space, but the axes no longer correspond to
the same semantic content. The dimension_labels property (top loading words
per axis) MUST be logged alongside all results for interpretability. This is
a methodological weakness relative to Tier 1 (explicit semantics), but Tier 2
provides higher representational fidelity for large corpora.
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from .config import Policy, unit_to_centred

log = logging.getLogger("policyswarm.extraction_embedding")

# ---------------------------------------------------------------------------
# Optional imports with clear error messages
# ---------------------------------------------------------------------------

def _require_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except ImportError:
        raise ImportError(
            "Tier 2 extraction requires:\n"
            "  pip install sentence-transformers scikit-learn\n"
            "Optional PDF support:\n"
            "  pip install pdfplumber"
        )

def _require_sklearn():
    try:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import MinMaxScaler
        return PCA, MinMaxScaler
    except ImportError:
        raise ImportError(
            "Tier 2 extraction requires:\n"
            "  pip install scikit-learn"
        )


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_words: int = 256, stride: int = 64) -> List[str]:
    """
    Sliding window chunking at sentence boundaries.

    Parameters
    ----------
    text : str
    max_words : int
        Approximate maximum words per chunk. Default 256.
    stride : int
        Overlap between consecutive chunks in words. Default 64.

    Returns
    -------
    list of str
        Non-empty chunks. Returns [""] if text is empty to avoid
        empty embedding inputs.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current_words, current = [], 0, []

    for sent in sentences:
        word_count = len(sent.split())
        if current_words + word_count > max_words and current:
            chunks.append(" ".join(current))
            # Stride: keep the last `stride` words
            overflow = " ".join(current).split()
            current  = overflow[-stride:] if len(overflow) > stride else []
            current_words = len(current)
        current.append(sent)
        current_words += word_count

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()] or [""]


def _read_pdf(path: Union[str, Path]) -> str:
    """Extract text from a PDF file."""
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
            "PDF ingestion requires one of:\n"
            "  pip install pdfplumber   (recommended)\n"
            "  pip install pypdf"
        )


# ---------------------------------------------------------------------------
# CorpusEncoder
# ---------------------------------------------------------------------------

class CorpusEncoder:
    """
    Fits and applies PCA-based policy encoding on a document corpus.

    The encoder is fit once on a corpus of K policy documents, then used to
    encode any new document into an n_dims-dimensional vector in [0, 1]^n_dims.

    Parameters
    ----------
    n_dims : int
        Number of PCA components (= opinion dimensions). Default 6.
        Choose via scree plot or target cumulative explained variance ≥ 0.85.
    model_name : str
        SentenceTransformer model. Default "all-MiniLM-L6-v2" (384-dim, fast).
        Higher quality: "all-mpnet-base-v2" (768-dim, slower).
    chunk_max_words : int
        Max words per chunk. Default 256.
    probe_text : str
        Text used to compute ideology salience per axis. The cosine similarity
        between each PC loading and the probe embedding gives dimension_salience.
        Default: a "strict government regulation" probe.

    Attributes (set after fit())
    ----------------------------
    n_dims : int
    dimension_labels : list of str
        Top-3 corpus words with highest absolute loading per axis.
    dimension_salience : np.ndarray, shape (n_dims,)
        Per-dimension ideology sensitivity, derived from probe similarity.
    confidence_baseline : np.ndarray, shape (n_dims,)
        Variance explained ratio per axis. Used as Policy.confidence.
    corpus_paths : list of str
        Paths of documents used for fitting.
    """

    _PROBE_TEXT = (
        "strict government regulation mandatory enforcement penalties "
        "compliance audit oversight prohibition ban restrict"
    )

    def __init__(
        self,
        n_dims          : int = 6,
        model_name      : str = "all-MiniLM-L6-v2",
        chunk_max_words : int = 256,
        probe_text      : Optional[str] = None,
    ):
        self.n_dims          = n_dims
        self.model_name      = model_name
        self.chunk_max_words = chunk_max_words
        self.probe_text      = probe_text or self._PROBE_TEXT

        # Set after fit()
        self._encoder          = None
        self._pca              = None
        self._scaler           = None
        self.dimension_labels  : List[str]   = []
        self.dimension_salience: np.ndarray  = np.zeros(n_dims)
        self.confidence_baseline: np.ndarray = np.ones(n_dims) / n_dims
        self.corpus_paths      : List[str]   = []
        self._is_fit           : bool        = False

    def _load_model(self):
        SentenceTransformer = _require_sentence_transformers()
        if self._encoder is None:
            log.info(f"Loading SentenceTransformer: {self.model_name}")
            self._encoder = SentenceTransformer(self.model_name)
        return self._encoder

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of text strings. Returns shape (len(texts), embed_dim)."""
        encoder = self._load_model()
        return encoder.encode(texts, show_progress_bar=False, batch_size=32)

    def _embed_document(self, text: str) -> np.ndarray:
        """
        Chunk a document, embed each chunk, mean-pool to a single vector.
        Returns shape (embed_dim,).
        """
        chunks = _chunk_text(text, max_words=self.chunk_max_words)
        chunk_embeddings = self._embed_texts(chunks)
        return chunk_embeddings.mean(axis=0)

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(
        self,
        texts : Optional[List[str]]             = None,
        paths : Optional[List[Union[str, Path]]] = None,
    ) -> CorpusEncoder:
        """
        Fit the PCA encoder on a corpus.

        Pass either raw texts or PDF/text file paths (or both).

        Parameters
        ----------
        texts : list of str, optional
            Raw policy texts.
        paths : list of str or Path, optional
            Paths to PDF or plain text files.

        Returns
        -------
        self (for method chaining)
        """
        PCA, MinMaxScaler = _require_sklearn()

        all_texts: List[str] = list(texts or [])

        if paths:
            for p in paths:
                p = Path(p)
                self.corpus_paths.append(str(p))
                if p.suffix.lower() == ".pdf":
                    all_texts.append(_read_pdf(p))
                else:
                    all_texts.append(p.read_text(encoding="utf-8", errors="replace"))

        if not all_texts:
            raise ValueError("fit() requires at least one text or path.")

        K = len(all_texts)
        log.info(f"Embedding {K} corpus documents ...")

        doc_embeddings = np.stack(
            [self._embed_document(t) for t in all_texts], axis=0
        )  # shape (K, embed_dim)

        # Fit PCA
        effective_dims = min(self.n_dims, K, doc_embeddings.shape[1])
        if effective_dims < self.n_dims:
            log.warning(
                f"Corpus has only {K} documents; reducing n_dims from "
                f"{self.n_dims} to {effective_dims}."
            )
            self.n_dims = effective_dims

        pca = PCA(n_components=self.n_dims, random_state=42)
        projected = pca.fit_transform(doc_embeddings)  # shape (K, n_dims)
        self._pca = pca

        # Fit MinMaxScaler on PCA projections to map to [0, 1]^n_dims
        scaler = MinMaxScaler()
        scaler.fit(projected)
        self._scaler = scaler

        # Confidence baseline: normalized variance explained ratios
        evr = pca.explained_variance_ratio_
        self.confidence_baseline = evr / evr.max()

        # Dimension salience: cosine similarity of each PC loading with probe
        probe_embed = self._embed_texts([self.probe_text])[0]  # shape (embed_dim,)
        loadings    = pca.components_  # shape (n_dims, embed_dim)
        sims = np.array([
            float(np.dot(loadings[i], probe_embed) /
                  (np.linalg.norm(loadings[i]) * np.linalg.norm(probe_embed) + 1e-9))
            for i in range(self.n_dims)
        ])
        self.dimension_salience = np.clip(sims, -1.0, 1.0)

        # Dimension labels: top-3 words from each PC loading
        # We don't have a vocabulary here (we use dense embeddings), so we
        # use the corpus documents' most loading-aligned sentences instead.
        self.dimension_labels = self._compute_dimension_labels(
            all_texts, pca, n_labels=3
        )

        self._is_fit = True
        log.info(
            f"CorpusEncoder fit: {K} docs, {self.n_dims} dims, "
            f"cumvar={evr.sum():.3f}"
        )
        return self

    def _compute_dimension_labels(
        self,
        corpus_texts : List[str],
        pca,
        n_labels     : int = 3,
    ) -> List[str]:
        """
        For each PCA axis, find the n_labels corpus sentences most aligned
        with that axis. Used for interpretability in describe() and logging.
        """
        labels = []
        for dim_idx in range(self.n_dims):
            # Score all chunks from all documents against this PC
            scores, snippets = [], []
            for text in corpus_texts:
                chunks = _chunk_text(text, max_words=64)  # shorter for labels
                if not chunks:
                    continue
                embeds = self._embed_texts(chunks)
                # Project onto this PC and take absolute value (either pole)
                pc = pca.components_[dim_idx]
                dim_scores = np.abs(embeds @ pc)
                for score, chunk in zip(dim_scores, chunks):
                    scores.append(float(score))
                    snippets.append(chunk[:80].replace("\n", " "))

            if not scores:
                labels.append(f"dim_{dim_idx}")
                continue

            top_idx = np.argsort(scores)[-n_labels:][::-1]
            top_snips = [snippets[i][:40] for i in top_idx]
            labels.append(" | ".join(top_snips))

        return labels

    # ------------------------------------------------------------------
    # Encode
    # ------------------------------------------------------------------

    def encode(self, text: str) -> np.ndarray:
        """
        Encode a raw text string to an n_dims-dimensional vector in [0, 1].

        Parameters
        ----------
        text : str

        Returns
        -------
        np.ndarray, shape (n_dims,)
        """
        if not self._is_fit:
            raise RuntimeError("Call fit() before encode().")
        doc_embed  = self._embed_document(text)              # (embed_dim,)
        projected  = self._pca.transform(doc_embed.reshape(1, -1))  # (1, n_dims)
        scaled     = self._scaler.transform(projected)       # (1, n_dims)
        return np.clip(scaled[0], 0.0, 1.0)

    def encode_pdf(self, path: Union[str, Path]) -> np.ndarray:
        """Encode a PDF file."""
        return self.encode(_read_pdf(path))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, path: Union[str, Path]) -> None:
        """Serialize the fitted encoder to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        log.info(f"CorpusEncoder saved to {path}")

    @classmethod
    def load(cls, path: Union[str, Path]) -> CorpusEncoder:
        """Load a serialized encoder from disk."""
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if not isinstance(obj, cls):
            raise TypeError(f"Expected CorpusEncoder, got {type(obj)}")
        log.info(f"CorpusEncoder loaded from {path}")
        return obj

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe(self) -> str:
        """Human-readable summary of the fitted encoder."""
        if not self._is_fit:
            return "CorpusEncoder: not yet fit."
        evr = self._pca.explained_variance_ratio_
        lines = [
            "=== CorpusEncoder Summary ===",
            f"Model       : {self.model_name}",
            f"Corpus size : {len(self.corpus_paths)} documents",
            f"Dimensions  : {self.n_dims}",
            f"Cum. var.   : {evr.sum():.3f}",
            "",
            "Per-dimension breakdown:",
        ]
        for i in range(self.n_dims):
            lines.append(
                f"  dim_{i}  var={evr[i]:.3f}  "
                f"conf={self.confidence_baseline[i]:.3f}  "
                f"salience={self.dimension_salience[i]:+.3f}"
            )
            lines.append(f"    label: {self.dimension_labels[i][:80]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# EmbeddingPolicyExtractor
# ---------------------------------------------------------------------------

class EmbeddingPolicyExtractor:
    """
    Wraps a fitted CorpusEncoder and produces Policy objects.

    Compatible with the full Simulation pipeline. SimConfig.opinion_dim
    must match encoder.n_dims.

    Parameters
    ----------
    encoder : CorpusEncoder
        A fitted CorpusEncoder instance.
    lag_estimator : callable, optional
        Function (text: str) -> int that estimates enforcement lag.
        Defaults to a simple keyword heuristic.

    Examples
    --------
    # Load pre-fit encoder
    extractor = EmbeddingPolicyExtractor.load("models/corpus_encoder.pkl")

    # Encode a PDF
    policy = extractor.extract("data/eu_ai_act.pdf")

    # Encode raw text
    policy = extractor.extract_text("The government introduces strict regulations ...")

    # SimConfig must match
    from policyswarm.config import SimConfig
    sim_config = SimConfig(opinion_dim=policy.dim)
    """

    _DIMENSION_NAME_TEMPLATE = "latent_axis_{i}"

    def __init__(
        self,
        encoder       : CorpusEncoder,
        lag_estimator : Optional[callable] = None,
    ):
        self.encoder       = encoder
        self.lag_estimator = lag_estimator or _keyword_lag_estimate

        if not encoder._is_fit:
            raise ValueError(
                "EmbeddingPolicyExtractor requires a fitted CorpusEncoder. "
                "Call encoder.fit() first."
            )

    @classmethod
    def load(cls, encoder_path: Union[str, Path]) -> EmbeddingPolicyExtractor:
        """Load from a serialized CorpusEncoder file."""
        encoder = CorpusEncoder.load(encoder_path)
        return cls(encoder)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(self, pdf_path: Union[str, Path]) -> Policy:
        """Extract a Policy from a PDF file."""
        text = _read_pdf(pdf_path)
        return self.extract_text(text)

    def extract_text(self, text: str) -> Policy:
        """
        Extract a Policy from raw text.

        The returned Policy uses generic dimension names (latent_axis_0,
        latent_axis_1, ...). Use encoder.dimension_labels for interpretability.

        Returns
        -------
        Policy
            vector: n_dims values in [-1, 1] (encoder output in [0, 1],
                    converted to the centred opinion space)
            confidence: normalized variance explained ratios (from PCA)
            dimension_salience: probe-similarity scores (from PCA loadings)
            dimension_names: ["latent_axis_0", ..., "latent_axis_{n-1}"]
            lag: estimated enforcement lag
        """
        vector = self.encoder.encode(text)

        lag = self.lag_estimator(text)

        dim_names = [
            f"latent_axis_{i}" for i in range(self.encoder.n_dims)
        ]

        return Policy(
            vector             = unit_to_centred(vector),
            dimension_names    = dim_names,
            confidence         = self.encoder.confidence_baseline.copy(),
            dimension_salience = self.encoder.dimension_salience.copy(),
            violator_dim_index = 0,   # convention: most "permissive" axis = dim 0
            violator_threshold = unit_to_centred(0.8),
            lag                = lag,
            narrative          = {},  # no narrative frames in Tier 2
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe(self, text: str) -> str:
        """Human-readable extraction summary for a text."""
        policy = self.extract_text(text)
        lines  = [
            "=== Embedding Extraction Summary ===",
            f"Encoder     : {self.encoder.model_name}",
            f"Dims        : {self.encoder.n_dims}",
            f"Cumvar      : {self.encoder._pca.explained_variance_ratio_.sum():.3f}",
            "",
            "Extracted Policy Vector:",
        ]
        evr = self.encoder._pca.explained_variance_ratio_
        for i, (val, conf, sal, label) in enumerate(zip(
            policy.vector,
            policy.confidence,
            policy.dimension_salience,
            self.encoder.dimension_labels,
        )):
            lines.append(
                f"  latent_axis_{i:<2}  = {val:.3f}  "
                f"(conf={conf:.3f}, salience={sal:+.3f}, var={evr[i]:.3f})"
            )
            lines.append(f"    label: {label[:80]}")
        lines.append(f"\n  enforcement_lag = {policy.lag}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lag estimation heuristic (Tier 2 fallback — no LLM available)
# ---------------------------------------------------------------------------

_LAG_PATTERNS = [
    # Patterns that suggest longer lags
    (r'\b(\d+)\s*year[s]?\b',           12.0),   # "2 years" → 2 * 12 / (60/20)
    (r'\bphased?\s+roll(?:out|in)\b',    20.0),
    (r'\bimplementation\s+period\b',     15.0),
    (r'\bgrace\s+period\b',              15.0),
    (r'\btransition\s+period\b',         15.0),
    (r'\b(\d+)\s*month[s]?\b',            2.0),  # "18 months"
    # Patterns that suggest shorter lags
    (r'\bimmediate(?:ly)?\b',             0.0),
    (r'\beffective\s+(?:upon|on)\s+(?:enactment|signing)\b', 0.0),
    (r'\beffective\s+immediately\b',      0.0),
]

def _keyword_lag_estimate(text: str) -> int:
    """
    Simple keyword heuristic for enforcement lag estimation.

    Maps temporal language to tick counts assuming a 60-tick horizon.
    No LLM required — used as default lag_estimator in EmbeddingPolicyExtractor.
    """
    text_lower = text.lower()
    score = 10.0  # default

    for pattern, weight in _LAG_PATTERNS:
        matches = re.findall(pattern, text_lower)
        if matches:
            if weight == 0.0:
                score = 0.0
                break
            # For numeric captures, use the number as a multiplier
            if matches[0] and matches[0].isdigit():
                score = min(score + float(matches[0]) * weight * 0.3, 40.0)
            else:
                score = min(score + weight, 40.0)

    return int(np.clip(round(score), 0, 40))
