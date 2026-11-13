# 设计文档：三层架构网站

对外交付的设计说明（含架构图）见 `docs/architecture.md`，本文件记录 Spec 层面的设计决策与需求映射。

## 总体方案
CloudFormation 单栈（`DbMode=ec2` 时 52 个资源），Internet → ALB（公网子网）→ EC2 ASG（应用子网，经单 NAT 出网）→ 数据库层（数据子网）。数据库层默认是 EC2 自建 MariaDB（`DbMode=ec2`，当前部署），可选 RDS MySQL（`DbMode=rds`，未验证）。

## 在现有模板上的变更
| 变更 | 需求 | 说明 |
|---|---|---|
| HTTPS 可选：`CertificateArn` 非空时创建 443 监听与 SG 入站，80 跳转 443 | 3.6 | 条件 `HasCert` |
| ALB 丢弃非法头；prod 开删除保护 | 3 / 7 | |
| ASG 目标跟踪（CPU 50%）、开启组指标 | 5 | |
| CloudWatch Agent 把 nginx 日志送到 `/{env}/webapp/{region}/ec2/nginx` | 5 | 应用角色内联最小权限，仅限该日志组 |
| VPC Flow Logs → `/{env}/webapp/{region}/vpc/flowlogs`，专用角色（含 `aws:SourceAccount/SourceArn` 防混淆代理） | 5.3 | |
| 7 个 CloudWatch 告警，无通知动作 | 5.1 | 部署角色无 SNS 权限，用户确认去掉 SNS/KMS；日后可由有权限者补 `AlarmActions` |
| CloudFormation 服务角色 `infra/iam/cfn-service-role.yaml` | 4 | 部署角色无 RDS/Secrets Manager 权限；管理员一次性部署服务角色，`deploy.sh -R` 使用，部署者只需 `iam:PassRole` |
| RDS `CopyTagsToSnapshot`，快照继承成本标签 | 6 | 仅 `DbMode=rds` |
| EBS 卷加 `data-class` 标签 | 6.1 | |
| `deploy.sh`：新增 `-c` 证书、`-R` 服务角色；运行 cfn-lint；给托管密钥补标签 | 3 / 4.4 / 6 | |
| 新增 `destroy.sh` | 7 | |
| `DbMode=ec2|rds` 参数；默认 `ec2`：EC2 自建 MariaDB + 独立加密数据卷 + SSM 保存随机密码 + S3 每日备份；数据子网增加经 NAT 的出站路由 | 3 / 4 / 7 | 部署角色无 `rds:*`（已用策略模拟与真实调用确认隐式拒绝），经用户确认先用自建方案跑通三层 |

## 数据层方案变更（已实施）
- 原设计为 RDS MySQL。部署角色没有任何 RDS 权限，创建 `DBSubnetGroup` 即被拒；修复方式（管理员授权或 CloudFormation 服务角色）需要账号管理员参与，暂不可得。
- 经用户确认，先以 `DbMode=ec2` 部署：数据库层为 EC2 自建 MariaDB 10.11，RDS 路径保留在模板中（`DbMode=rds`），权限开通后可切换（会替换数据库，需先迁移数据）。
- 偏离的需求：RDS 托管凭证（4.4）、RDS 级别的备份/Multi-AZ/存储告警。替代：随机密码存 SSM SecureString、每日 mysqldump 到 S3、主机 CPU 与状态检查告警。
- 已知问题：根卷缺 `org/workload/env/owner/managed-by` 标签；无数据库磁盘空间告警；admin 允许 `%` 主机（靠安全组限制）；连接未加密；实例被替换后 admin 密码参数与库内密码可能不一致。

## 关键取舍
- 单 NAT：约省 $32/月/个，代价是 AZ-a 故障时应用层出网中断；升级路径为每 AZ 一个 NAT + 每 AZ 一张应用路由表。
- 应用层不读数据库密钥：演示页只显示端点，故不授予 `secretsmanager:GetSecretValue`（最小权限）。真实应用上线时再按密钥 ARN 授权，且应使用独立的应用库账号而非主账号。
- 不用 ALB 访问日志：需要 S3 桶（额外资源与清理项），列入后续改进。
- 数据存储用 `DeletionPolicy: Snapshot`（RDS 实例，或 `ec2` 模式的数据卷）：删栈会留下快照；`ec2` 模式的备份桶是 `Retain`，SSM 密码参数由实例脚本创建、不属于栈。清理清单要求人工确认并删除。

## 已知缺口（命名规范中无前缀，按"查不到先确认"处理，未擅自发明）
| 资源 | 处理 | 需要的决定 |
|---|---|---|
| VPC Flow Log | 不加 `Name` 标签，仅带栈级必填标签 | 是否登记 `fl` 前缀 |
| RDS 参数组（强制 `require_secure_transport`） | 本次未创建 | 是否登记 `pg` 前缀 |

## 需求追踪
需求 1 → `docs/architecture.md`；2 → `docs/skills.md`；3 → `infra/*`；4/5/6/7 → `infra/template.yaml` + `docs/ops-checklist.md`。
