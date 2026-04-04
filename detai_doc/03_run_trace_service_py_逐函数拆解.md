# `run_trace_service.py` 逐函数拆解

本文专门拆 [`app/services/run_trace_service.py`](../app/services/run_trace_service.py)。

这个文件的作用不是日志，而是“给前端 execution trace 提供稳定 run/step 数据模型”。

你可以把它理解成：
- 结构化日志：面向 observability
- run trace：面向 UI 和人类查看

这个文件就是后者的核心实现。

---

## 1. 这份服务解决的实际问题

用户点击：
- `submit answer -> generate next question`

前端想看到的不是一个 spinner，而是：
- 当前 run 是什么
- 当前卡在哪一步
- 每一步用了多久
- 哪一步失败了

`run_trace_service.py` 做的就是把一次 `/next` 调用变成可视化的 run timeline。

```mermaid
flowchart TD
    A[/projects/{id}/next] --> B[create_run]
    B --> C[traced_run_step load_project_context]
    C --> D[traced_run_step refresh_summaries]
    D --> E[traced_run_step refresh_coverage]
    E --> F[traced_run_step render_prompt / call_llm / validate_question]
    F --> G[traced_run_step persist_result]
    G --> H[finalize_run]
    H --> I[serialize_run]
    I --> J[frontend active trace / historical trace UI]
```

---

## 2. `STEP_DEFINITIONS`：这是 UI label contract，不是随便起名

