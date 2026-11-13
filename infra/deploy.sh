#!/usr/bin/env bash
# Deploy the three-tier stack. Region is not fixed: pass --region or rely on AWS_REGION / AWS_DEFAULT_REGION.
# Usage: ./deploy.sh [-e dev] [-r us-west-2] [-o webapp-team@example.com] [-c <acm-cert-arn>] [-R <cfn-service-role-arn>] [-d ec2|rds] [-n]
#   -R  CloudFormation service role (create it once with iam/cfn-service-role.yaml, see README)
#   -d  database mode: ec2 (default; self-managed MariaDB, no RDS permission needed) or rds
#   -n  validate only (cfn-lint + validate-template), create nothing
set -euo pipefail

ORG=kiro
WORKLOAD=webapp
ENV=dev
INSTANCE=001
OWNER=webapp-team@example.com
CERT_ARN=""
SERVICE_ROLE=""
DB_MODE=ec2
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
DRY_RUN=false

while getopts "e:r:o:c:R:d:n" opt; do
  case $opt in
    e) ENV=$OPTARG ;;
    r) REGION=$OPTARG ;;
    o) OWNER=$OPTARG ;;
    c) CERT_ARN=$OPTARG ;;
    R) SERVICE_ROLE=$OPTARG ;;
    d) DB_MODE=$OPTARG ;;
    n) DRY_RUN=true ;;
    *) exit 2 ;;
  esac
done

[[ -n "$REGION" ]] || { echo "Region required: use -r <region>" >&2; exit 2; }
[[ "$DB_MODE" == ec2 || "$DB_MODE" == rds ]] || { echo "-d must be ec2 or rds" >&2; exit 2; }

# Region code table from the naming spec (section 2.3). Unregistered regions stop here.
declare -A REGION_CODES=(
  [us-east-1]=use1 [us-west-2]=usw2 [eu-central-1]=euc1 [eu-west-1]=euw1
  [ap-southeast-1]=apse1 [ap-northeast-1]=apne1 [ap-northeast-2]=apne2 [ap-east-1]=ape1
  [cn-north-1]=cnn1 [cn-northwest-1]=cnnw1
)
CODE="${REGION_CODES[$REGION]:-}"
[[ -n "$CODE" ]] || { echo "Region $REGION is not registered in the naming spec; register a code first." >&2; exit 2; }

STACK="stk-${WORKLOAD}-${ENV}-${CODE}-${INSTANCE}"
DIR="$(cd "$(dirname "$0")" && pwd)"

# Local lint first (no AWS call). Skipped with a notice when cfn-lint is not installed.
if command -v cfn-lint >/dev/null 2>&1; then
  cfn-lint "$DIR/template.yaml"
else
  echo "cfn-lint not found; skipping local lint (pip install cfn-lint)" >&2
fi

aws cloudformation validate-template --region "$REGION" --template-body "file://$DIR/template.yaml" >/dev/null
echo "Template valid. Stack: $STACK ($REGION)"
$DRY_RUN && exit 0

PARAMS=(Workload="$WORKLOAD" Env="$ENV" RegionCode="$CODE" Instance="$INSTANCE" Org="$ORG" DbMode="$DB_MODE")
[[ -z "$CERT_ARN" ]]    || PARAMS+=(CertificateArn="$CERT_ARN")


ROLE_ARGS=()
[[ -z "$SERVICE_ROLE" ]] || ROLE_ARGS=(--role-arn "$SERVICE_ROLE")

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$DIR/template.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  ${ROLE_ARGS[@]+"${ROLE_ARGS[@]}"} \
  --parameter-overrides "${PARAMS[@]}" \
  --tags org="$ORG" workload="$WORKLOAD" env="$ENV" owner="$OWNER" managed-by=cfn

# The RDS-managed master secret (rds!db-*) cannot be renamed or tagged by the stack: tag it here (tags only).
SECRET_ARN="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='DbSecretArn'].OutputValue" --output text)"
if [[ -n "$SECRET_ARN" && "$SECRET_ARN" != "None" ]]; then
  if ! aws secretsmanager tag-resource --region "$REGION" --secret-id "$SECRET_ARN" \
      --tags Key=org,Value="$ORG" Key=workload,Value="$WORKLOAD" Key=env,Value="$ENV" \
             Key=owner,Value="$OWNER" Key=managed-by,Value=service Key=data-class,Value=restricted; then
    echo "WARNING: could not tag $SECRET_ARN (needs secretsmanager:TagResource). Ask an admin to tag it; see docs/ops-checklist.md." >&2
  fi
fi

aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query 'Stacks[0].Outputs' --output table
