# 三层架构网站：架构图与设计说明

## 1. 目标与范围
在 AWS 上提供可水平扩展、数据层不暴露公网的三层网站。业务是“A/S 受理报告生成”：用户选择产品类别、故障类型、紧急程度，填购买日期与症状，系统按规则生成受理报告草稿（保修判定、优先级指导、维修步骤、一键复制），并把受理记录写入数据库。规则是示例规则（`app/report.py`），不用大模型（账号无 Bedrock 权限）；只用模拟数据，表单不收集个人信息。域名、WAF、CDN、CI/CD 不在范围内。区域不固定，`deploy.sh` 按区域推导区域代码；命名与标签遵循 `.kiro/steering/`（org=`kiro`，workload=`webapp`）。

## 2. 架构图
![三层架构图：用户经 Internet Gateway 与 ALB 访问可用区 a/b 的应用实例，应用实例访问数据子网中的 EC2 自建数据库；NAT 与数据库主机为 a 区单点；CloudWatch、S3 备份桶、S3 工件桶、SSM 参数库在 VPC 之外](architecture.png)

可编辑源文件：[`architecture.drawio`](architecture.drawio)（draw.io 打开，修改后重新导出 PNG）。实线为业务流量（含端口与来源限制），虚线为出网、日志、备份等辅助流；红框为单点（NAT、数据库主机只在 a 区）；灰框是 `DbMode=rds` 才创建的 RDS，当前未启用。

## 3. 分层设计
- **表现层**：面向公网的 ALB，位于两个公网子网，健康检查 `/health`。传入 ACM 证书 ARN 后增加 443 监听并让 80 跳转 443。
- **应用层**：启动模板加 ASG（2–4 台，跨两个可用区），在私有子网，经 NAT 出网。实例上 nginx 提供页面，并把 `/api/` 反代到本机 Python 服务；应用包由 `deploy.sh` 上传到 S3 工件桶，实例启动时下载。CPU 目标跟踪 50% 自动扩缩，无 SSH，运维走 SSM Session Manager。
- **数据层**：默认 `DbMode=ec2`：数据子网中一台 EC2（a 区）运行 MariaDB 10.11，数据在独立加密 gp3 卷上（删栈时留快照），每天 `mysqldump` 到 S3（保留 14 天）。应用使用独立账号 `asapp`，只有 `as_request` 表的 SELECT/INSERT，密码随机生成存 SSM SecureString。可选 `rds`（RDS MySQL，托管凭证），因账号无 RDS 权限未使用，切换会替换数据库，需先迁移数据。

## 4. 网络与安全
- 安全组逐层引用：Internet →(80/443) ALB SG →(80) App SG →(3306) DB SG。没有对 `0.0.0.0/0` 开放 22、3389 或数据库端口。
- 应用角色只有 SSM 托管策略、nginx 日志组写入、读应用包对象和读 `db/app` 一个参数；不授予 Secrets Manager。Flow Logs 角色带 `aws:SourceAccount`/`aws:SourceArn` 条件。强制 IMDSv2。
- EBS 与 S3 静态加密，两个 S3 桶都开启“阻止所有公有访问”，备份桶拒绝非 TLS 访问。
- `DbMode=ec2` 用部署者现有权限即可；`rds` 需管理员一次性创建 CloudFormation 服务角色（`infra/iam/`），该路径未验证。

## 5. 可用性
| 组件 | 现状 | 风险 | 升级路径 |
|---|---|---|---|
| ALB / ASG | 跨 2 AZ | 无 | 提高最小实例数 |
| NAT | 1 个（a 区） | a 区故障时应用层无法出网，已有实例仍可服务 | 每 AZ 一个 NAT 和路由表 |
| 数据库 | 单台 EC2（a 区） | 主机或 a 区故障即不可用 | 启用 RDS Multi-AZ，或自建主从 |
| 备份 | 每天一次逻辑备份 | RPO 最长约 24 小时，RTO 未评估，未做恢复演练 | 提高频率、加 EBS 定期快照 |

a 区故障时，b 区应用仍能返回页面，但连不上数据库，也无法出网；恢复需在 b 区重建数据库主机并从 S3 备份导入。

## 6. 监控
6 个 CloudWatch 告警：ALB 5xx、目标 5xx、不健康主机、ASG CPU、数据库主机 CPU、数据库主机状态检查（`rds` 模式为 7 个）。告警没有通知动作（账号无 SNS 权限）。nginx 日志与 VPC Flow Logs 写入按规范命名的日志组（保留 14 天）。详见 `ops-checklist.md`。

## 7. 成本
主要成本项：NAT Gateway（固定小时费加流量）、ALB、3 台 t3.micro、20 GiB 数据卷、S3、日志。必填标签 `org/workload/env/owner/managed-by` 由栈标签传播；需在 Billing 控制台激活成本分配标签。具体费用请用 AWS Pricing Calculator 估算，本文不给数字。

## 8. 取舍与已知限制
- **为什么自建数据库**：部署角色没有 RDS 权限（策略模拟为隐式拒绝，创建 DB 子网组的真实调用被拒），DynamoDB 建表也被拒，无法改用托管数据库。这是权限限制下的取舍；生产环境应使用 RDS Multi-AZ 或 Aurora。自建意味着补丁、高可用、恢复由我们负责，且无磁盘空间告警、无故障转移，`admin` 与 `asapp` 账号允许任意主机连接（靠安全组限制），连接未加密。
- **只有 HTTP**：账号无 ACM、IAM 服务器证书、CloudFront、Route 53 权限，拿不到受信任证书，自签证书也无法装到 ALB，浏览器会提示“不安全”。影响有限：页面只处理模拟数据。上线前需取得证书后运行 `./deploy.sh -c <证书ARN>`（路径在模板中，未部署验证），并向管理员申请权限。
- **标签缺口**：3 个 EBS 根卷缺 `org/workload/env/owner/managed-by`（启动模板的卷标签不继承栈标签），EC2 实例和数据卷标签齐全。
- 未启用 ALB 访问日志；Flow Log 的 `Name` 标签与 RDS 参数组因命名规范无对应前缀，待登记。
- **验证状态**：`cfn-lint`、15 个单元测试通过；已在 ap-northeast-2 部署并验证：站点与 `/health` 返回 200，两台实例目标 healthy（刚部署 1–2 分钟内有 502），提交模拟数据写库并读回一致，非法日期返回 400，两台实例均被轮询到，`asapp` 权限符合预期，日志流已写入，6 个告警为 OK，页面已在浏览器打开并截图。**未验证**：复制按钮、`rds` 路径、告警触发与恢复、备份恢复演练、数据库主机替换后的行为、HTTPS 路径。
