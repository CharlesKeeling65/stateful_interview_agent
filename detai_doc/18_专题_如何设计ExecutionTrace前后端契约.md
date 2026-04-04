# 专题：如何设计 Execution Trace 前后端契约

这篇专题专门讲一个很多 Agent 产品都会遇到的问题：

> 怎样把“系统内部执行过程”变成用户能看懂、前后端都稳定的产品契约？

这个项目已经走到比较成熟的一步：
- 后端有 `AgentRun` / `AgentRunStep`
- 前端有 execution trace panel
- 中间不是直接传日志，而是走独立 run-trace contract

这非常值得学习。

---

## 1. 为什么不能直接把日志喂给前端

很多初学者会有个自然想法：
- 后端不是已经有日志了吗？
- 直接把日志展示出来不就行了？

这在工程上通常不是好方案。

因为日志是面向：
- 开发者
- 追踪
- 排障

而前端 trace 是面向：
- 用户
- operator
- 产品内执行体验

日志和 UI 的需求完全不同。

所以这个项目采用的是：

**logging 和 execution trace 两套并行抽象**

---

## 2. 一个好的 execution trace contract 应该回答什么

至少要回答：

1. 这是哪一次 run？  
2. 当前 run 是 running / completed / failed？  
3. 当前正在执行哪一步？  
4. 已完成了哪些步骤？  
5. 每一步用了多久？  
6. 整个 run 用了多久？  

这个项目里的 contract 基本都覆盖了。

---

## 3. 本项目的 contract 是怎么设计的

关键代码：
- [`app/models/agent_run.py`](../app/models/agent_run.py)
- [`app/models/agent_run_step.py`](../app/models/agent_run_step.py)
- [`app/services/run_trace_service.py`](../app/services/run_trace_service.py)
- [`frontend/src/types/api.ts`](../frontend/src/types/api.ts)

### run 级字段

- `id`
- `project_id`
- `turn_no`
- `status`
- `started_at`
- `ended_at`
- `duration_ms`
- `total_llm_tokens`
- `total_llm_calls`
- `step_count`
- `current_step_key`
- `current_step_label`
- `current_step_status`

### step 级字段

- `step_index`
- `step_key`
- `label`
- `status`
- `description`
- `method`
- `started_at`
- `ended_at`
- `duration_ms`
- `next_step_hint`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `meta`

---

## 4. 为什么 step 既要有 `step_key` 又要有 `label`

这是一个很通用的好设计。

### `step_key`
- 稳定的内部标识
- 适合程序逻辑和判断

### `label`
- 面向用户展示
- 适合在前端直接呈现

如果只有一个字段，就很容易在：
- 内部语义稳定性
- UI 友好性

之间互相牵制。

---

## 5. 为什么要有 `method`

`method` 不是必须字段，但很有价值。

它回答的是：
- “这一步大概是通过什么方式完成的？”

例如：
- `database lookup`
- `rule-based retrieval`
- `prompt asset renderer`
- `OpenAI-compatible chat.completions`

这让 execution trace 更像现代 agent CLI/TUI 的体验，而不是一串黑箱步骤名。

---

## 6. 为什么这个 contract 适合前端 polling

因为它天然支持两种状态：

### 运行中
- `status=running`
- `current_step_*` 可更新
- steps 列表不断增长/更新

### 已结束
- `status=completed` 或 `failed`
- `duration_ms` 固定
- 前端停止 polling

这说明 contract 设计得足够“时间友好”，而不是只适合离线读取。

---

## 7. 前端展示时为什么要默认折叠

execution trace 是高价值信息，但不能占满整个 transcript。

所以一个好的 UI 策略通常是：

1. 当前 active run 更突出  
2. 历史 run 默认折叠  
3. 只展开用户关心的那一条  

这就是这个项目 execution trace UI 的方向。

---

## 8. 如果你自己设计一个 execution trace contract，最小版应包含什么

最小版建议：

### run
- id
- status
- started_at
- ended_at
- duration_ms
- current_step

### step
- step_index
- step_key
- label
- status
- duration_ms

然后再逐步加：
- method
- description
- next_step_hint
- token usage
- meta

---

## 9. 一个最值得你动手做的练习

练习目标：
- 给某个 step 增加一个 `meta` 字段展示，例如 retrieval 选中的 branch 数

你会同时练到：
- 后端 trace 写入
- API contract
- 前端 trace 渲染

这比只改文案更能让你理解“契约设计”的含义。

---

## 10. 一句话总结

execution trace 的关键不只是“记录步骤”，而是：

**设计一份既稳定、又可轮询、又适合 UI、又不暴露底层噪音的前后端契约。**
