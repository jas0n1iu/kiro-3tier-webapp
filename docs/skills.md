# 使用的 Skills

仅列出本次会话中实际加载并使用的 skill。

| Skill | 用途 | 对应产出 |
|---|---|---|
| `aws-cloudformation`（v3） | 模板编写最佳实践检查（安全默认值、DeletionPolicy、SG 范围）、`cfn-lint` 校验流程、模板头部的 `AWSToolsMetrics.AWSAgentToolkit` 标记、"沿用现有注释约定"的上下文记录规则 | `infra/template.yaml`、`deploy.sh` 的 lint 步骤 |
| `aws-iam` | 最小权限、服务角色信任策略加 `aws:SourceAccount`/`aws:SourceArn`（防混淆代理）、`iam:PassRole` 范围提示 | Flow Logs 角色、应用角色内联策略、权限清单 |
| `aws-observability` | CloudWatch 告警/日志组/Flow Logs 的选型（Step 0 判定为经典 CloudWatch，未使用 Omni） | 7 个告警、日志组、监控清单 |
| `aws-billing-and-cost-management` | 成本标签与分析方法（Cost Explorer 按标签分组、预算、日期须以工具取得、计算须脚本化） | 成本标签清单、成本项说明 |

## 项目规则（非 skill）
`.kiro/steering/aws-naming-{core,reference,registry}.md`：命名与标签规范，用于资源名、标签、新增缩写登记。

## 未使用
`aws-networking`（范围不含 VPC/ALB）、`aws-well-architected-review`（未做完整评审）、`aws-security`（未接入 GuardDuty/Security Hub）。如需上线前评审，可再用 `aws-well-architected-review` 复核本方案。

## 工具与限制
本地使用 `cfn-lint 1.46.0`。当前角色受工作坊策略限制：只允许 `ap-northeast-2` 与 `us-east-1`，且没有 RDS、SNS、Secrets Manager 权限，因此数据库层采用 EC2 自建方案（`DbMode=ec2`），告警不带通知。服务端校验与部署均在 `ap-northeast-2` 完成。
