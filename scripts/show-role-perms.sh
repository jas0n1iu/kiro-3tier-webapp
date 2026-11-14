#!/usr/bin/env bash
# 只读：打印某个 IAM 角色的信任策略、权限边界、托管策略和内联策略，用来排查部署权限。
# 注意：输出包含账号 ID 等信息，不要贴进文档、截图或聊天。
# 用法: show-role-perms.sh <assumed-role ARN 或角色名>
set -euo pipefail
IN="${1:?assumed-role ARN or role name}"
ROLE="${IN#*assumed-role/}"; ROLE="${ROLE%%/*}"   # 从会话 ARN 取出角色名
echo "Role: $ROLE"
echo "--- trust policy"; aws iam get-role --role-name "$ROLE" --query Role.AssumeRolePolicyDocument --output json
echo "--- permissions boundary"; aws iam get-role --role-name "$ROLE" --query Role.PermissionsBoundary --output json
for A in $(aws iam list-attached-role-policies --role-name "$ROLE" --query 'AttachedPolicies[].PolicyArn' --output text); do
  V=$(aws iam get-policy --policy-arn "$A" --query Policy.DefaultVersionId --output text)
  echo "--- managed: $A ($V)"
  aws iam get-policy-version --policy-arn "$A" --version-id "$V" --query PolicyVersion.Document --output json
done
for N in $(aws iam list-role-policies --role-name "$ROLE" --query 'PolicyNames[]' --output text); do
  echo "--- inline: $N"; aws iam get-role-policy --role-name "$ROLE" --policy-name "$N" --query PolicyDocument --output json
done