源码位置：
- [`run_trace_service.py:15-52`](../app/services/run_trace_service.py#L15)

```python
STEP_DEFINITIONS = {
    "load_project_context": {
        "label": "Load project context",
        "method": "database lookup",
    },
    ...
}
```

### 每个字段代表什么

#### key
- 内部 step 标识
- 例如 `refresh_summaries`

#### `label`
- 前端给用户看的友好标题
- 例如 `Refresh summaries`

#### `method`
- 对当前步骤采用的手段做一句抽象解释
- 例如：
  - `rule-based retrieval`
  - `prompt asset renderer`
  - `database write`

### 为什么不要把这里做得太技术化

这个字段面向的是：
- 产品内 trace UI
- 人类 inspection

不是面向程序调试器。

所以这里要表达的是：
- “这一步干什么”
而不是：
- “内部函数名叫什么”

### 修改建议

如果前端 trace 看起来太像 debug console，先调这里，而不是先改前端样式。

---

## 3. `utcnow()`：看起来简单，但它统一了 run/step 时间源

源码位置：
- [`run_trace_service.py:55-56`](../app/services/run_trace_service.py#L55)

```python
def utcnow() -> datetime:
    return datetime.utcnow()
```

### 为什么需要单独抽函数

不是为了代码复用，而是为了：
- 时间来源统一
- 后续更容易切换成 timezone-aware datetime
- 测试里更容易 mock

如果将来要统一时区策略，这里是一个自然切入点。

---

## 4. `_emit_trace_write_error()`：为什么 trace 写失败不能把主流程打爆

源码位置：
- [`run_trace_service.py:59-75`](../app/services/run_trace_service.py#L59)

```python
emit_event(
    "errors",
    "run_trace.write_error",
    "Run trace bookkeeping failed",
    ...
)
```

### 这个函数的真实定位

它不是业务错误，而是“trace 账本自己写坏了”的错误上报器。

### 为什么必须存在

这个项目前面已经踩过一个坑：
- 主流程成功生成了下一问
- 但 run trace 写 step 时撞上 SQLite lock
- UI 看起来像失败，甚至把成功请求误伤成失败

所以现在的策略是：
- trace 是重要的
- 但 trace 不能反向打断主流程

`_emit_trace_write_error()` 就是这套 best-effort 策略的入口。

---

## 5. `create_run()`：一次 `/next` 请求如何变成一个 run

源码位置：
- [`run_trace_service.py:78-95`](../app/services/run_trace_service.py#L78)

```python
context = get_log_context()
db = SessionLocal()
...
run = AgentRun(
    project_id=project_id,
    turn_no=turn_no,
    request_id=context.get("request_id"),
    trace_id=context.get("trace_id"),
    status="running",
    started_at=utcnow(),
)
```

### 逐句含义

#### `get_log_context()`
- 从 logging contextvars 里拿当前请求上下文
- 把日志里的 `request_id / trace_id` 同步进 run trace

这一步特别关键，因为它把：
- logging
- run trace

串成了同一条链。

#### `SessionLocal()`
- 用新的数据库 session 单独写 run
- 不依赖主业务事务

#### `status="running"`
- run 创建出来时就是 running
- 前端之所以能立刻开始轮询 active run，就是因为这一步

#### `db.refresh(run)`
- 提交后重新加载 run，拿到数据库生成的 `id`

### 为什么 `create_run()` 要独立 commit

如果 run 不先落库：
- 前端没法马上轮询到它
- 后续 step 也没法引用它的 `run_id`

---

## 6. `finalize_run()`：run 结束时到底做了哪些聚合

源码位置：
- [`run_trace_service.py:98-116`](../app/services/run_trace_service.py#L98)

### 它更新的字段

- `status`
- `turn_no`
- `ended_at`
- `duration_ms`
- `total_llm_calls`
- `total_llm_tokens`
- `step_count`

### 逐个解释

#### `run.turn_no = turn_no if turn_no is not None else run.turn_no`
- 允许在 run 结束时补上最终关联 turn
- 因为某些时候 run 开始时还不知道最后会生成哪一轮

#### `duration_ms`
- 由 `ended_at - started_at` 算出
- 这是前端显示“本次生成耗时”的基础

#### `total_llm_calls`
- 通过统计 step 中 `step_key == "call_llm"` 且 `status == "completed"` 得到

#### `total_llm_tokens`
- 汇总所有 step 的 `total_tokens`

### 注意点

这里的 `sum(step.total_tokens for step in run.steps)` 假定：
- 非 LLM step 的 `total_tokens` 为 0 或 None-safe 数值

如果以后 step 模型默认值变了，这里要小心空值问题。

### 外层 `try/except`

如果 finalize 自己写失败：
- 只发 `run_trace.write_error`
- 不抛到主流程

这再次体现了 trace 的 best-effort 原则。

---

## 7. `StepSpan`：为什么需要这个 dataclass

源码位置：
- [`run_trace_service.py:119-140`](../app/services/run_trace_service.py#L119)

`StepSpan` 是 traced step 的可变句柄。

### 字段作用

- `run_id`
  - 属于哪个 run
- `step_id`
  - 对应数据库里的哪条 `AgentRunStep`
- `step_key`
  - 当前步骤类型
- `meta`
  - 额外结构化信息
- `next_step_hint`
  - 给前端的“接下来大概干什么”
- `description`
  - 当前步骤的更具体说明
- `usage`
  - prompt / completion / total token
- `started_at_monotonic`
  - 目前主要是保留字段，便于以后做更稳定的耗时测量

### 为什么不直接把这些参数都传给 `_finish_step()`

因为 step 的信息往往是在执行过程中逐步补齐的。

例如：
- 先创建 step
- 调完 LLM 后才知道 token usage
- 做完检索后才知道被选中的 branch

`StepSpan` 让这件事变得自然：
- `span.set_meta(...)`
- `span.set_usage(...)`
- `span.set_next_step_hint(...)`

---

## 8. `_start_step()`：一条 step 记录是怎么创建出来的

源码位置：
- [`run_trace_service.py:143-183`](../app/services/run_trace_service.py#L143)

### 关键流程

1. 根据 `step_key` 查 `STEP_DEFINITIONS`
2. 打开新 `SessionLocal()`
3. 查 run 是否存在
4. 用 `len(run.steps) + 1` 算 `step_index`
5. 写一条 `AgentRunStep`
6. commit + refresh
7. 返回 `StepSpan`

### 重点拆解

#### `definition = STEP_DEFINITIONS.get(step_key, {})`
- 如果没配置定义，也允许写 step
- label fallback 会用 `step_key.replace("_", " ").title()`

这是一种很实用的兜底设计。

#### `run = db.query(AgentRun).filter(AgentRun.id == run_id).first()`
- 确保 run 真的存在
- 否则直接抛 `ValueError`

#### `step_index = len(run.steps) + 1`
- 这个写法简单，但要知道它对高并发并不绝对安全
- 当前项目单 run 单链路执行，通常够用

### 什么时候可能需要改

如果未来同一个 run 里允许并行 step，这里就不够安全了。

---

## 9. `_finish_step()`：step 完成时哪些字段会被回填

源码位置：
- [`run_trace_service.py:186-207`](../app/services/run_trace_service.py#L186)

### 回填字段

- `status`
- `ended_at`
- `duration_ms`
- `next_step_hint`
- `description`
- token usage
- `meta_json`

### 逐段理解

#### `step.duration_ms = ...`
- 当前基于数据库中的 `started_at` 和新的 `ended_at` 差值
- 没用 `perf_counter()` 结果

#### `if span.usage:`
- 只有当业务代码显式调用了 `span.set_usage(...)` 才会落 token

#### `meta = dict(span.meta)`
- 先复制一份，避免副作用

#### `if error_message: meta["error_message"] = error_message`
- 失败 step 会把异常文本也塞进 meta

#### `step.meta_json = json.dumps(meta, ensure_ascii=True, sort_keys=True)`
- 这里和 coverage_state 一样，追求稳定的 JSON 输出

### 为什么 `_finish_step()` 本身不 catch 异常

因为它的上层 `traced_run_step()` 要决定：
- 失败时是记 write_error 还是 finalize_run failed

异常处理放在更高层才合理。

---

## 10. `traced_run_step()`：这是这个文件最值得你掌握的函数

源码位置：
- [`run_trace_service.py:210-265`](../app/services/run_trace_service.py#L210)

这是一个 `@contextmanager`，让业务代码可以这样写：

```python
with traced_run_step(..., step_key="call_llm") as span:
    ...
    span.set_usage(...)
    span.set_meta(...)
```

---

### 10.1 `run_id is None` 分支

```python
if run_id is None:
    yield None
    return
```

### 意义

允许业务代码无条件包 step，而不用每次都写：

```python
if run_id:
    ...
```

这是很实用的 API 设计。

---

### 10.2 `_start_step()` 失败时为什么不抛

源码位置：
- [`run_trace_service.py:224-241`](../app/services/run_trace_service.py#L224)

如果 start step 写失败：
- 记 `run_trace.write_error`
- `yield None`
- 主流程继续

### 这就是“trace 不能拖垮主流程”的最佳体现

如果这里直接抛异常，就会再次出现：
- 问题已经能生成
- 但因为 trace 写失败导致整次 `/next` 失败

---

### 10.3 业务逻辑抛异常时的处理

源码位置：
- [`run_trace_service.py:242-255`](../app/services/run_trace_service.py#L242)

```python
except Exception as exc:
    try:
        _finish_step(span, status="failed", error_message=str(exc))
    ...
    finalize_run(run_id=run_id, status="failed")
    raise
```

### 这段的逻辑顺序很对

1. 先尽量把当前 step 标成 failed
2. 再把整个 run 标成 failed
3. 最后把真正业务异常抛回去

### 为什么不能反过来

如果先抛业务异常：
- run/step 的失败状态可能来不及落库
- 前端就会卡在“running”

---

### 10.4 正常完成时为什么 `_finish_step()` 失败也不抛

源码位置：
- [`run_trace_service.py:256-265`](../app/services/run_trace_service.py#L256)

```python
try:
    _finish_step(span, status="completed")
except Exception as exc:
    _emit_trace_write_error(...)
```

### 这里是整个 best-effort 设计的核心

语义是：
- 主业务已经成功
- 现在只是 trace 补账失败
- 不能把成功请求重新打成失败

这是之前 run-trace 稳定性修复后的关键改动之一。

---

## 11. `serialize_run()`：前端真正消费的 contract 从这里出来

源码位置：
- [`run_trace_service.py:268-308`](../app/services/run_trace_service.py#L268)

### 它做了什么

把 SQLAlchemy 的 `AgentRun` 模型转成前端友好的 dict：

- run 级字段
- current step 摘要
- step 列表

### `current_step` 的选择规则

```python
current_step = next((step for step in reversed(run.steps) if step.status == "running"), None)
if current_step is None and run.steps:
    current_step = run.steps[-1]
```

这说明：
- 优先显示当前 still-running 的 step
- 如果没有 running，就显示最后一步

### 为什么这是对的

因为前端 active panel 最关心的是：
- 现在卡在哪里

如果 run 已结束，则最相关的信息是：
- 最后完成/失败的是哪一步

### `steps` 列表中每个字段

- `label`
  - 展示标题
- `status`
  - pending/running/completed/failed
- `description`
  - 更细解释
- `method`
  - 方法/工具级抽象
- `duration_ms`
  - 单步耗时
- `next_step_hint`
  - 下一步提示
- `prompt_tokens / completion_tokens / total_tokens`
  - token usage
- `meta`
  - 更细结构化信息

这就是 execution trace UI 的直接后端 contract。

---

## 12. 这个文件里几类最常见的改动切入点

### 场景 A：前端 trace 里步骤名字太技术化

改：
- `STEP_DEFINITIONS`

### 场景 B：想在某个步骤里多展示一点内部信息

改业务代码调用处：
- `span.set_meta(...)`
- `span.set_description(...)`
- `span.set_next_step_hint(...)`

而不是先改这里。

### 场景 C：成功生成了问题，但 trace 因写库失败把请求弄挂

优先检查：
- `traced_run_step()` 的 best-effort 路径
- `finalize_run()` 是否 catch 住异常
- 数据库 session 是否和主事务锁冲突

### 场景 D：run 一直停在 running

优先排查：
1. 业务异常时是否真的走到 `finalize_run(..., failed)`
2. 成功路径是否真的调用了 `finalize_run(..., completed)`
3. 前端 polling 是否在异常分支正常停止

---

## 13. 这个文件最值得继续增强的方向

### 方向 1：把 step 定义抽成 typed schema

现在 `STEP_DEFINITIONS` 是 dict，简单但不够强类型。

可升级成：
- `RunStepDefinition` dataclass / Pydantic model

### 方向 2：支持更丰富的 step meta 规范

现在 `meta` 是自由 dict。

可以考虑按 step 类型定义：
- retrieval meta
- llm meta
- persistence meta

这样前端渲染会更稳定。

### 方向 3：如果以后引入 SSE/WebSocket，这个文件基本不用重写

因为 run/step 模型已经够稳定了。

你要改的主要会是：
- API 推送方式
- 前端订阅逻辑

这说明当前设计的分层是合理的。

---

## 14. 一句话总结

`run_trace_service.py` 的价值不在“记录日志”，而在“把一次复杂 agent 运行整理成前端可查看、可轮询、可解释的 run timeline”。  
你后续想增强 execution trace 体验，先改这里定义的数据 contract，再改前端展示。
