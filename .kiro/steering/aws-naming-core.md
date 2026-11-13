---
inclusion: always
---

# AWS 资源命名与标签规范（核心 · CAF 风格 v1.0）

生成或审核任何 AWS 资源名称、IaC 模板、脚本时必须遵守。前缀与特殊命名空间速查见 `aws-naming-reference.md`，本项目登记的组织与 workload 见 `aws-naming-registry.md`。

## 执行流程（Agent / IaC）
1. 定类型：在 reference 查资源类型前缀；查不到则停止并向用户确认，不自行发明。
2. 填构件：依次确定 workload、env、region、instance。
3. 套模式：按该资源模式拼接；特殊命名空间（S3 全局桶、路径型、数据对象）用 reference 中的专用模式。
4. 核约束：核对长度、字符、是否可改名。
5. 打标签：补齐必填标签。
6. 出结论：用户名称不合规时，列出违规项并给出合规名称，由用户决定是否采用。

## 设计原则
- 类型前置；构件顺序全局固定；名称只放创建后不变的信息（可变信息进标签）。
- 简短可读，只用登记过的缩写；全小写、`-` 分隔，便于正则与策略匹配。
- 服务自动创建、名称不可控的资源（如 `rds!db-*` 托管密钥、`/aws/lambda/*`）不改名，只补标签。

## 标准模式
```
{resource-type}-{workload}[-{qualifier}]-{env}-{region}-{instance}
```
- workload：2–12 位小写字母数字，不含 `-`，须登记。
- env：`prod | stg | uat | test | dev | sbx | shared`。一个账号原则上只承载一个 env。
- region 代码：us-east-1=use1, us-west-2=usw2, eu-central-1=euc1, eu-west-1=euw1, ap-southeast-1=apse1, ap-northeast-1=apne1, ap-northeast-2=apne2, ap-east-1=ape1, cn-north-1=cnn1, cn-northwest-1=cnnw1, 全局/跨区域=glb。绑定区域的资源必须写区域代码。
- instance：三位数字 `001`–`999`，只有一个也写。AZ 绑定资源写 `{az字母}{###}`，如 `a001`。
- 全局唯一名称冲突时在编号后加 4 位随机串（IaC 生成后固定），并记录标签 `name-suffix`。

## 必填标签
| Key | 取值 |
|---|---|
| Name | 完整资源名（默认 VPC 及其子资源除外） |
| org | 组织短码 |
| workload | 与名称一致 |
| env | 与名称一致 |
| owner | 团队邮件组，不填个人 |
| managed-by | terraform / cdk / cfn / console / cli / service |
| data-class | public / internal / confidential / restricted（存储与数据库类必填） |

可选：business-unit、cost-center（无编码不填）、project、criticality、ops-team、sla、az-id、name-suffix、expires-on（sbx 必填 yyyy-mm-dd）。
标签 Key 小写 + `-`（Name 例外），Value 小写。

## 禁止项
- 大写、空格、中文、个人姓名、日期（AMI 除外）。
- prod 资源名出现 test、demo、tmp、new、old、final。
- 未登记的缩写或 workload。
- 保留 `launch-wizard-*` 安全组；业务资源放入 default 安全组；给默认 VPC 加 Name。
- 安全组名不得以 `sg-` 开头（统一用 `nsg-`）。

## 校验正则（标准模式）
```
^[a-z0-9]{2,8}-[a-z0-9]{2,12}(-[a-z0-9]{2,12})?-(prod|stg|uat|test|dev|sbx|shared)-[a-z]{3,5}[0-9]?-([a-c])?[0-9]{3}$
```

## 自检清单
- [ ] 前缀来自 reference 或 registry
- [ ] 顺序为 type → workload → [qualifier] → env → region → instance
- [ ] 编号为三位数字
- [ ] 长度与字符满足 reference 中的服务约束
- [ ] 必填标签齐全，且与名称一致
