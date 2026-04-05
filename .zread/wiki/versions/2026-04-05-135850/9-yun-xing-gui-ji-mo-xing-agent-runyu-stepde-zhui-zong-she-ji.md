在状态化访谈Agent系统中，可观测性是保障系统可靠性和调试能力的基石。运行轨迹（Run Trace）模型作为可观测性体系的核心组件，负责记录每一次Agent执行的生命周期——从Run的创建到每个Step的完整执行路径，为开发者提供了从宏观到微观的全链路可见性。该模型与[日志子系统：JSONL结构化日志设计](16-ri-zi-zi-xi-tong-jsonljie-gou-hua-ri-zhi-she-ji)共同构成系统的可观测性基础设施，前者侧重结构化执行路径追踪，后者侧重运行时事件记录。

## 核心数据模型：AgentRun与AgentRunStep

运行轨迹模型采用两级层级结构：**AgentRun** 代表一次完整的Agent执行周期（如一轮问题的生成过程），**AgentRunStep** 则是该执行周期内的原子操作单元。这种设计使得系统既能追踪宏观的执行概览，也能深入分析单个步骤的性能与行为。

### AgentRun：执行周期容器

AgentRun模型定义了一次Agent运行的核心元数据，包括项目关联、时序标识、状态管理与资源消耗统计：


```python
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_sessions.id"), nullable=False, index=True
    )
    turn_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_llm_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project = relationship("ProjectSession", back_populates="agent_runs")
    steps = relationship(
        "AgentRunStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunStep.step_index",
    )
```

