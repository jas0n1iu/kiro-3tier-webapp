# IaC 说明（CloudFormation）

文件
- `../app/`：A/S 受理报告应用（Python 标准库 + PyMySQL，含单元测试 `app/tests`）。`deploy.sh` 先跑测试，再把它打包上传到工件桶，实例启动时下载。
- `template.yaml`：单栈，VPC、三层子网、NAT、ALB、ASG、数据库层（默认 EC2 自建 MariaDB，可选 RDS）、Flow Logs、告警（无通知）。
- `deploy.sh`：跑应用测试、cfn-lint、校验并部署；`-n` 只校验。会创建（不属于栈的）工件桶 `s3-kiro-webapp-artifact-<env>-<区域码>-001`，每次上传应用包。
- `destroy.sh`：删除栈（需确认，拒绝 prod），并删除工件桶。
- `iam/cfn-service-role.yaml`：CloudFormation 服务角色（管理员一次性部署）。**仅 `-d rds` 需要**；默认 `ec2` 模式用不到。

前置条件：AWS CLI v2、已登录的凭证；可选 `cfn-lint`（`pip install cfn-lint`）。部署者权限见 `docs/ops-checklist.md` 第 1 节。

## 数据库模式（`-d`）
- `ec2`（默认）：因当前账号没有 RDS 权限而采用的替代方案（原因见 `docs/architecture.md` 第 8 节）。数据子网内一台 EC2 运行 MariaDB 10.11，独立加密数据卷，随机 admin 密码存 SSM `/ENV/webapp/RC/db/admin`，每日 `mysqldump` 到 S3。不需要 RDS 权限。**这是自建数据库**：补丁、高可用、恢复都自己负责（见 `docs/architecture.md` 第 8 节）。
- `rds`：RDS MySQL，托管密钥。需要 RDS 权限，见下一节。
- 在两种模式间切换会替换数据库，请先迁移数据。

## 权限模型（仅 `-d rds` 需要）：CloudFormation 服务角色（一次性，管理员执行）
部署者角色（如 `WSParticipantRole`）不直接持有 RDS、Secrets Manager 等权限，只需要对服务角色有 `iam:PassRole`。由管理员先部署服务角色栈：
```bash
cd infra/iam
aws cloudformation deploy --region ap-northeast-2 \
  --stack-name stk-webapp-iam-dev-apne2-001 --template-file cfn-service-role.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides Env=dev RegionCode=apne2 \
  --tags org=kiro workload=webapp env=dev owner=webapp-team@example.com managed-by=cfn
aws cloudformation describe-stacks --region ap-northeast-2 --stack-name stk-webapp-iam-dev-apne2-001 \
  --query "Stacks[0].Outputs[?OutputKey=='CfnServiceRoleArn'].OutputValue" --output text
```
再用输出的 ARN 部署应用栈：`./deploy.sh -R <角色ARN>`。后续对该栈的更新和删除会沿用这个服务角色。
该角色的权限被限定在本 workload、环境、区域的命名范围内；EC2/ELB/Auto Scaling 只能限制到本区域。
提示：给 RDS 托管密钥补标签的步骤用的是部署者自己的权限；缺 `secretsmanager:TagResource` 时只告警，不中断部署。

## 命名与区域
栈名 `stk-webapp-<env>-<区域码>-001`。区域码由 `deploy.sh` 按区域查表得出（ap-northeast-2→apne2、us-west-2→usw2 等），表中没有的区域会中止，需先在命名规范里登记。模板不写死区域。

