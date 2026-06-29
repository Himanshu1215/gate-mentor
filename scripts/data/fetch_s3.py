"""
scripts/data/fetch_s3.py
────────────────────────
Upload / download raw data (PDFs, answer keys, notes) from an S3-compatible
bucket so the VM can pull the latest files without a git clone of large binaries.

Works with AWS S3 and S3-compatible storage (E2E Object Storage, MinIO, Wasabi).

Credentials (environment only — never hard-code):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    S3_ENDPOINT_URL   (for E2E/MinIO — omit for AWS)
    S3_BUCKET         (optional default for --bucket)

Bucket layout mirrors the local knowledge/ tree:
    pyqs/...        -> knowledge/official/pyqs/
    answer_keys/... -> knowledge/official/answer_keys/
    textbooks/...   -> knowledge/textbooks/

Usage
-----
    pip install boto3
    export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...
    export S3_ENDPOINT_URL=https://objectstore.e2enetworks.net
    export S3_BUCKET=mentor-data

    # Download everything:
    python scripts/data/fetch_s3.py --download

    # Upload specific files:
    python scripts/data/fetch_s3.py --upload knowledge/official/pyqs/gate_da_pyqs.pdf
    python scripts/data/fetch_s3.py --upload knowledge/official/pyqs/  # whole folder

    # Download only pyqs/ prefix:
    python scripts/data/fetch_s3.py --download --prefix pyqs/
"""

import os
import sys
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DEST = os.path.join(ROOT, "knowledge")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def make_client(endpoint_url):
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        sys.exit(1)
    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        logger.error("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in the environment.")
        sys.exit(1)
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        config=Config(s3={"addressing_style": "path"}),
    )


def local_to_key(local_path):
    """Convert a local file path under knowledge/ to an S3 key."""
    rel = os.path.relpath(local_path, DEFAULT_DEST)
    return rel.replace(os.sep, "/")


def do_upload(s3, bucket, paths):
    """Upload one or more local paths (files or directories) to S3."""
    import glob as _glob

    files = []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isdir(p):
            files.extend(
                f for f in _glob.glob(os.path.join(p, "**", "*"), recursive=True)
                if os.path.isfile(f)
            )
        elif os.path.isfile(p):
            files.append(p)
        else:
            logger.warning(f"Skipping '{p}' — not a file or directory.")

    if not files:
        logger.error("No files found to upload.")
        sys.exit(1)

    count = 0
    for f in files:
        key = local_to_key(f)
        logger.info(f"↑ {f}  ->  s3://{bucket}/{key}")
        s3.upload_file(f, bucket, key)
        count += 1

    logger.info(f"Uploaded {count} file(s) to s3://{bucket}/")


def do_download(s3, bucket, prefix, dest):
    """Download all objects under prefix into dest/."""
    logger.info(f"Listing s3://{bucket}/{prefix} ...")
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            local_path = os.path.join(dest, key.replace("/", os.sep))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(f"↓ {key}  ->  {local_path}")
            s3.download_file(bucket, key, local_path)
            count += 1

    if count == 0:
        logger.warning("No objects downloaded. Check bucket/prefix/credentials.")
    else:
        logger.info(f"Downloaded {count} file(s) into {dest}")
        logger.info("Next: python scripts/data/collect_pdfs.py --ingest")


def main():
    parser = argparse.ArgumentParser(description="Upload/download data to/from S3-compatible bucket.")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET"), help="Bucket name")
    parser.add_argument("--endpoint-url", default=os.environ.get("S3_ENDPOINT_URL"),
                        help="S3-compatible endpoint (omit for AWS)")
    # Actions
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--upload", nargs="+", metavar="PATH",
                       help="Local file(s) or folder(s) under knowledge/ to upload")
    group.add_argument("--download", action="store_true", help="Download from bucket to knowledge/")
    # Download options
    parser.add_argument("--prefix", default="", help="S3 key prefix to download (default: all)")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="Local root for downloads")
    args = parser.parse_args()

    if not args.bucket:
        logger.error("No bucket. Pass --bucket or set S3_BUCKET.")
        sys.exit(1)

    s3 = make_client(args.endpoint_url)

    if args.upload:
        do_upload(s3, args.bucket, args.upload)
    else:
        do_download(s3, args.bucket, args.prefix, args.dest)


if __name__ == "__main__":
    main()