Sources: [agent_run.py](app/models/agent_run.py#L1-L35)

其中 `project_id` 将Run绑定到特定的项目会话，`turn_no` 标识该Run对应的访谈轮次，`request_id` 和 `trace_id` 则用于关联外部的请求追踪系统。`status` 字段记录Run的最终状态（running/completed/failed），`duration_ms` 和token统计则为性能分析提供量化依据。`steps` 关系通过级联删除确保Run销毁时自动清理关联的Step记录。

### AgentRunStep：原子操作的细粒度记录

AgentRunStep模型记录Run内每个具体操作的执行细节，其设计目标是提供足够的信息来重现完整的执行路径：


```python
class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_sessions.id"), nullable=False, index=True
    )
    turn_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_step_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
```

Sources: [agent_run_step.py](app/models/agent_run_step.py#L1-L42)

**step_key** 是Step的核心标识符，对应预定义的步骤类型；**step_index** 则记录该Step在当前Run中的顺序位置，便于后续重放执行流程。`next_step_hint` 字段用于记录工作流的下一步提示，这在调试复杂的状态机行为时尤为有用。`meta_json` 字段以JSON格式存储步骤级别的扩展元数据（如prompt_id、模型版本、查询计数等），而token统计字段则为成本分析与性能优化提供数据支撑。

## 预定义步骤体系：STEP_DEFINITIONS

系统通过 `STEP_DEFINITIONS` 字典预定义了Agent执行过程中可能遇到的典型步骤类型，每个定义包含人类可读的标签和对应的方法描述：

```python
STEP_DEFINITIONS = {
    "load_project_context": {
        "label": "Load project context",
        "method": "database lookup",
    },
    "refresh_summaries": {
        "label": "Refresh summaries",
        "method": "summary maintenance",
    },
    "refresh_coverage": {
        "label": "Refresh coverage",
        "method": "rule-based coverage map",
    },
    "build_compact_context": {
        "label": "Build compact context",
        "method": "history compaction",
    },
    "retrieve_relevant_branches": {
        "label": "Retrieve relevant context",
        "method": "rule-based retrieval",
    },
    "render_prompt": {
        "label": "Render prompt",
        "method": "prompt asset renderer",
    },
    "call_llm": {
        "label": "Call model",
        "method": "OpenAI-compatible chat.completions",
    },
    "validate_question": {
        "label": "Validate question",
        "method": "rule-based validator",
    },
    "persist_result": {
        "label": "Persist result",
        "method": "database write",
    },
}
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L14-L42)

这些预定义步骤构成了标准执行路径的主体。实际使用中，代码还通过 `repo_manifest`、`repo_search`、`repo_read`、`repo_trace` 等步骤扩展名来追踪代码仓库 grounding 操作。

## 服务层架构：traced_run_step上下文管理器

Run Trace服务的核心是一个上下文管理器 `traced_run_step`，它以声明式的方式自动处理每个步骤的生命周期：

```python
@contextmanager
def traced_run_step(
    *,
    run_id: int | None,
    project_id: int,
    turn_no: int | None,
    step_key: str,
    description: str | None = None,
    next_step_hint: str | None = None,
) -> Iterator[StepSpan | None]:
    if run_id is None:
        yield None
        return

    try:
        span = _start_step(
            run_id=run_id,
            project_id=project_id,
            turn_no=turn_no,
            step_key=step_key,
            description=description,
            next_step_hint=next_step_hint,
        )
    except Exception as exc:
        _emit_trace_write_error(...)
        yield None
        return

    try:
        yield span
    except Exception as exc:
        try:
            _finish_step(span, status="failed", error_message=str(exc))
        except Exception as trace_exc:
            _emit_trace_write_error(...)
        finalize_run(run_id=run_id, status="failed")
        raise
    else:
        try:
            _finish_step(span, status="completed")
        except Exception as exc:
            _emit_trace_write_error(...)
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L212-L265)

该设计实现了三个关键能力：**自动生命周期管理**——进入上下文时创建Step记录，退出时自动更新状态；**异常传播与记录**——即使Step执行失败，也能捕获错误信息并写入 `meta_json`；**容错性保证**——即使追踪写入失败，也不影响主业务逻辑的执行（通过异常捕获确保 `yield span` 始终返回）。

### StepSpan：内存中的执行片段

`StepSpan` 是上下文管理器返回的内存对象，用于在执行过程中动态收集元数据：

```python
@dataclass
class StepSpan:
    run_id: int
    step_id: int
    step_key: str
    meta: dict[str, Any] = field(default_factory=dict)
    next_step_hint: str | None = None
    description: str | None = None
    usage: dict[str, int] | None = None
    started_at_monotonic: float = field(default_factory=perf_counter)

    def set_meta(self, **values: Any) -> None:
        self.meta.update(values)

    def set_usage(self, usage: dict[str, int] | None) -> None:
        self.usage = usage

    def set_next_step_hint(self, hint: str | None) -> None:
        self.next_step_hint = hint

    def set_description(self, description: str | None) -> None:
        self.description = description
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L99-L120)

开发者可以在Step执行过程中通过 `span.set_meta()` 追加任意键值对，通过 `span.set_usage()` 记录LLM调用产生的token消耗。这些数据会在Step完成时持久化到数据库。

## 实际使用模式：在LangGraph节点中集成追踪

在LangGraph工作流节点中，追踪功能的集成遵循统一模式——使用 `with` 语句包装关键操作。以下是问题生成节点的典型用法：

```python
# 在 interview_nodes.py 中的 refresh_summaries 步骤
with traced_run_step(
    run_id=run_id,
    project_id=project.id,
    turn_no=next_turn_no,
    step_key="refresh_summaries",
    description="Ensure older answered turns have compact summaries available.",
    next_step_hint="Build compact context",
) as summary_step:
    summarized_count = ensure_turn_summaries(
        db=db,
        project_id=project.id,
        system_prompt=project.system_prompt,
        turns_to_summarize=answered_turns,
    )
    if summary_step:
        summary_step.set_meta(summarized_count=summarized_count)
```

Sources: [interview_nodes.py](app/graphs/interview_nodes.py#L323-L344)

对于涉及LLM调用的步骤，系统会记录完整的使用量统计：

```python
with traced_run_step(
    run_id=run_id,
    project_id=project_id or 0,
    turn_no=next_turn_no,
    step_key="call_llm",
    description=f"Call {settings.openai_model} to draft the next question.",
    next_step_hint="Validate question",
) as llm_step:
    response = client.chat.completions.create(...)
    if llm_step:
        llm_step.set_meta(model=settings.openai_model, prompt_id=prompt.prompt_id)
    usage_metrics = extract_usage_metrics(response, ...)
    if llm_step:
        llm_step.set_usage(usage_metrics)
```

Sources: [question_generator.py](app/services/question_generator.py#L205-L234)

这种模式的优势在于：**声明式**——追踪逻辑与业务逻辑分离，代码清晰度不受影响；**资源感知**——自动捕获执行时长和token消耗；**错误可追溯**——异常时的错误信息被写入元数据，便于事后分析。

## API契约：Run Trace的数据序列化

前端和外部系统通过REST API获取Run和Step的完整信息。Schema层定义了严格的数据契约：

```python
class RunStepRead(BaseModel):
    id: int
    step_index: int
    step_key: str
    label: str
    status: str
    description: str | None
    method: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    next_step_hint: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    meta: dict[str, Any] = Field(default_factory=dict)


class RunRead(BaseModel):
    id: int
    project_id: int
    turn_no: int | None
    request_id: str | None
    trace_id: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    total_llm_tokens: int
    total_llm_calls: int
    step_count: int
    current_step_key: str | None = None
    current_step_label: str | None = None
    current_step_status: str | None = None
    steps: list[RunStepRead] = Field(default_factory=list)
```

Sources: [run_trace.py](app/schemas/run_trace.py#L1-L48)

值得注意的是，`RunRead` 包含三个可选字段 `current_step_key`、`current_step_label`、`current_step_status`，用于在前端实时展示当前正在执行的步骤，为用户提供进度反馈。序列化逻辑通过 `serialize_run` 函数实现，它会查找最近一个处于 "running" 状态的Step作为当前步骤：

```python
def serialize_run(run: AgentRun) -> dict[str, Any]:
    current_step = next(
        (step for step in reversed(run.steps) if step.status == "running"), 
        None
    )
    if current_step is None and run.steps:
        current_step = run.steps[-1]
    return {
        # ... other fields
        "current_step_key": current_step.step_key if current_step else None,
        "current_step_label": current_step.label if current_step else None,
        "current_step_status": current_step.status if current_step else None,
        "steps": [...],
    }
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L256-L292)

