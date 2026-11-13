# 任务清单

- [x] 1. 更新 `infra/template.yaml`
  - [x] 1.1 新增参数、条件、HTTPS 监听与 SG 入站（需求 3.6）
  - [x] 1.2 应用角色内联日志权限；CloudWatch Agent；ASG 目标跟踪与组指标（需求 4、5）
  - [x] 1.3 Flow Logs、日志组、专用角色（需求 5.3）
  - [x] 1.4 7 个告警（无通知；SNS/KMS 因权限去掉）（需求 5.1）
  - [x] 1.5 标签补全：EBS `data-class`、告警/日志组 `Name`、RDS `CopyTagsToSnapshot`（需求 6）
  - [x] 1.6 `cfn-lint` 通过，名称长度/正则自检（需求 3.1、3.2）
- [x] 2. 更新 `infra/deploy.sh`，新增 `infra/destroy.sh`（需求 3、7）
- [x] 3. 写 `infra/README.md`（需求 3.4）
- [x] 4. 写 `docs/architecture.md`，含 Mermaid 架构图，≤3 页（需求 1）
- [x] 5. 写 `docs/skills.md`（需求 2）
- [x] 6. 写 `docs/ops-checklist.md`：权限、监控、成本标签、清理（需求 4–7）
- [x] 7. 总体验证：对照 requirements 逐条核对，列出未能验证的项（已在 ap-northeast-2 完成服务端校验与部署；RDS 路径因权限未验证）
- [x] 8. 数据层改为 `DbMode`（默认 EC2 自建 MariaDB，RDS 可选），已部署 `stk-webapp-dev-apne2-001` 并验证站点、目标健康、数据库、备份
- [ ] 9. 待办：补根卷成本标签；数据库磁盘空间告警；admin 密码在实例替换后的一致性；备份恢复演练；`DbMode=rds` 路径在拿到权限后验证
