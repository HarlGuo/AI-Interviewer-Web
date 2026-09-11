# 简历解析契约

## 管线

```text
PDF 校验 → 确定性提取 → NFKC 规范化 → 规则分段 → 联系方式脱敏
→ 稳定行 ID → DeepSeek 分类 → ID/词表校验 → 原始行重建 → 用户确认
```

允许章节：基本信息、个人总结、教育经历、工作/实习经历、项目经历、技能/证书及其他、其他。

## 响应语义

- `review_status = rule_only`：仅确定性提取，不得称为 AI 已验证。
- `review_status = ai_verified`：每个原始内容行恰好一次归入允许章节，并由原始文本重建。
- `review_issues`：复核警告，不是事实来源。

AI 验证仅代表结构完整性检查通过，不保证简历陈述真实或解析零错误。

## 实现位置

- 提取：`backend/app/resume_parser.py`
- AI 复核：`backend/app/ai_resume_reviewer.py`
- 接口：`backend/app/main.py` 的 `POST /v1/resumes/parse`
- 用户确认：`src/app/resume.tsx`
- 私有材料：`local-data/`（必须被 Git 忽略）