## API端点：运行轨迹的查询接口

系统为Run Trace提供了三个核心REST端点：

| 端点 | 方法 | 功能描述 |
|------|------|----------|
| `/projects/{project_id}/runs` | GET | 列出项目中所有Run，按时间倒序 |
| `/projects/{project_id}/runs/latest` | GET | 获取最近一次Run的完整信息 |
| `/projects/{project_id}/runs/{run_id}` | GET | 获取指定Run及其所有Step的详细信息 |

Sources: [projects.py](app/api/routes/projects.py#L667-L705)

每个端点都返回完整的 `RunRead` 对象，包含该Run下所有Step的嵌套数据。这种设计使得前端可以一次性加载完整的执行轨迹用于可视化展示。

## Run的创建与终结：生命周期管理

Run的创建发生在每次问题生成请求的处理入口处。在Projects API中，当用户提交回答后，系统会创建一个新的Run来追踪下一轮问题的生成过程：

```python
# projects.py 中 regenerate_turn 端点
run = create_run(project_id=project_id, turn_no=latest_turn.turn_no)
bind_log_context(run_id=run.id)

# 后续的节点执行会使用 run.id 作为 run_id 参数
generation_payload = generate_question_for_state(
    current_stage=...,
    db=db,
    project=project,
    run_id=run.id,  # 传递给追踪系统
    turn_no=latest_turn.turn_no,
    turns=turns,
)
```

Sources: [projects.py](app/api/routes/projects.py#L334-L365)

Run的终结通过 `finalize_run` 函数完成，它会计算总执行时长、统计LLM调用次数和token消耗总量，并更新最终状态：

```python
def finalize_run(*, run_id: int, status: str, turn_no: int | None = None) -> None:
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        return
    run.status = status
    run.ended_at = utcnow()
    run.duration_ms = max(0, int((run.ended_at - run.started_at).total_seconds() * 1000))
    run.total_llm_calls = sum(
        1 for step in run.steps 
        if step.step_key == "call_llm" and step.status == "completed"
    )
    run.total_llm_tokens = sum(step.total_tokens for step in run.steps)
    run.step_count = len(run.steps)
    db.commit()
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L76-L96)

## 与其他可观测性组件的协作

运行轨迹模型并非孤立存在，它与日志子系统、事件追踪服务共同构成完整的可观测性体系。在 `run_trace_service.py` 中，每当追踪写入失败时，系统会通过 `emit_event` 将错误记录到JSONL日志：

```python
def _emit_trace_write_error(*, operation: str, exc: Exception, ...):
    emit_event(
        "errors",
        "run_trace.write_error",
        "Run trace bookkeeping failed",
        level=40,
        operation=operation,
        run_id=run_id,
        step_key=step_key,
        exc_info=exc,
    )
```

Sources: [run_trace_service.py](app/services/run_trace_service.py#L51-L68)

这种设计确保了追踪系统本身的故障也不会导致主业务中断，同时留下足够的诊断线索。关于日志子系统的详细设计，可参见 [日志子系统：JSONL结构化日志设计](16-ri-zi-zi-xi-tong-jsonljie-gou-hua-ri-zhi-she-ji)；关于API层的数据契约，可参见 [执行轨迹API：Run Trace的前后端契约](17-zhi-xing-gui-ji-api-run-tracede-qian-hou-duan-qi-yue)。

## 架构演进思考

当前模型在以下方面表现出良好的扩展性：**元数据字段**——通过 `meta_json` 支持任意扩展，无需修改表结构；**步骤类型**——通过 `STEP_DEFINITIONS` 字典可灵活添加新的步骤定义；**聚合分析**——通过 `ProjectRunSummary` Schema支持项目级别的运行统计。

对于需要更深入分析的场景，可考虑在 `AgentRunStep` 中增加**父子步骤嵌套**支持（用于追踪包含子操作复合步骤），或在 `AgentRun` 中增加**分支与版本**信息（用于A/B测试场景）。