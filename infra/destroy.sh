#!/usr/bin/env bash
# Delete the three-tier stack. DESTRUCTIVE: removes ALB, EC2 (app + db host), NAT, logs (and RDS in DbMode=rds).
# Left behind on purpose: data volume / RDS snapshot, the S3 backup bucket, and the SSM password parameter.
# Usage: ./destroy.sh [-e dev] [-r us-west-2] [-y <stack-name>]
#   Without -y you are prompted to type the stack name. env=prod is refused.
set -euo pipefail

WORKLOAD=webapp
ENV=dev
INSTANCE=001
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
CONFIRM=""

while getopts "e:r:y:" opt; do
  case $opt in
    e) ENV=$OPTARG ;;
    r) REGION=$OPTARG ;;
    y) CONFIRM=$OPTARG ;;
    *) exit 2 ;;
  esac
done

[[ -n "$REGION" ]] || { echo "Region required: use -r <region>" >&2; exit 2; }
[[ "$ENV" != "prod" ]] || { echo "Refusing to destroy env=prod. Turn off ALB deletion protection and the database protection (RDS deletion protection or EC2 termination protection) and delete manually after review." >&2; exit 3; }

declare -A REGION_CODES=(
  [us-east-1]=use1 [us-west-2]=usw2 [eu-central-1]=euc1 [eu-west-1]=euw1
  [ap-southeast-1]=apse1 [ap-northeast-1]=apne1 [ap-northeast-2]=apne2 [ap-east-1]=ape1
  [cn-north-1]=cnn1 [cn-northwest-1]=cnnw1
)
CODE="${REGION_CODES[$REGION]:-}"
[[ -n "$CODE" ]] || { echo "Region $REGION is not registered in the naming spec." >&2; exit 2; }

STACK="stk-${WORKLOAD}-${ENV}-${CODE}-${INSTANCE}"
aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" >/dev/null

if [[ -z "$CONFIRM" ]]; then
  read -r -p "Type the stack name to delete it ($STACK): " CONFIRM
fi
[[ "$CONFIRM" == "$STACK" ]] || { echo "Stack name mismatch; nothing deleted." >&2; exit 4; }

aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "Deleted $STACK."
echo "Now walk through docs/ops-checklist.md section 4 (data snapshot, backup bucket, SSM parameter, leftovers, billing tags)."
