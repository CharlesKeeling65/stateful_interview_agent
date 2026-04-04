# Harness Engineering：从本项目迁移到通用 AI Agent

学这个仓库最重要的不是“会改这个项目”，而是：

**学会把它抽象成一套通用 AI Agent 工程方法。**

这篇文档专门讲迁移性。

---

## 1. 先分清：哪些是“项目特有逻辑”，哪些是“通用 harness 结构”

### 项目特有逻辑

- Code Understand 四阶段框架
- Panorama / Architecture / Code Detail / Use Cases 的具体 rubric
- 针对代码理解的 coverage 指标
- `问题.md` 提供的问答节奏参考

### 通用 harness 结构

- prompt asset system
- planner
- validator
- state / memory
- branch retrieval
- human review signal
- run trace
- structured logging

学习时要始终把这两层分开。

---

## 2. 你以后做别的 agent，可以直接复用什么

### 2.1 Prompt 资产层

当前做法：
- YAML prompt files
- prompt schema
- loader / renderer

可迁移到：
- writing agent
- research agent
- coding agent
- business workflow agent

### 2.2 Planner 层

当前做法：
- 先决定下一步意图和目标
- 再渲染 prompt

可迁移到：
- 任何 multi-step agent

### 2.3 Validator 层

当前做法：
- 对模型输出做第二层质量约束

可迁移到：
- 任何对输出质量有明确 contract 的 agent

### 2.4 State / Memory 层

当前做法：
- coverage_state
- branches
- question_history

可迁移到：
- task state
- evidence memory
- file investigation memory
- unresolved issue memory

### 2.5 Run Trace 层

当前做法：
- AgentRun
- AgentRunStep
- step timeline

可迁移到：
- 几乎所有可视化 agent 产品

---

## 3. 如果你做的是 Code Agent，可以怎么复用

把本项目的概念替换一下：

### 当前项目
- stage = interview phase
- target = question target
- coverage = understanding coverage

### code agent 中
- stage = investigation / edit / verify / summarize
- target = file / function / test / command
- coverage = files inspected / hypotheses verified / fixes attempted

### 对应迁移

- `coverage_service.py` -> 调查进度状态
- `question_planner.py` -> 下一步动作规划器
- `question_validator.py` -> patch / command / summary 校验器
- `run_trace_service.py` -> 执行步骤展示

---

## 4. 如果你做的是 Research Agent，可以怎么复用

### 当前项目
- branch = 主题分支
- framework gaps = rubric 缺口

### research agent 中
- branch = research theme / sub-question
- framework gaps = 尚未覆盖的研究问题 / 证据缺口

### 对应迁移

- coverage framework -> evidence coverage matrix
- planner -> decide next source / next sub-question
- validator -> answer completeness / citation coverage check

---

## 5. 如果你做的是 Workflow Agent，可以怎么复用

### 当前项目
- user submits answer
- system plans next question

### workflow agent 中
- user submits intent / task state
- system plans next tool call / next subtask

### 对应迁移

- human review signal -> approval / override / reroute signal
- stage manager -> workflow phase manager
- prompt renderer -> tool instruction renderer
- run trace -> task execution timeline

---

## 6. 一套通用 Agent Harness 模板应该长什么样

你以后可以把这套结构抽象成：

```text
app/
  routes/
  models/
  workflow/
  state/
  planner/
  validator/
  prompts/
  llm/
  traces/
  logging/
  debug/
frontend/
  views/
  hooks/
  run-trace/
  human-review/
```

这个目录思想已经能从本项目里看出来。

---

## 7. 最值得迁移的工程原则

### 原则 1：模型只是组件，不是系统本身

### 原则 2：复杂行为要拆成 state / plan / generate / validate

### 原则 3：人类输入必须结构化，才能真正进入工作流

### 原则 4：execution trace 要服务用户，而不是只服务开发者

### 原则 5：observability 不能反向打断主流程

### 原则 6：状态结构要能兼容迭代，而不是一次写死

---

## 8. 你后续自己做 agent 时最实用的落地步骤

### 第一步：先定义 state contract

不要先写 prompt。

先定义：
- 系统要记住什么
- 系统如何知道自己完成了多少

### 第二步：再写 planner contract

定义：
- 下一步要决定哪些字段
- 为什么做这个决定

### 第三步：最后才写 prompt

因为 prompt 只是 planner 决策的语言化执行层。

### 第四步：一开始就加 trace

别等出问题了再补 observability。

---

## 9. 对 AI 初学者最重要的一点

如果你把这个仓库只看成“一个代码理解工具”，你学到的是局部。  
如果你把它看成“一个完整的 agent harness 样板”，你以后做别的 agent 会快很多。

---

## 10. 一句话总结

这个项目最有价值的地方，不只是功能本身，而是它已经把很多主流 AI Agent 的核心工程问题都落成了真实代码。  
学会抽象这些结构，你以后做别的 agent 就不会总是从 prompt 开始重来。
