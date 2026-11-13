# 需求文档：三层架构网站（three-tier-webapp）

## 简介
在 AWS 上交付一个三层网站：表现层（ALB）、应用层（EC2 Auto Scaling）、数据层（默认 EC2 自建 MariaDB，可选 RDS MySQL，见文末变更记录）。
使用 CloudFormation 部署，区域不固定（由 `deploy.sh` 按 `AWS::Region` 推导区域代码），
所有资源命名与标签遵循 `.kiro/steering/aws-naming-*.md`（org=`kiro`，workload=`webapp`，managed-by=`cfn`）。

现状（已读取 `infra/template.yaml`、`infra/deploy.sh`）：已有网络、安全组、ALB、ASG、RDS 的基础实现。
缺口：无监控告警、无 HTTPS、无流日志、无 IAM 最小权限说明、无成本标签核对、无清理清单、无设计文档与架构图。

## 需求

### 需求 1：架构图与设计说明
**用户故事：** 作为评审人，我希望用不超过三页的设计说明和一张架构图快速理解方案。

验收标准
1. THE 交付物 SHALL 包含 `docs/architecture.md`，内含 Mermaid 架构图（VPC、三层子网、ALB、ASG、RDS、NAT、数据流向）。
2. THE 设计说明 SHALL 不超过三页（约 1500 中文字），覆盖：目标与范围、分层设计、网络与安全、可用性、监控、成本、取舍与已知限制。
3. THE 设计说明 SHALL 明确说明哪些点是单点（如单 NAT）及升级路径。

### 需求 2：使用的 skills
**用户故事：** 作为团队成员，我希望知道交付过程依据了哪些 skills，便于复现。

验收标准
1. THE 交付物 SHALL 包含 `docs/skills.md`，列出实际加载并使用的 skill、用途、对应产出。
2. IF 某 skill 未实际加载，THEN 文档 SHALL NOT 将其列为已使用。

### 需求 3：IaC 脚本及说明
**用户故事：** 作为运维，我希望一条命令校验并部署整套环境。

验收标准
1. THE `infra/template.yaml` SHALL 通过 `cfn-lint`/`validate-template` 校验。
2. THE 所有资源名称 SHALL 符合命名规范正则与服务长度约束（ALB/TG ≤32，RDS ≤63，IAM Role ≤64）。
3. THE 模板 SHALL 不写死区域；`deploy.sh` SHALL 在区域未登记时中止。
4. THE `infra/README.md` SHALL 说明参数、部署、验证、回滚与销毁步骤。
5. WHEN 使用 `deploy.sh -n` THEN 脚本 SHALL 只校验模板，不创建资源。
6. THE 模板 SHALL 提供 HTTPS 可选项（传入 ACM 证书 ARN 时启用 443 并将 80 跳转 443）。

### 需求 4：权限
验收标准
1. THE 数据层安全组 SHALL 仅允许应用层安全组访问 3306；应用层 SHALL 仅允许 ALB 安全组访问 80。
2. THE EC2 角色 SHALL 仅含 `AmazonSSMManagedInstanceCore` 与 CloudWatch Agent 所需最小权限；无 SSH 入口，运维走 Session Manager。
3. THE EC2 SHALL 强制 IMDSv2；EBS 与 RDS SHALL 加密。
4. THE 数据库凭证 SHALL 由 RDS 托管（`rds!db-*`），不改名、仅补标签；占位应用不读取密钥，故应用角色不授予 Secrets Manager 权限，真实应用上线时再按密钥 ARN 授权。
5. THE `docs/ops-checklist.md` SHALL 包含权限清单（部署者、运维、应用三类主体及其所需权限）。

### 需求 5：监控
验收标准
1. THE 模板 SHALL 创建以下 CloudWatch 告警（暂无通知动作：部署角色无 SNS 权限，经用户确认去掉 SNS）：ALB 5xx、目标 5xx、TG 不健康主机数、ASG 实例 CPU、RDS CPU、RDS 剩余存储、RDS 连接数（共 7 个）。
2. THE 告警与日志组名称 SHALL 遵循 `alrt` 前缀与路径型日志组规范。
3. THE VPC SHALL 开启 Flow Logs 到 CloudWatch Logs（日志组保留期有限）。
4. THE 监控清单 SHALL 写入 `docs/ops-checklist.md`。

### 需求 6：成本标签
验收标准
1. THE 所有可打标签资源 SHALL 带 `Name/org/workload/env/owner/managed-by` 标签；存储与数据库资源（EBS、RDS）SHALL 带 `data-class`。
2. THE 标签 Key 与 Value SHALL 全小写（`Name` 例外），且 `workload`、`env` 与资源名一致。
3. THE 清单 SHALL 说明需在 Billing 控制台激活成本分配标签（`org/workload/env/owner`），并列出主要成本项（NAT、ALB、EC2、RDS）。
4. `cost-center` 无编码不填。

### 需求 7：资源清理
验收标准
1. THE `infra/` SHALL 提供 `destroy.sh`，删除前要求输入栈名确认。
2. THE 清理清单 SHALL 列出：栈删除顺序、数据快照（RDS 快照，或 ec2 模式的数据卷快照）、备份桶、SSM 密码参数、托管密钥、CloudWatch 日志组、ACM 证书、成本标签、残留 EIP/ENI 检查命令。
3. WHEN env=prod THEN 数据库 SHALL 启用保护（RDS 删除保护，或 ec2 模式的实例终止保护），`destroy.sh` SHALL 拒绝执行并提示先关闭保护。

### 需求 8：登记项
1. THE 新增缩写（`tg`、`dbsng`）已登记于 `aws-naming-registry.md`；除此之外 SHALL NOT 引入未登记前缀。
2. IF 需要使用规范中无前缀的资源 THEN 先向用户确认，不自行发明。当前未决：Flow Log 的 `Name` 标签前缀、RDS 参数组前缀（见 design.md 已知缺口）。告警用 `alrt`，服务角色名 `role-webapp-cfn-…`、策略名 `pol-webapp-cfndeploy-…`，均来自规范。

## 范围外
自定义域名与 Route 53、WAF、CloudFront、CI/CD 流水线、真实业务应用代码（应用层以 nginx 静态页占位）。

## 变更记录
- 数据层：部署角色无 RDS 权限，经用户确认默认改为 EC2 自建 MariaDB（`DbMode=ec2`），RDS 保留为可选（`DbMode=rds`）。需求 4.4（RDS 托管凭证）仅在 `DbMode=rds` 下适用；`ec2` 模式下凭证为随机生成并存入 SSM SecureString。
- 标签：需求 6.1 当前**未完全满足**：应用层与数据库主机的 EBS 根卷缺 `org/workload/env/owner/managed-by`，待修复（见 tasks.md 第 9 项）。
- 告警：去掉 SNS 通知（无权限），7 个告警中的 3 个 RDS 告警仅在 `DbMode=rds` 创建，`ec2` 模式增加 2 个数据库主机告警。
