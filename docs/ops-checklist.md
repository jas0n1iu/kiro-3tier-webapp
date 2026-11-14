# 权限、监控、成本标签与资源清理清单

变量：`ENV`=dev，`REGION`=部署区域，`RC`=区域代码（如 usw2），栈名 `stk-webapp-$ENV-$RC-001`。

## 1. 权限清单
| 主体 | 所需权限（最小集合） | 说明 |
|---|---|---|
| 部署者（人/流水线） | （DbMode=ec2 时无需服务角色，用现有 EC2/ELB/ASG/S3/SSM/IAM 角色权限即可。）以下为 DbMode=rds 的要求：`cloudformation:*` 限 `stk-webapp-*`；`iam:PassRole` 仅限 CloudFormation 服务角色（`iam:PassedToService` = `cloudformation.amazonaws.com`）；`secretsmanager:TagResource` 限 `rds!db-*`（可选，缺失时只告警） | 部署者自己不持有 RDS、Secrets Manager 等创建权限 |
| CloudFormation 服务角色 `role-webapp-cfn-ENV-RC-001` | 由 `infra/iam/cfn-service-role.yaml` 创建（管理员一次性部署）：EC2/ELB/ASG 限本区域；RDS、日志组、告警、IAM 角色按 `webapp-ENV-RC` 命名范围限定；`PassRole` 仅限 `role-webapp-*` 且传给 EC2/Flow Logs；`AttachRolePolicy` 仅限 `AmazonSSMManagedInstanceCore`；KMS 仅经 RDS/Secrets Manager 使用；信任策略限本账号 `stk-webapp-ENV-RC-*` 栈 | 部署者权限边界之外的授权都在这里，且可审计 |
| 运维人员 | 经 Identity Center 权限集 `webapp-ops`：`ssm:StartSession`（限带 `workload=webapp` 标签的实例）、`cloudwatch:Describe*/Get*`、`logs:Get*/FilterLogEvents/StartQuery`（限 `/ENV/webapp/*`）、`rds:Describe*`（DbMode=rds）、`elasticloadbalancing:Describe*` | 无 SSH、无密钥对 |
| 应用层 EC2 | 角色 `role-webapp-ec2app-…`：`AmazonSSMManagedInstanceCore` + 向 `/ENV/webapp/RC/ec2/nginx` 写日志 + `s3:GetObject` 仅限应用包对象 + `ssm:GetParameter` 仅限 `/ENV/webapp/RC/db/app` | 未授予 Secrets Manager。应用用独立数据库账号 `asapp`，只有 `asdesk.as_request` 的 SELECT/INSERT，不用 admin |
| 数据库主机（DbMode=ec2） | 角色 `role-webapp-dbhost-…`：SSM 核心 + `ssm:PutParameter` 仅限 `/ENV/webapp/RC/db/admin` 与 `/ENV/webapp/RC/db/app` + `s3:PutObject` 仅限备份桶 | 无读密码、无删对象权限；读取密码由运维人员单独授权 |
| VPC Flow Logs | 角色 `role-webapp-flowlog-…`：仅向 Flow Logs 日志组写入；信任策略带 `aws:SourceAccount`/`aws:SourceArn` | |

核对项
- [ ] 账号中无 `iam:PassRole` + `Resource: *` 的部署策略（已知：当前工作区角色的 `iam-policy-0` 含 `PutRolePolicy`/`AttachRolePolicy`/`PassRole` 且资源为 `*`，可自我提权，建议收紧）
- [ ] 无个人 IAM 用户访问，运维走 Identity Center
- [ ] 安全组：ALB 仅 80/443 对公网，App 仅来自 ALB SG，DB 仅来自 App SG（`aws ec2 describe-security-groups --filters Name=tag:workload,Values=webapp`）
- [ ] IMDSv2 强制、EBS 与备份桶加密、备份桶阻止公共访问
- [ ] 数据库主机无公网 IP，3306 只来自 App SG：`aws ec2 describe-instances --filters Name=tag:Name,Values=vm-webapp-db-ENV-RC-001`
- [ ] 数据库主机角色 `role-webapp-dbhost-…` 仅有 SSM 核心 + 写 `/ENV/webapp/RC/db/admin` 参数 + 写备份桶对象

