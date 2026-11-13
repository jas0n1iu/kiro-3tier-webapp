---
inclusion: fileMatch
fileMatchPattern: '**/*.{yaml,yml,json,tf,sh}'
---

# AWS 命名速查：前缀、特殊命名空间、服务约束

未注明的资源一律套用标准模式 `{type}-{workload}[-{qualifier}]-{env}-{region}-{instance}`。

## 网络
| 资源 | 前缀 | 说明 |
|---|---|---|
| VPC | vpc | vpc-hub-shared-usw2-001 |
| Subnet | snet | snet-{workload}-{tier}-{env}-{region}-{az}{###} |
| Route Table | rt | 主路由表 qualifier 用 main |
| Network ACL | nacl | |
| Internet Gateway | igw | |
| NAT Gateway | ng | AZ 绑定：ng-hub-prod-usw2-a001 |
| Elastic IP | pip | qualifier 写用途：pip-hub-nat-prod-usw2-001 |
| VPC Endpoint | vpce | qualifier 写服务 |
| VPC Peering | peer | qualifier 写两端 |
| Transit Gateway / Attachment / RT | tgw / tgwa / tgwrt | |
| VPN / Client VPN | vpn / cvpn | |
| Direct Connect GW | dxgw | region 用 glb |
| ALB / NLB | alb / nlb | 名称上限 32 字符 |
| Route 53 私有托管区 | — | 直接用域名 |

子网 tier（qualifier）：`pub`（公网入口）、`app`（应用）、`data`（数据库/缓存/消息，不出网）、`mgmt`（运维、TGW ENI）、`pod`（容器二级网段）。需要专用子网时扩展 qualifier（如 `tgw-mgmt`），不新增 tier。

## 安全与身份
| 资源 | 前缀 | 说明 |
|---|---|---|
| Security Group | nsg | 一个对象一个 SG；不得以 `sg-` 开头 |
| IAM Role | role | qualifier 写使用方 |
| IAM Policy | pol | |
| Instance Profile | — | 与对应 Role 同名 |
| IAM User | usr | 仅限审批例外；人员访问走 Identity Center |
| Identity Center 权限集 | — | {workload}-{角色} |
| KMS Alias | kms | alias/kms-datalake-s3-prod-usw2-001 |
| WAF Web ACL | waf | |
| Key Pair | kp | 优先使用 SSM Session Manager |
| ACM 证书 | — | 不命名，Name 标签写主域名 |

## 计算与容器
| 资源 | 前缀 |
|---|---|
| EC2 | vm |
| EBS | disk |
| Launch Template / ASG | lt / asg |
| AMI | ami（允许日期：ami-orderapi-web-20261112） |
| Lambda / Layer | func / layer |
| EKS / Node Group | eks / np |
| ECS Cluster / Service | ecs / ecss |
| ECR Repository | —，用 {workload}/{镜像名} |

## 存储与数据库
S3 通用桶 s3、S3 Table Bucket s3t、EFS efs、FSx fsx、RDS rds、Aurora aur、DynamoDB ddb、ElastiCache redis、MemoryDB mdb、Redshift rs、Redshift Serverless rss、OpenSearch os（域名 ≤28 字符）。

## 数据与分析
MSK msk / mskcfg、MSK Connect mskc、Kinesis kds / kdf、MWAA mwaa、Glue gj / gc / gwf / gconn、EMR emr / emrs、Step Functions sfn、Athena Workgroup athwg。QuickSight 等控制台内对象用业务可读名，靠标签管理。

## 集成与运维
API Gateway apim（Stage 只写 v1、v2）、SNS sns、SQS sqs（FIFO 须以 `.fifo` 结尾）、EventBridge evb / evr、CloudWatch alrt / dash、CloudFormation Stack stk、Backup Vault / Plan bv / bp。

## 特殊命名空间
### 全局唯一名称（S3 通用桶等）
```
s3-{org}-{workload}[-{qualifier}]-{env}-{region}-{instance}[-{rand4}]
```
总长 ≤63，预留 5 字符给随机串。来源系统、日期等业务维度放对象前缀，不进桶名。

### 路径型（env 在前，便于按环境授权）
| 资源 | 模式 | 示例 |
|---|---|---|
| Secrets Manager | {env}/{workload}/{region}/{purpose} | prod/crm/usw2/db-admin |
| SSM Parameter | /{env}/{workload}/{region}/{purpose} | /prod/datalake/usw2/msk/bootstrap |
| CloudWatch 日志组 | /{env}/{workload}/{region}/{resource-type}/{purpose} | /prod/orderapi/usw2/apim/public |

### 数据对象（用 `_`，不带 env/region）
适用 Glue/S3 Tables/Lakehouse/Airflow DAG。Database：`{layer}` 或 `{layer}_{subject}`；Table：`{layer}_{subject}_{实体}_{粒度}`；Catalog：`{env}_{workload}`；DAG：`{layer}_{subject}_{频率}`。layer：raw / curated / serving / ref / sandbox；频率：hourly / daily / weekly / monthly。不同 layer 的库不得指向同一存储位置。

### 容器内对象
平台内部对象省略 env/region，用 `{workload}-{用途}-{规格}`，通过标签携带 env。

## 服务约束
| 资源 | 长度 | 字符 | 可改名 |
|---|---|---|---|
| Name 标签 | 256 | 任意 | 能 |
| S3 桶 / Table Bucket | 3–63 | 小写、数字、- | 否 |
| Security Group | 255 | 不得以 sg- 开头 | 否 |
| IAM Role / Policy | 64 / 128 | 字母数字 +=,.@-_ | 否 |
| Lambda | 64 | 字母数字 -_ | 否 |
| MSK | 64 | 字母数字 - | 否 |
| MWAA | 80 | 字母开头，字母数字 -_ | 否 |
| ElastiCache Serverless | 40 | 小写、数字、- | 否 |
| OpenSearch 域 | 3–28 | 小写开头，小写数字 - | 否 |
| Glue Database | 255 | 小写 | 否 |
| KMS Alias | 256 | 以 alias/ 开头 | 可新建 alias |
| Secrets Manager | 512 | 字母数字 /_+=.@- | 否 |
| ALB / Target Group（本项目补充） | 32 | 字母数字 - | 否 |
| RDS 实例标识符（本项目补充） | 63 | 小写字母开头，字母数字 - | 否 |

64 字符上限的资源：`{type}-{workload}-{qualifier}` 合计不超过 40 字符，为 env/region/instance 留余量。ALB/Target Group 只有 32 字符，qualifier 要短。
