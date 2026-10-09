---
name: ontolens-evidence
description: 使用格物镜 MCP 工具建立带来源定位的证据链和确定性关系路径。
---

# 格物镜证据链

## 工具

- evidence_lookup(query, version_id)：找来源片段、文件哈希和 locator。
- graph_query(requester_id, lot_id, cabinet_id, version_id)：返回审核快照中的关系边和来源定位。
- asset_recognition(source_id)：从来源识别已知资产、资产类型和待审核关系候选。
- candidate_suggestions(source_id)：只从明确的人员 ID、类别别名和授权句式提出 proposed 候选。
- evidence_rerank_jev(query, version_id, limit)：在配置 JEV 时对证据候选做相关性重排；未配置时保留普通检索结果。

## 规则

每一个解释事实都要保留 source_id、title、locator、quote 和 sha256。先使用工具返回的证据，再组织说明；不要凭常识补齐缺失字段。

关系路径只说明“申请—人员授权—批次—物料类别—柜位—规则版本”的已记录关系。mode=synthetic_demo 时必须明确这是合成演示；不能将关系路径称为知识图谱算法效果或专业安全认证。

asset_recognition 的 observed 资产来自当前目录匹配，proposed 关系来自明确句式。授权句式中出现生效/有效至日期时，会提出 authorized_for 关系的 schema 属性候选。它不自动写入 schema、当前快照或规则。真实行业本体与标准对齐仍需资料和专业审核。

遇到来源冲突、版本不明、无定位片段或工具错误，停止在 needs_review，不交给模型自行裁决。

候选提取是确定性别名匹配基线，不是自动本体生成。候选必须经过人工确认，不能直接写入当前快照。

JEV 的 Noul 只提供证据相关性概率，代码据此标记复核优先级；JEV 不得生成 ALLOW、DENY、LIMIT 或 ISOLATE。
