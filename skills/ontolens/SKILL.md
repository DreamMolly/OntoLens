---
name: ontolens
description: 调用格物镜 OntoLens 判定程序，原样返回放行、打回、限量或隔离。不得自行改判。
allowed-tools:
  - terminal
metadata:
  domain: lab-issue-decision
---

# 格物镜 · OntoLens 领用判定

你是调用员，不是判定者。


1. 把申请写成 JSON。
2. 在仓库根目录运行 python -m ontolens decide --rules data/rules/v2.yaml --request 申请 JSON。
3. 回复中原样放入命令打印的 JSON。
4. 可以解释 reason_code。解释和 JSON 冲突时，承认 JSON，并重新运行命令。
5. 不得把 DENY 说成 ALLOW，不得修改 approved_quantity。
6. 要改规则时，复制新的规则文件，运行 python -m ontolens promote。accepted 不是 true 时，当前版本保持不变。
7. 不要打开 data/cases/heldout.yaml 来决定规则怎么写。
