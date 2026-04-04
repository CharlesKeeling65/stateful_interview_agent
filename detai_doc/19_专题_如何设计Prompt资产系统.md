# 专题：如何设计 Prompt 资产系统

很多 AI 项目一开始都把 prompt 直接写在业务代码里：

```python
prompt = f"..."
```

这种做法短期快，但长期会出很多问题：
- prompt 太长，业务代码可读性差
- 不同任务的 prompt 混在一起
- 版本管理困难
- 很难知道某次行为变化到底来自代码还是来自 prompt

这个项目已经把 prompt 体系做成了比较清晰的资产层，非常适合学习。

---

## 1. Prompt 资产系统的目标是什么

不是单纯把字符串搬到 YAML。

真正目标是：

1. **分离职责**
- 业务代码负责何时用哪个 prompt
- prompt 文件负责如何表达任务

2. **稳定契约**
- prompt 要求哪些变量
- render 后输出什么消息结构

3. **可演进**
- 可以替换版本
- 可以扩 stage-specific prompt
- 可以对不同任务拆不同资产

---

## 2. 这个项目里的 prompt 资产分层

关键代码：
- [`app/prompts/assets/`](../app/prompts/assets/)
- [`app/prompts/schemas.py`](../app/prompts/schemas.py)
- [`app/prompts/manager.py`](../app/prompts/manager.py)

可以把它理解成三层：

### 2.1 资产层

具体 YAML 文件，例如：
- `next_question_panorama.yaml`
- `next_question_architecture.yaml`
- `next_question_code_detail.yaml`
- `next_question_use_cases.yaml`
- `human_review_question.yaml`
- `drift_repair_question.yaml`

### 2.2 Schema 层

定义每个 prompt 至少要有哪些字段，例如：
- `id`
- `version`
- `description`
- `required_variables`
- `system_template`
- `user_template`

### 2.3 Manager 层

负责：
- 加载
- 校验
- 渲染
- 返回最终消息结构

---

## 3. 为什么 prompt 资产系统对 agent 特别重要

因为 agent 通常不是一个 prompt，而是一组 prompt：

- 规划 prompt
- 问题生成 prompt
- 摘要 prompt
- 修复漂移 prompt
- human review prompt

如果这些 prompt 都埋在业务函数里，你后面几乎没法维护。

这个项目的经验很明确：
- prompt 增多后，资产化不是优化，而是必需品

---

## 4. 一个好的 prompt 资产系统应该具备什么

### 4.1 有 schema

不要只靠 YAML 自由发挥。

如果没有 schema，就很容易出现：
- 少字段
- 占位符拼错
- 新老 prompt 结构不一致

### 4.2 有变量声明

prompt 应该显式声明：
- 需要哪些变量

这样 render 前就能校验，而不是运行到一半才崩。

### 4.3 有版本概念

即使你暂时不做复杂版本管理，也应该允许：
- `version: 1.0`
- `version: 2.0`

因为 prompt 也是系统行为的一部分。

### 4.4 和业务逻辑解耦

planner 决定：
- 用哪个 `prompt_id`

manager 决定：
- 怎样 render

生成器决定：
- 什么时候调用模型

这就是良好的分层。

---

## 5. 这个项目里最值得学习的设计点

### 5.1 stage-specific prompt assets

这说明项目没有走“一个万能 next question prompt”，而是按阶段拆开。

这非常符合 agent 工程实际：
- 不同阶段的约束本来就不同

### 5.2 human_review / drift_repair 也有专门 prompt

这说明 prompt 资产不只是“普通主任务 prompt”，也可以服务辅助 orchestration 任务。

### 5.3 manager 会检查 unresolved fields

这是一种非常实用的安全设计：
- 避免 `{variable}` 漏替换还直接送进模型

---

## 6. 如何自己从零设计一个最小 prompt 资产系统

最小版本建议：

### 文件结构

```text
prompts/
  assets/
    task_a.yaml
    task_b.yaml
  schemas.py
  manager.py
```

### 每个 YAML 至少包含

```yaml
id: task_a
version: "1.0"
required_variables:
  - context
  - target
system_template: |
  ...
user_template: |
  ...
```

### manager 至少提供

- `get(prompt_id)`
- `render(prompt_id, variables)`
- `render_messages(prompt_id, variables)`

---

## 7. Prompt 资产系统最容易踩的坑

### 坑 1：把业务规则又写回 YAML

例如：
- 哪个阶段选哪个 prompt
- 哪些情况要 drift repair

这些应该留在 planner / stage manager，而不是塞进 prompt 资产层。

### 坑 2：变量名不稳定

如果每个 prompt 都自己发明变量名，系统会越来越乱。

### 坑 3：把 prompt 当成不可测试的黑箱

至少应该测试：
- 能否加载
- 必填字段是否齐全
- render 是否会漏变量

---

## 8. 一句话总结

Prompt 资产系统不是“把字符串搬家”，而是：

**把 prompt 从业务逻辑里抽出来，变成有 schema、有变量契约、有版本、有分层的可维护工程资产。**
