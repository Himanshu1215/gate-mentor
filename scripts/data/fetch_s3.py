"""
scripts/data/fetch_s3.py
────────────────────────
Download raw data (PDFs, answer keys, notes) from an S3-compatible bucket into
the local knowledge/ tree, so the rest of the pipeline (collect_pdfs.py ->
parse_pyqs.py -> build_dataset.py) can run.

Works with AWS S3 and S3-compatible object storage (E2E Object Storage, MinIO,
Wasabi, ...) via a custom --endpoint-url.

Credentials (read from environment — never hard-code or commit them):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    S3_ENDPOINT_URL   (optional; for E2E/MinIO/etc. — omit for AWS)
    S3_BUCKET         (optional default for --bucket)

Suggested bucket layout (prefix -> local destination is by default 1:1):
    pyqs/...        -> knowledge/official/pyqs/
    answer_keys/... -> knowledge/official/answer_keys/
    textbooks/...   -> knowledge/textbooks/
    nptel/...       -> knowledge/nptel/

Usage
-----
    pip install boto3
    export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...
    export S3_ENDPOINT_URL=https://objectstore.e2enetworks.net   # E2E example

    python scripts/data/fetch_s3.py --bucket gate-mentor-data
    python scripts/data/fetch_s3.py --bucket gate-mentor-data --prefix pyqs/
    python scripts/data/fetch_s3.py --bucket gate-mentor-data --dest knowledge
"""

import os
import sys
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DEST = os.path.join(ROOT, "knowledge")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Download data from an S3-compatible bucket.")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET"), help="Bucket name")
    parser.add_argument("--prefix", default="", help="Key prefix to download (default: whole bucket)")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="Local root to mirror keys into")
    parser.add_argument("--endpoint-url", default=os.environ.get("S3_ENDPOINT_URL"),
                        help="S3-compatible endpoint (omit for AWS)")
    args = parser.parse_args()

    if not args.bucket:
        logger.error("No bucket. Pass --bucket or set S3_BUCKET.")
        sys.exit(1)

    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        logger.error("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in the environment.")
        sys.exit(1)

    s3 = boto3.client("s3", endpoint_url=args.endpoint_url)
    logger.info(f"Listing s3://{args.bucket}/{args.prefix} ...")

    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=args.bucket, Prefix=args.prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue  # skip "directory" markers
            local_path = os.path.join(args.dest, key.replace("/", os.sep))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(f"↓ {key}  ->  {local_path}")
            s3.download_file(args.bucket, key, local_path)
            count += 1

    if count == 0:
        logger.warning("No objects downloaded. Check bucket/prefix/credentials.")
    else:
        logger.info(f"✅ Downloaded {count} file(s) into {args.dest}")
        logger.info("Next: python scripts/data/collect_pdfs.py")


if __name__ == "__main__":
    main()
