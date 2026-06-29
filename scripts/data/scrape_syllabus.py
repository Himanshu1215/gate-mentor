"""
scripts/data/scrape_syllabus.py
───────────────────────────────
Produce the GATE Data Science & AI (DA) syllabus as markdown for ingestion.

Two modes:
  1. (default) Write the bundled, hand-curated official GATE DA syllabus. This
     is reliable, offline, and never breaks — the official syllabus changes
     rarely. Output: knowledge/official/syllabus/gate_da_syllabus.md
  2. (--url URL) Best-effort fetch + plain-text extraction from a page you
     trust, for cross-checking the bundled copy. Requires `requests` and
     `beautifulsoup4` (kept out of the core requirements; install on demand).
     RESPECT the site's robots.txt / terms of service before using this.

Usage
-----
    python scripts/data/scrape_syllabus.py
    python scripts/data/scrape_syllabus.py --url https://example.org/gate-da-syllabus
"""

import os
import sys
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SYLLABUS_DIR = os.path.join(ROOT, "knowledge", "official", "syllabus")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Canonical GATE DA (Data Science & Artificial Intelligence) syllabus.
# Source: IIT official GATE DA information brochure. Update if the board revises it.
BUNDLED_SYLLABUS = """# GATE Data Science & Artificial Intelligence (DA) — Syllabus

## 1. Probability and Statistics
- Counting (permutation and combinations), probability axioms, sample space, events.
- Independent events, mutually exclusive events, marginal/conditional/joint probability.
- Bayes Theorem.
- Conditional expectation and variance.
- Mean, median, mode, standard deviation; correlation and covariance.
- Random variables: discrete (uniform, Bernoulli, binomial, Poisson) and continuous
  (uniform, exponential, Poisson, normal, standard normal, t-distribution,
  chi-squared) distributions; cumulative distribution function; PMF; PDF.
- Central limit theorem.
- Confidence intervals; z-test, t-test, chi-squared test.

## 2. Linear Algebra
- Vector space, subspaces, linear dependence and independence of vectors.
- Matrices: projection, orthogonal, idempotent, partition matrices and their properties.
- Quadratic forms.
- Systems of linear equations and solutions; Gaussian elimination.
- Eigenvalues and eigenvectors.
- Determinant, rank, nullity, projections.
- LU decomposition; singular value decomposition (SVD).

## 3. Calculus and Optimization
- Functions of a single variable, limit, continuity and differentiability.
- Taylor series.
- Maxima and minima.
- Single-variable optimization.

## 4. Programming, Data Structures and Algorithms
- Programming in Python.
- Basic data structures: stacks, queues, linked lists, trees, hash tables.
- Search algorithms: linear search and binary search.
- Sorting: selection sort, bubble sort, insertion sort; divide-and-conquer (mergesort, quicksort).
- Graph theory; basic graph algorithms: traversals, shortest path.

## 5. Database Management and Warehousing
- ER-model; relational model: relational algebra, tuple calculus, SQL.
- Integrity constraints, normal forms.
- File organization, indexing.
- Data types, data transformation (normalization, discretization, sampling,
  compression); data warehouse modelling: schema for multidimensional data models,
  concept hierarchies, measures and computations.

## 6. Machine Learning
### Supervised Learning
- Regression and classification problems; simple linear regression, multiple linear regression.
- Ridge regression.
- Logistic regression, k-nearest neighbour, naive Bayes classifier, linear discriminant analysis.
- Support vector machine, decision trees, bias-variance trade-off, cross-validation
  (leave-one-out, k-folds).
- Multi-layer perceptron, feed-forward neural network.
### Unsupervised Learning
- Clustering algorithms: k-means/k-medoid, hierarchical clustering (top-down, bottom-up),
  single/complete/average linkage.
- Dimensionality reduction: principal component analysis.

## 7. Artificial Intelligence
- Search: informed, uninformed, adversarial.
- Logic: propositional, predicate.
- Reasoning under uncertainty: conditional independence representation, exact inference
  through variable elimination, approximate inference through sampling.
"""


def write_bundled():
    os.makedirs(SYLLABUS_DIR, exist_ok=True)
    out = os.path.join(SYLLABUS_DIR, "gate_da_syllabus.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(BUNDLED_SYLLABUS)
    logger.info(f"Wrote bundled GATE DA syllabus -> {out} ({len(BUNDLED_SYLLABUS)} chars)")
    return out


def fetch_url(url):
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("URL mode needs: pip install requests beautifulsoup4")
        sys.exit(1)

    logger.info(f"Fetching {url} (ensure this is permitted by the site's ToS/robots.txt)")
    resp = requests.get(url, timeout=30, headers={"User-Agent": "gate-mentor-syllabus/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())

    os.makedirs(SYLLABUS_DIR, exist_ok=True)
    out = os.path.join(SYLLABUS_DIR, "gate_da_syllabus_fetched.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Fetched from {url}\n\n{text}\n")
    logger.info(f"Wrote fetched syllabus -> {out} ({len(text)} chars). Review before ingesting.")
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate the GATE DA syllabus markdown.")
    parser.add_argument("--url", help="Optional URL to fetch + cross-check (needs requests, bs4)")
    args = parser.parse_args()

    write_bundled()
    if args.url:
        fetch_url(args.url)


if __name__ == "__main__":
    main()