## 参数
| 参数 | 默认 | 说明 |
|---|---|---|
| `Env` | dev | prod/stg/uat/test/dev/sbx；prod 同时打开 ALB 删除保护和数据库删除/终止保护 |
| `RegionCode` | 脚本提供 | |
| `CertificateArn` | 空 | 空=仅 HTTP；填同区域 ACM 证书=启用 HTTPS 并将 80 跳转 443；`-c` 传入 |
| `VpcCidr` | 10.0.0.0/16 | |
| `AppInstanceType` / `AppMinSize` / `AppMaxSize` | t3.micro / 2 / 4 | |
| `DbMode` | ec2 | `ec2` 或 `rds`；`-d` 传入 |
| `Org` | kiro | 备份桶名使用 |
| `AppBundleBucket` / `AppBundleKey` | 脚本提供 | 应用包所在的桶与对象键（键含内容哈希）；不要手工填 |
| `DbHostInstanceType` / `DbHostVolumeGiB` / `DbBackupRetentionDays` | t3.micro / 20 / 14 | 仅 `ec2` 模式 |
| `DbInstanceClass` / `DbMultiAz` | db.t3.micro / false | 仅 `rds` 模式 |
| `LogRetentionDays` | 14 | 7/14/30/60/90 |
| `DbConnAlarmThreshold` | 40 | 按实例规格调整 |

## 使用
```bash
cd infra
./deploy.sh -n -r ap-northeast-2                         # 只校验（cfn-lint + validate-template），不创建资源
./deploy.sh -r ap-northeast-2                       # 部署 dev，数据库用 EC2 自建（区域也可取自 AWS_REGION）
./deploy.sh -d rds -R <服务角色ARN>                  # 数据库用 RDS（需要管理员先建服务角色）
./deploy.sh -e stg -r ap-northeast-2 -c <acm-cert-arn>   # 启用 HTTPS
```
部署后：用输出的 `SiteUrl` 访问；按 `docs/ops-checklist.md` 第 2 节验证告警与日志。

更新：重新运行 `deploy.sh`（变更集方式）。建议先 `aws cloudformation deploy --no-execute-changeset` 查看变更；数据库相关变更可能导致替换；ec2 模式下替换主机后须核对 admin 密码（见运维清单）。

回滚：CloudFormation 自动回滚失败的创建/更新。排查失败栈：`aws cloudformation describe-events --stack-name <栈名>`。

销毁：`./destroy.sh -e dev -r ap-northeast-2`，然后走 `docs/ops-checklist.md` 第 4 节（备份桶、数据卷快照和两个 SSM 参数 `db/admin`、`db/app` 不会随栈删除）。

## 费用提示
NAT Gateway、ALB、EC2（含数据库主机）即使无流量也按小时计费，不用时请删除整栈。

## 应用（A/S 受理报告）
页面 `/`：选择产品类别、故障类型、紧急程度，填购买日期和症状，生成受理报告草稿（保修判定、优先级指导、维修步骤、复制按钮），并写入数据库表 `asdesk.as_request`，页面下方显示最近 10 条。只用测试或模拟数据：表单不收集姓名、电话、地址。保修月数、处理时限和维修步骤是**示例规则**（`app/report.py`），上线前须换成真实政策。数据库不可用时报告仍会生成，页面标注“未保存”。本地测试：`cd app && python3 -m unittest discover -s tests`。

## 校验状态
- `cfn-lint`（1.46.0）：通过。
- 服务端 `validate-template`：在 ap-northeast-2 通过（其他区域被策略拒绝）。
- 已实际部署 `stk-webapp-dev-apne2-001`（`DbMode=ec2`，A/S 应用版本）：站点返回 200，两台实例目标 healthy，提交模拟数据写库并读回成功，应用库账号仅有 SELECT/INSERT，日志流与告警正常；两个 SSM 密码参数均已写入。
- HTTPS：当前账号无证书相关权限，站点只有 HTTP（浏览器显示“不安全”）。`-c` 证书路径在模板中，未部署验证。
- 未验证：浏览器里的页面交互、HTTPS 路径、`DbMode=rds` 路径（账号无 RDS 权限，未部署过）；告警触发与恢复；备份的恢复演练；数据库主机被替换后的行为。
- 已知缺口（待命名规范登记）：Flow Log `Name` 标签、RDS 参数组（强制 TLS）。详见 `.kiro/specs/three-tier-webapp/design.md`。
