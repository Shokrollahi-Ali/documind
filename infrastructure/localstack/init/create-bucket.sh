#!/usr/bin/env bash
set -euo pipefail

bucket_name="${DOCUMIND_S3_BUCKET:?Document bucket name is required}"
region="${DOCUMIND_S3_REGION:?Storage region is required}"

if awslocal s3api head-bucket --bucket "$bucket_name" --region "$region" 2>/dev/null; then
    exit 0
fi

awslocal s3 mb "s3://$bucket_name" --region "$region"