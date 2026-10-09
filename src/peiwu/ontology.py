from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OntologyType:
    identifier: str
    label: str
    description: str


@dataclass(frozen=True)
class OntologyRelation:
    identifier: str
    label: str
    subject_type: str
    object_type: str
    description: str


TYPES = (
    OntologyType("Person", "人员", "提出领用或具备授权的主体"),
    OntologyType("Chemical", "物料", "具有危害类别和单次限制的物料"),
    OntologyType("HazardClass", "危害类别", "教学演示中的类别标识"),
    OntologyType("Lot", "批次", "具有库存和状态的物料批次"),
    OntologyType("StorageZone", "柜位", "允许存放特定类别的目标位置"),
    OntologyType("Policy", "制度/规则", "带版本、生效期和来源的约束"),
    OntologyType("Request", "领用申请", "一条历史回放或旁路核验申请"),
    OntologyType("Decision", "程序决定", "四种确定性结果或人工复核状态"),
    OntologyType("Evidence", "证据片段", "带 source_id、定位和哈希的原始片段"),
)

RELATIONS = (
    OntologyRelation("authorized_for", "授权类别", "Person", "HazardClass", "人员在证据和有效期范围内具备类别授权"),
    OntologyRelation("lot_of", "批次对应物料", "Lot", "Chemical", "批次归属的物料"),
    OntologyRelation("has_hazard", "物料危害类别", "Chemical", "HazardClass", "物料的教学危害类别"),
    OntologyRelation("allows_class", "柜位允许类别", "StorageZone", "HazardClass", "柜位接受的类别"),
    OntologyRelation("supported_by", "来源支持", "Policy", "Evidence", "制度/关系由来源片段支持"),
    OntologyRelation("constrains", "制度约束", "Policy", "Request", "制度或规则影响申请核验"),
    OntologyRelation("decides", "决定申请", "Decision", "Request", "确定性程序决定一条申请"),
)


def schema() -> dict:
    return {
        "version": "peiwu-ontology-1",
        "types": [item.__dict__ for item in TYPES],
        "relations": [item.__dict__ for item in RELATIONS],
        "alignment": {
            "status": "synthetic_demo",
            "external_standard": None,
            "notice": "当前 schema 是教学演示模型；未对齐任何真实行业规范或标准体系",
        },
    }
