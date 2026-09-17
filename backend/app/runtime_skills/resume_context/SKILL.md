---
name: resume_context
version: 2.0.0
description: 将用户已确认的简历转换成面试 Agent 可使用的脱敏、限长证据上下文。
kind: deterministic
input_schema: ResumeContextInput
output_schema: ResumeContextOutput
---
# 简历上下文准备

只接受已经完成 AI 复核并由用户确认的结构化简历章节。

- 删除“基本信息”和“其他”章节。
- 脱敏电话号码与邮箱，不向后续模型发送联系方式。
- 每个章节最多保留 12000 字，总上下文最多 30000 字。
- 原文只做脱敏和截断，不总结、不改写、不补充事实。
- 同时生成可逐字核对引用的 `searchable_text`。
