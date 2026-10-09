---
name: ontolens-decision
description: 调用格物镜确定性判定工具，原样返回四种业务决定或人工复核状态。
---

# 格物镜确定性判定

本 Skill 不提供化学品配制、反应、提取或使用指导，只处理领用核验和证据解释。

调用 decision_check，输入申请字段与已核验的版本快照标识。工具从可信快照读取授权、库存、已领类别和规则；调用方不能在请求中注入这些字段。

## 输出契约

- status=ready：只原样返回 decision.action、approved_quantity、reason_code、rule_version；action 只能是 ALLOW、DENY、LIMIT、ISOLATE。
- status=needs_review：只说明缺失/冲突原因和证据定位，不生成业务决定。
- status=tool_error：说明工具失败并建议重试，不猜测结果。

任何解释都必须与 JSON 相同。不能把 DENY 说成允许，不能修改批准数量，不能添加程序没有返回的理由码。

## 变更

规则或授权候选只能调用 candidate_review 预览影响。它不是发布命令；发布和回滚由工作台操作者在合成演示中显式确认，专业审核人为空时必须标注“未审核”。