## 2. 监控清单
| 告警 | 指标 | 阈值 | 处理 |
|---|---|---|---|
| `alrt-webapp-alb5xx-…` | ALB `HTTPCode_ELB_5XX_Count` | 5 分钟 ≥10 | 查 ALB/目标是否全部不健康、扩容是否滞后 |
| `alrt-webapp-tg5xx-…` | `HTTPCode_Target_5XX_Count` | 5 分钟 ≥10 | 查 `/ENV/webapp/RC/ec2/nginx` 错误日志 |
| `alrt-webapp-tgunhealthy-…` | `UnHealthyHostCount` | ≥1，连续 3 分钟 | SSM 登录实例，查 nginx 与 `/health` |
| `alrt-webapp-asgcpu-…` | EC2 CPU（按 ASG） | >80%，连续 15 分钟 | 检查是否已达 `AppMaxSize` |
| `alrt-webapp-dbhostcpu-…`（DbMode=ec2） | 数据库主机 CPU | >80%，连续 15 分钟 | 慢查询、升级规格 |
| `alrt-webapp-dbhoststatus-…`（DbMode=ec2） | `StatusCheckFailed` | ≥1，连续 2 分钟 | 重启或从数据卷/备份恢复 |
| `alrt-webapp-rdscpu-…`（DbMode=rds） | RDS CPU | >80%，连续 15 分钟 | 慢查询、升级规格 |
| `alrt-webapp-rdsstorage-…`（DbMode=rds） | `FreeStorageSpace` | <2 GiB（缺数据视为触发） | 扩容存储（当前未配置自动扩展） |
| `alrt-webapp-rdsconn-…`（DbMode=rds） | `DatabaseConnections` | >`DbConnAlarmThreshold`（默认 40），连续 10 分钟 | 查连接泄漏、调整阈值 |

其他
- 日志组：`/ENV/webapp/RC/ec2/nginx`、`/ENV/webapp/RC/vpc/flowlogs`，默认保留 14 天（`LogRetentionDays`）。
- 部署后动作
  - [ ] 触发一次验证：`aws cloudwatch set-alarm-state --alarm-name alrt-webapp-asgcpu-ENV-RC-001 --state-value ALARM --state-reason test`，确认告警在控制台变为 ALARM（下一个评估周期会自动恢复）
  - [ ] `aws logs describe-log-streams --log-group-name /ENV/webapp/RC/ec2/nginx` 确认有实例日志流（验证 CloudWatch Agent）
  - [ ] 访问站点 URL 并刷新，确认轮询到不同实例 ID
- 通知：**当前告警没有通知动作**（部署角色无 SNS 权限，已去掉 SNS 主题）。需要通知时，由有权限的人新增 SNS 主题并给各告警加 `AlarmActions`，或接入 AWS Chatbot。
- 未覆盖：ALB 访问日志、数据库主机磁盘空间/慢查询、应用级追踪。
- 数据库主机专项（DbMode=ec2）
  - [ ] 备份在跑：`aws s3 ls s3://s3-kiro-webapp-dbbackup-ENV-RC-001/`（每天 03:00 UTC 一份，首次部署时已生成一份）
  - [ ] 做一次恢复演练：下载最新 dump，导入测试库，确认可用
  - [ ] 磁盘：经 SSM 登录后 `df -h /var/lib/mysql`，数据量增长时调大 `DbHostVolumeGiB`（卷在线扩容后再 `xfs_growfs`）
  - [ ] 密码：`aws ssm get-parameter --with-decryption --name /ENV/webapp/RC/db/admin`（需要 ssm:GetParameter 与 KMS 解密权限；不要把密码贴到聊天或日志里）
  - [ ] 实例若被替换，admin 密码参数会被新值覆盖，而数据卷上的旧账号密码不变：替换后用 `mysql -uroot` 重置 admin 密码并与参数保持一致

## 3. 成本标签清单
必填标签：`Name`、`org=kiro`、`workload=webapp`、`env`、`owner`、`managed-by`；存储与数据库另需 `data-class`（EBS 根卷=internal，数据卷与备份桶=confidential；RDS 模式：RDS=confidential，托管密钥=restricted）。`cost-center` 无编码不填。

