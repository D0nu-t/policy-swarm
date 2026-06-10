"""
policyswarm.tools.fit_encoder
==============================
CLI tool for fitting a Tier 2 CorpusEncoder from a directory of policy PDFs.

Usage
-----
    python -m policyswarm.tools.fit_encoder \\
        --corpus-dir data/policy_corpus/ \\
        --n-dims 6 \\
        --output models/corpus_encoder.pkl

    # With custom sentence transformer model
    python -m policyswarm.tools.fit_encoder \\
        --corpus-dir data/policy_corpus/ \\
        --n-dims 8 \\
        --model all-mpnet-base-v2 \\
        --output models/corpus_encoder_mpnet.pkl

    # Custom probe text for ideology salience
    python -m policyswarm.tools.fit_encoder \\
        --corpus-dir data/healthcare_corpus/ \\
        --n-dims 4 \\
        --probe "strict mandatory healthcare regulation government intervention" \\
        --output models/healthcare_encoder.pkl

    # Describe a fitted encoder
    python -m policyswarm.tools.fit_encoder \\
        --describe models/corpus_encoder.pkl

    # Test-encode a document
    python -m policyswarm.tools.fit_encoder \\
        --encode data/new_policy.pdf \\
        --encoder models/corpus_encoder.pkl

Output
------
The encoder is serialized to --output as a pickle file containing the
fitted CorpusEncoder. Load it in experiments with:

    from policyswarm.extraction_embedding import EmbeddingPolicyExtractor
    extractor = EmbeddingPolicyExtractor.load("models/corpus_encoder.pkl")
    policy = extractor.extract("data/new_regulation.pdf")
    sim_config = SimConfig(opinion_dim=policy.dim)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("fit_encoder")


def parse_args():
    p = argparse.ArgumentParser(
        description="Fit a Tier 2 CorpusEncoder from a directory of policy PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # --- Fit mode ---
    fit_group = p.add_argument_group("Fit mode (requires --corpus-dir and --output)")
    fit_group.add_argument(
        "--corpus-dir",
        type=Path,
        help="Directory containing policy PDF or .txt files.",
    )
    fit_group.add_argument(
        "--output",
        type=Path,
        help="Output path for serialized encoder (e.g. models/encoder.pkl).",
    )
    fit_group.add_argument(
        "--n-dims",
        type=int,
        default=6,
        help="Number of PCA components (opinion dimensions). Default 6.",
    )
    fit_group.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help=(
            "SentenceTransformer model name. Default 'all-MiniLM-L6-v2'. "
            "Higher quality: 'all-mpnet-base-v2'."
        ),
    )
    fit_group.add_argument(
        "--probe",
        type=str,
        default=None,
        help=(
            "Probe text for ideology salience computation. "
            "Default: 'strict government regulation mandatory enforcement penalties'."
        ),
    )
    fit_group.add_argument(
        "--glob",
        type=str,
        default="*.pdf",
        help="File glob pattern within --corpus-dir. Default '*.pdf'.",
    )
    fit_group.add_argument(
        "--min-variance",
        type=float,
        default=None,
        help=(
            "If set, override --n-dims with the minimum number of components "
            "to explain at least this fraction of variance (e.g. 0.85)."
        ),
    )

    # --- Describe mode ---
    describe_group = p.add_argument_group("Describe mode (requires --describe)")
    describe_group.add_argument(
        "--describe",
        type=Path,
        metavar="ENCODER_PATH",
        help="Load and print a summary of an existing encoder.",
    )

    # --- Encode mode ---
    encode_group = p.add_argument_group("Encode mode (requires --encode and --encoder)")
    encode_group.add_argument(
        "--encode",
        type=Path,
        metavar="DOC_PATH",
        help="PDF or text file to encode and show the resulting policy vector.",
    )
    encode_group.add_argument(
        "--encoder",
        type=Path,
        metavar="ENCODER_PATH",
        help="Encoder to use for --encode mode.",
    )

    return p.parse_args()


def _collect_paths(corpus_dir: Path, glob: str) -> list[Path]:
    paths = list(corpus_dir.glob(glob))
    if not paths:
        # Also try txt
        paths = list(corpus_dir.glob("*.txt"))
    if not paths:
        log.error(f"No files matching '{glob}' found in {corpus_dir}")
        sys.exit(1)
    log.info(f"Found {len(paths)} files matching '{glob}' in {corpus_dir}")
    return sorted(paths)


def _auto_n_dims(corpus_paths, model_name, min_variance):
    """
    Fit a temporary full PCA to find the minimum n_dims for min_variance.
    Avoids loading the encoder twice by returning the recommended n_dims.
    """
    from policyswarm.extraction_embedding import CorpusEncoder, _read_pdf
    from sklearn.decomposition import PCA
    import numpy as np

    enc = CorpusEncoder(n_dims=1, model_name=model_name)
    enc._load_model()

    texts = []
    for p in corpus_paths:
        try:
            texts.append(_read_pdf(p) if p.suffix == ".pdf" else p.read_text())
        except Exception as e:
            log.warning(f"Skipping {p}: {e}")

    embeddings = [enc._embed_document(t) for t in texts]
    mat = np.stack(embeddings, axis=0)

    max_components = min(len(texts), mat.shape[1])
    pca = PCA(n_components=max_components, random_state=42)
    pca.fit(mat)

    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n_dims = int(np.searchsorted(cumvar, min_variance)) + 1
    n_dims = max(2, min(n_dims, max_components))

    log.info(
        f"Auto n_dims={n_dims} explains {cumvar[n_dims-1]:.3f} variance "
        f"(target: {min_variance})"
    )
    return n_dims


def main():
    args = parse_args()

    # ── Describe mode ────────────────────────────────────────────────────
    if args.describe:
        from policyswarm.extraction_embedding import CorpusEncoder
        enc = CorpusEncoder.load(args.describe)
        print(enc.describe())
        return

    # ── Encode mode ──────────────────────────────────────────────────────
    if args.encode:
        if not args.encoder:
            log.error("--encode requires --encoder path.")
            sys.exit(1)
        from policyswarm.extraction_embedding import EmbeddingPolicyExtractor
        extractor = EmbeddingPolicyExtractor.load(args.encoder)
        print(extractor.describe(
            args.encode.read_text() if args.encode.suffix == ".txt"
            else None
        ) if args.encode.suffix == ".txt" else extractor.describe(
            open(args.encode).read() if args.encode.suffix != ".pdf"
            else __import__("policyswarm.extraction_embedding",
                            fromlist=["_read_pdf"])._read_pdf(args.encode)
        ))
        return

    # ── Fit mode ─────────────────────────────────────────────────────────
    if not args.corpus_dir or not args.output:
        log.error("Fit mode requires --corpus-dir and --output. "
                  "Use --help for usage.")
        sys.exit(1)

    if not args.corpus_dir.is_dir():
        log.error(f"--corpus-dir is not a directory: {args.corpus_dir}")
        sys.exit(1)

    paths = _collect_paths(args.corpus_dir, args.glob)

    n_dims = args.n_dims
    if args.min_variance is not None:
        log.info(
            f"Auto-selecting n_dims to explain {args.min_variance:.0%} variance ..."
        )
        n_dims = _auto_n_dims(paths, args.model, args.min_variance)

    from policyswarm.extraction_embedding import CorpusEncoder

    encoder = CorpusEncoder(
        n_dims          = n_dims,
        model_name      = args.model,
        probe_text      = args.probe,
    )

    texts = []
    for p in paths:
        try:
            if p.suffix.lower() == ".pdf":
                from policyswarm.extraction_embedding import _read_pdf
                texts.append(_read_pdf(p))
            else:
                texts.append(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            log.warning(f"Skipping {p}: {e}")

    if not texts:
        log.error("All corpus files failed to read.")
        sys.exit(1)

    encoder.fit(texts=texts)
    encoder.corpus_paths = [str(p) for p in paths]

    encoder.save(args.output)

    print()
    print(encoder.describe())
    print()
    print(f"Encoder saved to: {args.output}")
    print()
    print("Usage in experiments:")
    print(f"  python run_all.py \\")
    print(f"      --policy-source embedding \\")
    print(f"      --encoder {args.output} \\")
    print(f"      --policy-doc data/new_regulation.pdf")


if __name__ == "__main__":
    main()
