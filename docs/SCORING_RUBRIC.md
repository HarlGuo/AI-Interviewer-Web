# 面试评分量表 V1

## 采用依据

本项目采用结构化面试的行为锚定评分方法：统一评价维度，使用事先定义的等级描述，只依据回答中的行为证据评分，并为每项评分记录理由。

- U.S. Office of Personnel Management, [Structured Interview Guide](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/guide.pdf)
- U.S. Office of Personnel Management, [Structured Interview Example Rating Scale](https://www.opm.gov/policy-data-oversight/assessment-and-selection/examples/structured-interview-example.pdf)
- Public Service Commission of Canada, [Appointment processes: how to conduct interviews](https://www.canada.ca/en/public-service-commission/services/public-service-hiring-guides/appointment-processes-how-conduct-interviews.html)

这些资料共同支持 1–5 统一量表、行为锚点、岗位相关能力和逐项证据理由。项目不复制特定岗位答案，而是采用其评估方法。

## 固定维度与计算

内容完整性、岗位匹配度、表达逻辑、流畅度、个人贡献清晰度、数据证据。六项等权；缺乏证据的维度不计入平均分，并显示“证据不足”。

| 等级 | 行为锚点 | 展示分数 |
|---:|---|---:|
| 1 | 未展示该能力，或回答与问题明显无关 | 20 |
| 2 | 仅有零散、模糊或主要依赖追问后才出现的证据 | 40 |
| 3 | 提供基本可接受的相关证据，但深度、范围或清晰度有限 | 60 |
| 4 | 提供清晰、具体且较完整的证据，能够说明行动与结果 | 80 |
| 5 | 提供充分、具体且相互印证的证据，明显超过基本要求 | 100 |

模型只返回等级、理由、原文证据和建议。后端验证证据确实出现在用户回答中，再按固定映射计算分数和等权平均值。该分数用于练习反馈，不代表录用概率或真实招聘结论。
