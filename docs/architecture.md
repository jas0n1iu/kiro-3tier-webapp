# 三层架构网站：架构图与设计说明

## 1. 目标与范围
在 AWS 上提供可水平扩展、数据层不暴露公网的三层网站。应用层用 nginx 静态页占位（显示实例 ID 与数据库端点），用来验证链路、扩缩容与监控；真实业务代码、自定义域名、WAF、CDN、CI/CD 不在本次范围。区域不固定，由 `deploy.sh` 按 `AWS::Region` 推导区域代码；命名与标签遵循 `.kiro/steering/` 规范（org=`kiro`，workload=`webapp`）。

## 2. 架构图
![三层架构图：用户经 Internet Gateway 与 ALB 访问可用区 a/b 的应用实例，应用实例访问数据子网中的 EC2 自建数据库；NAT 与数据库主机为 a 区单点；CloudWatch、S3 备份桶、SSM 参数库在 VPC 之外](architecture.png)



图例与读图说明
- 实线：业务流量（含端口和来源限制）；虚线：出网、指标、日志、备份等辅助流。
- 红色节点：单点。NAT 只在 a 区；数据库主机只在 a 区。a 区故障时，应用层出网中断、数据库不可用。
- 灰色虚线节点：`DbMode=rds` 时才创建的 RDS，当前部署未启用（账号无 RDS 权限）。当前 data-b 子网为空，仅为将来 RDS 的子网组预留。
- ALB 是一个跨 pub-a 与 pub-b 的逻辑资源，图中画在两区之间；两个应用实例分布在 a、b 两区。
- 安全组边界以子网标题中的 SG 名标注：ALB SG → App SG → DB SG，逐层只允许上一层访问。
- 告警目前没有通知动作（部署角色无 SNS 权限）。HTTPS 默认不启用，传入证书 ARN 后才会有 443。

## 3. 分层设计
- 表现层：Internet-facing ALB 位于两个公网子网。HTTP 健康检查 `/health`。传入 ACM 证书 ARN 后自动增加 443 监听（TLS1.3/1.2 策略），80 跳转 443。ALB 丢弃非法头；prod 开删除保护。
- 应用层：Launch Template + ASG（最小 2、最大 4，跨两 AZ），位于私有应用子网，经 NAT 出网。ELB 健康检查驱动替换；CPU 目标跟踪 50% 自动扩缩。无 SSH，运维走 SSM Session Manager。
- 数据层：由参数 `DbMode` 选择。
  - `ec2`（默认，当前部署）：数据子网中的一台 EC2（AZ-a）运行 MariaDB 10.11（MySQL 协议兼容）。数据放在独立的加密 gp3 数据卷（挂载 `/var/lib/mysql`，`DeletionPolicy: Snapshot`，实例替换后数据仍在）。首次启动时生成随机 `admin` 密码并存入 SSM SecureString `/{env}/webapp/{region}/db/admin`；systemd 定时器每天把 `mysqldump` 备份到 S3（带生命周期，默认 14 天）。数据子网增加经 NAT 的出站默认路由（装包、SSM、S3），仍无入站路径。**这是自建数据库，不是托管服务**：补丁、高可用、恢复演练都由我们负责。
  - `rds`：RDS MySQL，凭证由 RDS 托管，需要账号授予 RDS 权限（当前部署角色没有，因此未使用）。在两种模式间切换会替换数据库，需先迁移数据。

## 4. 网络与安全
- 三层 SG 链式引用：Internet →(80/443) ALB SG →(80) App SG →(3306) DB SG；无 `0.0.0.0/0` 的非 Web 端口。
- 权限最小化：EC2 角色 = SSM 托管策略 + 仅限 nginx 日志组的写日志权限；不授予 Secrets Manager 权限（占位页不读密钥）。Flow Logs 角色限定服务主体，并带 `aws:SourceAccount` / `aws:SourceArn` 条件防混淆代理。
- 加密：EBS（含数据库数据卷）与 S3 备份桶静态加密；备份桶拒绝非 TLS 访问。数据库连接目前未启用 TLS（见第 8 节）。
- 部署权限：管理员一次性创建 CloudFormation 服务角色（`infra/iam/cfn-service-role.yaml`），资源创建权限限定在本 workload/环境/区域的命名范围内；部署者只需 `iam:PassRole`。

## 5. 可用性
| 组件 | 现状 | 单点/风险 | 升级路径 |
|---|---|---|---|
| ALB / ASG | 跨 2 AZ | 无 | 提高最小实例数 |
| NAT | 1 个（AZ-a） | AZ-a 故障时应用层无法出网（已有实例仍可服务 ALB 流量） | 每 AZ 一个 NAT + 每 AZ 一张应用路由表 |
| 数据库 | 单台 EC2（AZ-a）；RDS 模式默认单 AZ | AZ-a 或主机故障即不可用，需从数据卷或 S3 备份恢复 | 启用 RDS（`DbMultiAz=true`），或自建主从复制 |

## 6. 监控
7 个 CloudWatch 告警（ALB 5xx、目标 5xx、不健康主机、ASG CPU、数据库主机 CPU 与状态检查；RDS 模式下为 RDS CPU/剩余存储/连接数）（当前仅在控制台可见，无通知动作：部署角色无 SNS 权限）；nginx 访问/错误日志与 VPC Flow Logs 进入按规范命名的日志组（默认保留 14 天）。ASG 开启组指标。详见 `docs/ops-checklist.md`。

## 7. 成本
主要成本项：NAT Gateway（固定小时费 + 流量）、ALB、2 台 t3.micro、一台 t3.micro 数据库主机加 20 GiB 数据卷与 S3 备份（RDS 模式下为 db.t3.micro）、日志。必填标签 `org/workload/env/owner/managed-by` 由栈级标签传播，EBS、RDS 另带 `data-class`；需在 Billing 控制台激活成本分配标签。具体费用请用 AWS Pricing Calculator 按所选区域估算，本文不给数字。

## 8. 取舍与已知限制
- 单 NAT 与单台数据库主机是 dev 默认的成本取舍（见第 5 节）。
- EC2 自建数据库的限制：无数据库层面的磁盘空间告警（只有 CPU 与状态检查）；无主从与自动故障转移；备份是逻辑备份（`mysqldump`），大数据量时恢复慢；admin 账号允许来自任意主机，仅靠安全组限制到应用层；连接未加密；admin 密码仅在首次启动时生成，实例替换后需核对（见运维清单）。
- 标签缺口：应用层与数据库主机的**根卷**只带 `Name`、`data-class`，缺 `org/workload/env/owner/managed-by`（启动模板的卷标签不继承栈标签）。EC2 实例与数据卷的标签是齐的。
- 未启用 ALB 访问日志（需额外 S3 桶）、RDS 强制 TLS 参数组（仅 RDS 模式相关）、Flow Log 的 `Name` 标签：命名规范缺少对应前缀，待架构组登记后补充，未擅自发明前缀。
- 验证状态：`cfn-lint` 通过；服务端校验在 ap-northeast-2 通过（其他区域被策略拒绝）；已在 ap-northeast-2 以 `DbMode=ec2` 部署（`stk-webapp-dev-apne2-001`），站点返回 200、目标健康、数据库可用、备份已生成。**未验证**：`DbMode=rds` 路径（账号无 RDS 权限）、告警触发与恢复、备份恢复演练、CloudWatch Agent 日志投递到日志组（只确认了站点和目标健康，未单独核对日志流）。
