---
inclusion: always
---

# 附录 A · 本项目组织登记表

| 项 | 值 |
|---|---|
| 组织短码 `<org>` | `kiro` |
| 已登记 workload | `webapp`（三层网站） |
| IaC 工具 | CloudFormation（managed-by 取值 `cfn`） |
| 部署区域 | 不固定。区域代码由部署脚本按 `AWS::Region` 推导，模板不写死 |
| 默认 owner | `webapp-team@example.com`（占位，部署时用参数覆盖） |
| 业务缩写 | 无 |

## 本项目新增缩写（待架构组审批，审批前仅限本项目使用）
规范 reference 中没有以下资源的前缀，按"查不到先确认"的要求在此登记：

| 资源 | 前缀 | 示例 |
|---|---|---|
| ALB Target Group | tg | tg-webapp-web-dev-usw2-001（≤32 字符） |
| DB Subnet Group | dbsng | dbsng-webapp-dev-usw2-001 |
| 用户数据库凭证 | — | 由 RDS 托管密钥自动创建（`rds!db-*`），只补标签，不改名 |

新增缩写流程：提交登记 → 架构组审批 → 更新本表后方可使用。
