# 专题：如何设计 Planner 输出契约

很多 agent 项目有 planner，但 planner 只是返回一句模糊的人话：

- “下一步深挖一下实现细节”

这种 planner 在 demo 里能跑，在工程里不够用。

真正适合工程化的 planner，输出必须是一个 **结构化 contract**。

这个项目已经走在这条路上，因此非常适合拿来学习。

---

## 1. 为什么 planner 输出不能只是自然语言

如果 planner 只返回一段自然语言，后面的层很难稳定使用：

- prompt 层很难知道该用哪个模板
- validator 很难知道应该检查什么
- transcript 很难解释“为什么这题这样问”
- debug 很难看清 planner 究竟做了什么决定

所以一个好的 planner，输出必须是结构化的。

---

## 2. 这个项目里的 planner 输出已经包含哪些核心字段

对应代码：
- [`app/services/question_planner.py`](../app/services/question_planner.py)

当前核心字段包括：

- `phase`
- `intent_mode`
- `question_intent`
- `target_type`
- `target_label`
- `target_identifier`
- `selected_framework_gap`
- `selected_branch_ids`
- `selected_turn_ids`
- `retrieval_focus`
- `constraints`
- `prompt_id`
- `reasoning`
- `drift_detected`
- `human_collaboration_gate`
- `human_review_applied`
- `validation_constraints`
- `why_this_question`

这已经非常接近一个完整的 planner contract。

---

## 3. 为什么这些字段都需要

### `phase`
- 说明当前处于哪个阶段
- validator 和 UI 都需要它

### `intent_mode`
- 区分：
  - `understand_current_code`
  - 其他潜在模式

### `question_intent`
- 说明这题到底在干什么
- 例如：
  - `overview_gap_fill`
  - `architecture_clarification`
  - `code_detail_deep_dive`
  - `scenario_completion`
  - `human_guided_redirect`

### `target_type` / `target_label`
- 把“下一题问什么”结构化成机器可用字段

### `selected_framework_gap`
- 说明是哪个 rubric 缺口驱动了这题

### `selected_branch_ids` / `selected_turn_ids`
- 说明这题主要基于哪些历史证据

### `constraints`
- 说明生成器必须遵守什么

### `validation_constraints`
- 说明校验器后面应该查什么

### `why_this_question`
- 说明给人看的解释

---

## 4. 一个好 planner contract 的判断标准

你可以用这 5 个问题来检查：

1. **下一步做什么** 是否清楚？  
2. **为什么做这个** 是否清楚？  
3. **基于哪些证据** 是否清楚？  
4. **生成器必须遵守什么** 是否清楚？  
5. **如果错了，校验器怎么拦** 是否清楚？  

如果这 5 个问题回答不了，planner 输出就还不够工程化。

---

## 5. 本项目里最值得学习的 planner contract 思路

### 思路 1：planner 不直接写问题，而是规定生成问题的边界

这是一个关键区别。

planner 负责：
- 目标
- 约束
- 意图

LLM 负责：
- 把这些约束语言化

### 思路 2：planner 输出要同时服务 3 类下游

1. prompt renderer  
2. validator  
3. transcript/debug  

这就是为什么字段不能只够 prompt 用。

### 思路 3：human review 也必须进入 planner contract

如果 human review 不进入 planner 输出，它就只能停留在输入层，而不会真正影响系统。

---

## 6. 如果你自己从零设计 planner contract，推荐最小版本是什么

一个最小可用版本至少要有：

```python
plan = {
    "phase": "...",
    "intent": "...",
    "target_type": "...",
    "target_label": "...",
    "constraints": [...],
    "why": "...",
}
```

然后逐步再加：

- `selected_gap`
- `selected_branch_ids`
- `selected_turn_ids`
- `validation_constraints`
- `human_review_applied`

不要一开始就只返回一段自然语言。

---

## 7. 为什么 planner contract 应该尽量 typed

当前项目里 planner 还是返回 dict，这已经足够灵活。

但从长期演进角度，更理想的方向是：
- Pydantic model
- dataclass
- typed enums

因为这样可以减少：
- 字段漂移
- 拼写错误
- 前后端契约不一致

所以你以后如果继续演进这个项目，这是很值得做的一步。

---

## 8. 一个很适合你的练习

练习目标：
- 给 planner contract 增加一个新字段：
  - `risk_level`
  - 或 `confidence`

然后思考：
- 它应该由谁设置？
- 后续谁来消费？
- 是给 UI 用、给 validator 用，还是给 debug 用？

做完这个练习，你就会更清楚“contract 设计”是什么意思。

---

## 9. 一句话总结

一个成熟的 planner，不是“替模型想一句提示语”，而是：

**为后续生成、校验、展示和调试提供一份结构化、可解释、可消费的决策合同。**