- [ ] 在 Billing 控制台 → Cost allocation tags 激活 `org`、`workload`、`env`、`owner`（激活后才进入账单，生效有延迟，且不追溯历史）
- [ ] 抽查标签覆盖：`aws resourcegroupstaggingapi get-resources --tag-filters Key=workload,Values=webapp --region REGION`，核对 EC2 实例/EBS 卷是否带齐栈级标签（ASG 传播行为需首次部署后验证）
- [ ] 托管密钥标签（`deploy.sh` 补标签失败时会告警，由管理员补）：`aws secretsmanager list-secrets --filters Key=tag-key,Values=workload --region REGION`
- [ ] 按标签查成本（日期用 `date` 取得，计算用脚本）：`aws ce get-cost-and-usage --time-period Start=<起>,End=<止> --granularity MONTHLY --metrics UnblendedCost --group-by Type=TAG,Key=env`
- [ ] 建议建月度预算（Budgets 接口在 us-east-1），按 `workload=webapp` 标签过滤
- 主要成本项：NAT Gateway、ALB、EC2（应用×2 + 数据库主机×1）、EBS、S3 备份、CloudWatch 日志（RDS 模式则含 RDS）。
- **已知标签缺口**：3 个 EBS 根卷缺 `org/workload/env/owner/managed-by`，按标签的成本分摊会漏掉这部分（金额较小）。核对（根卷不带栈标签，按实例挂载查）：`aws ec2 describe-volumes --region REGION --filters Name=attachment.instance-id,Values=<实例ID,逗号分隔> --query 'Volumes[].[VolumeId,Attachments[0].Device,Tags[?Key==`workload`]|[0].Value]'`，`None` 即缺标签。2026-11-14 实测：3 个根卷缺标签，数据卷标签齐全。dev 不用时请整栈删除。

## 4. 资源清理清单
删除是破坏性操作，先确认环境。

1. 确认目标：`aws cloudformation describe-stacks --stack-name stk-webapp-ENV-RC-001 --region REGION`
2. 如需保留数据：先确认 S3 备份是最新的（DbMode=rds 时改为手动快照：`aws rds create-db-snapshot --db-instance-identifier rds-webapp-ENV-RC-001 --db-snapshot-identifier <名称> --region REGION`）
3. 执行 `infra/destroy.sh -e ENV -r REGION`（需输入栈名确认；`prod` 会被拒绝，需先手动关闭 ALB（及 RDS 或数据库主机终止保护）的删除保护）
4. 删除后核对与手动清理
   - **DbMode=ec2 专项（删栈后必定有残留，不处理会继续产生少量费用）**
     - [ ] 数据卷快照：数据卷是 `DeletionPolicy: Snapshot`，删栈会留下一个 EBS 快照。不需要时：`aws ec2 describe-snapshots --owner-ids self --filters Name=description,Values='*Created by CloudFormation*' --region REGION` → `aws ec2 delete-snapshot --snapshot-id <id>`（不可恢复）
     - [ ] S3 备份桶：桶是 `Retain`，删栈后仍在。确认不再需要后清空并删除（桶启用了版本控制，需要同时删除历史版本和删除标记）：`aws s3 rb s3://s3-kiro-webapp-dbbackup-ENV-RC-001 --force` 只删当前对象；版本化对象需用 `aws s3api list-object-versions` + `delete-objects`，或在控制台使用“清空桶”
     - [ ] SSM 参数：`/ENV/webapp/RC/db/admin` 与 `/ENV/webapp/RC/db/app` 是实例启动脚本创建的，**不属于栈**，需手动删除：`aws ssm delete-parameter --name <参数名> --region REGION`
     - [ ] 应用工件桶 `s3-kiro-webapp-artifact-ENV-RC-001`：`destroy.sh` 会删除；若脚本中断则手动清空并删除
   - [ ] （DbMode=rds）RDS 最终快照：栈删除会留下一个快照（`DeletionPolicy: Snapshot`），不需要时删除：`aws rds describe-db-snapshots --region REGION` → `delete-db-snapshot`（不可恢复）
   - [ ] （DbMode=rds）自动备份在实例删除后随之删除，手动快照不会——逐个检查
   - [ ] （DbMode=rds）RDS 托管密钥 `rds!db-*` 随实例删除；`aws secretsmanager list-secrets` 确认无残留
   - [ ] CloudWatch 日志组 `/ENV/webapp/RC/*` 已随栈删除；`/aws/rds/instance/rds-webapp-*` 若存在需手动删
   - [ ] 孤儿 EIP / ENI / 卷：`aws ec2 describe-addresses`、`describe-network-interfaces`、`describe-volumes`（按 `tag:workload=webapp` 过滤）
   - [ ] ACM 证书（如自行创建）不由本栈管理，需单独删除
   - [ ] （仅 DbMode=rds）CloudFormation 服务角色栈 `stk-webapp-iam-ENV-RC-001` 由管理员保留或删除（先删应用栈再删它）
   - [ ] Billing 控制台：次日起观察 NAT/ALB/EC2（及 RDS）成本归零
