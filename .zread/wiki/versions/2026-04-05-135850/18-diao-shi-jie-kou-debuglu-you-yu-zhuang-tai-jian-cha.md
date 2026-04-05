在开发与维护状态化访谈Agent的过程中，开发者经常需要了解系统的内部运行状态——当前处于哪个阶段、Agent模式是什么、任务看板进度如何、覆盖度状态是否正确等。这些信息对于定位问题、验证工作流逻辑、以及理解Agent决策过程至关重要。本项目提供了一套完整的调试接口，专门用于状态检查与运行时诊断。

## 调试接口架构概览

本项目的调试接口采用RESTful风格，统一挂载在 `/debug` 路由下。通过FastAPI的依赖注入机制，这些接口可以直接访问数据库会话和核心服务层，返回结构化的诊断信息。需要注意的是，这些接口主要面向后端开发者调试使用，在生产环境中可根据需要添加额外的认证或访问控制。

调试接口的路由定义位于 `app/api/routes/debug.py`，该模块导出了四个核心端点，分别用于LLM连接测试、项目覆盖度检查、完整状态诊断，以及下一轮上下文的预览。路由通过 `app/main.py` 中的 `app.include_router(debug_router)` 语句注册到FastAPI应用。

Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L1-L25)
Sources: [app/main.py](app/main.py#L77-L78)

### 调试接口端点总览

| 端点路径 | HTTP方法 | 功能描述 | 适用场景 |
|---------|---------|---------|---------|
| `/debug/llm` | GET | 测试LLM连接是否正常 | 验证API密钥配置、排查LLM调用失败 |
| `/debug/projects/{project_id}/coverage` | GET | 获取项目覆盖度状态快照 | 检查分支追踪完整性、验证主题覆盖 |
| `/debug/projects/{project_id}/state` | GET | 获取完整运行时状态诊断 | 深度调试模式转换、任务看板、阶段决策 |
| `/debug/projects/{project_id}/next-context` | POST | 预览下一轮生成上下文 | 预测性问题测试、上下文工程验证 |

Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L27-L220)

## 端点详解

### 1. LLM连接测试：GET /debug/llm

这是最简单的调试端点，用于验证LLM服务是否可以正常连接。当开发者配置完OpenAI API密钥后，可以通过调用此接口快速确认配置是否生效。

该端点调用 `app/services/llm_test.py` 中的 `test_llm_call()` 函数，向LLM发送一条简单的测试消息 "Hello"，并返回响应结果。如果连接成功，返回包含模型名称、API基础URL和生成内容的响应；如果失败，则返回错误类型和详细信息。

```json
// 成功响应示例
{
  "ok": true,
  "model": "gpt-4",
  "base_url": "https://api.openai.com/v1",
  "content": "Hello! How can I help you today?"
}

// 失败响应示例
{
  "ok": false,
  "error_type": "AuthenticationError",
  "message": "Incorrect API key provided",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4"
}
```

这个端点在首次部署或更换LLM服务时特别有用，可以快速定位是配置问题还是代码逻辑问题。

Sources: [app/services/llm_test.py](app/services/llm_test.py#L1-L43)

### 2. 覆盖度状态检查：GET /debug/projects/{project_id}/coverage

覆盖度（Coverage）是本项目的核心概念之一，用于追踪访谈过程中已覆盖的代码分支和主题。此端点返回指定项目的完整覆盖度状态数据，包括所有分支的详细信息、问题历史、以及框架配置。

响应数据结构定义在 `app/schemas/debug.py` 的 `CoverageDebugResponse` 模型中，包含以下核心字段：

- `version`: 覆盖度状态版本号
- `branch_count`: 已追踪的分支数量
- `updated_through_turn_no`: 最新更新的轮次编号
- `branches`: 分支详情数组，每个分支包含标识、标签、阶段、状态、优先级、关键词、证据轮次ID、未解决点等信息
- `question_history`: 问题历史记录，用于追踪已生成的问题
- `framework`: 框架配置信息

此端点对于验证覆盖度追踪逻辑、检查是否存在重复问题、以及分析访谈进度非常有用。开发者可以通过对比不同轮次返回的覆盖度状态，观察系统的学习过程。

Sources: [app/schemas/debug.py](app/schemas/debug.py#L78-L128)
Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L29-L37)

### 3. 完整状态诊断：GET /debug/projects/{project_id}/state

这是功能最全面的调试端点，返回项目当前完整的运行时诊断信息。该端点聚合了多个子系统的状态数据，提供一站式的状态检查能力。

响应数据结构定义在 `DebugInfoResponse` 模型中，包含以下六个主要部分：

**（1）question_plan（问题规划状态）**

返回当前问题生成的相关决策信息，包括：

- `mode`: 当前Agent模式（understand_current_code / review_current_code / propose_changes）
- `phase`: 当前阶段名称
- `rubric_task_id` 和 `rubric_task_label`: 当前处理的评分任务ID和标签
- `target_branch_ids`: 目标分支ID列表
- `confidence_score`: 规划置信度评分
- `human_gate_triggered`: 是否触发了人工介入门槛
- `why_this_question`: 解释为什么选择当前问题的推理文本
- `planning_steps`: 问题规划所执行的步骤序列
- `drift_detected`: 是否检测到话题漂移
- `human_review_applied`: 是否应用了人工评审意见

这些信息完整地记录了问题生成的全过程决策，对于理解为何Agent提出了某个特定问题至关重要。

**（2）task_board（任务看板状态）**

返回评分任务看板的当前状态，包括：

- `current_phase`: 当前阶段名称
- `phase_status`: 各阶段状态映射
- `incomplete_tasks`: 未完成的任务列表（最多返回10个）
- `next_priority_task`: 下一个优先处理的任务
- `human_gate_pending`: 是否存在待处理的人工介入请求

**（3）mode（模式状态）**

返回Agent模式的详细信息：

- `current_mode`: 当前模式
- `mode_constraints`: 当前模式的约束配置
- `can_propose_changes`: 是否允许提出代码修改建议
- `valid_transitions`: 可以转换到的有效目标模式列表

模式转换遵循单向流程：`understand_current_code → review_current_code → propose_changes`，此端点可以验证模式转换逻辑是否正确。

Sources: [app/services/mode__service.py](app/services/mode_service.py#L1-L100)

**（4）scenario（场景状态）**

返回场景完成度信息：

- `is_complete`: 访谈场景是否已完成
- `confidence`: 完成置信度
- `scenario_count`: 场景数量
- `missing_aspects`: 缺失的方面列表
- `follow_up_questions`: 待提出的跟进问题

**（5）coverage_summary（覆盖度摘要）**

返回覆盖度统计信息：

- `branch_count`: 分支总数
- `updated_through_turn_no`: 最新更新的轮次编号

**（6）recent_events（最近事件日志）**

返回最近10条事件日志，用于追踪系统运行过程中的关键事件。

Sources: [app/schemas/debug.py](app/schemas/debug.py#L1-L76)
Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L39-L95)

### 4. 上下文预览：POST /debug/projects/{project_id}/next-context

这是一个预测性调试端点，允许开发者模拟输入一个答案，然后预览系统将如何生成下一轮问题和上下文。这是一个强大的调试工具，可以在不实际运行访谈的情况下验证系统行为。

**请求参数（ContextPreviewRequest）**

- `answer_text`（必填）: 模拟的用户回答文本
- `human_review`（可选）: 人工评审输入，包含评审意见和问题修改建议

**响应参数（ContextPreviewResponse）**

该端点返回一个完整的"下一轮预览"数据包，包含：

- `current_stage`: 当前阶段名称
- `next_turn_no`: 下一轮编号
- `stage_objective`: 当前阶段目标
- `framework_gaps`: 框架差距列表
- `recent_context`: 最近上下文（经过记忆压缩处理）
- `retrieved_context`: 检索到的相关上下文
- `coverage_priorities`: 覆盖度优先级
- `selected_turn_ids`: 选定的轮次ID（用于构建上下文）
- `selected_branch_ids`: 选定的分支ID
- `branch_selection_元数据`: 分支选择元信息
- `question_history`: 问题历史
- `stage_decision`: 阶段决策结果
- `planner_决策`: 问题规划器决策结果
- `validation_预览`: 问题校验器预览结果
- `prompt_id`: 使用的Prompt模板ID
- `prompt_version`: Prompt模板版本
- `prompt_messages`: 完整的Prompt消息数组

通过这个端点，开发者可以：

1. 预测特定答案将如何影响下一轮的问题生成
2. 验证上下文工程模块的检索效果
3. 检查问题规划器的决策逻辑
4. 查看最终生成的Prompt完整内容

Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L97-L229)

## 调试接口使用示例

### 通过cURL调用调试接口

**测试LLM连接：**

```bash
curl http://localhost:8000/debug/llm
```

**检查项目覆盖度状态：**

```bash
curl http://localhost:8000/debug/projects/1/coverage
```

**获取完整状态诊断：**

```bash
curl http://localhost:8000/debug/projects/1/state
```

**预览下一轮上下文：**

```bash
curl -X POST http://localhost:8000/debug/projects/1/next-context \
  -H "Content-Type: application/json" \
  -d '{
    "answer_text": "这个函数的主要目的是处理用户认证流程。"
  }'
```

### 在Python中调用调试接口

```python
import requests

BASE_URL = "http://localhost:8000"

# 测试LLM连接
def test_llm():
    response = requests.get(f"{BASE_URL}/debug/llm")
    return response.json()

# 获取项目状态
def get_project_state(project_id: int):
    response = requests.get(f"{BASE_URL}/debug/projects/{project_id}/state")
    return response.json()

# 预览下一轮
def preview_next_context(project_id: int, answer_text: str):
    response = requests.post(
        f"{BASE_URL}/debug/projects/{project_id}/next-context",
        json={"answer_text": answer_text}
    )
    return response.json()
```

## 调试工作流建议

在实际开发中，建议按照以下顺序使用调试接口：

**第一步：基础连通性检查**

首先调用 `/debug/llm` 确认LLM服务配置正确，这是所有上层功能的前提。

**第二步：状态快速扫描**

使用 `/debug/projects/{id}/state` 获取项目状态的全局视图，这可以帮助快速定位问题所在的子系统（模式？任务看板？覆盖度？）。

**第三步：专项深入分析**

根据第二步的发现，选择专项接口进行深入分析：

- 覆盖度异常 → `/debug/projects/{id}/coverage`
- 上下文构建疑问 → `/debug/projects/{id}/next-context`（带模拟答案）

**第四步：Prompt级别调试**

当需要查看最终发送给LLM的Prompt完整内容时，使用 `/debug/projects/{id}/next-context` 并检查返回的 `prompt_messages` 字段。

Sources: [app/api/routes/debug.py](app/api/routes/debug.py#L1-L229)

## 与其他模块的调试关联

调试接口并非孤立存在，它依赖于多个核心服务模块提供状态数据。理解这些依赖关系有助于更好地使用调试接口：

**与模式服务的关联**：调试接口中的mode状态部分直接调用 `app/services/mode_service.py` 中的 `get_mode_constraints()`、`can_mode_propose_changes()` 和 `validate_mode_transition()` 函数。这些函数定义了三种Agent模式的约束规则和转换条件。

Sources: [app/services/mode_service.py](app/services/mode_service.py#L100-L160)

**与覆盖度服务的关联**：覆盖度相关的调试功能依赖 `app/services/coverage_ervice.py` 中的 `rebuild_coverage_state()` 和 `save_coverage_state()` 函数。前者根据历史轮次重建覆盖度状态，后者负责将状态持久化到数据库。

Sources: [app/services/coverage_service.py](app/services/coverage_service.py#L164-L200)

**与阶段管理服务的关联**：上下文预览端点调用 `app/services/stage_manager.py` 中的 `decide_next_stage()` 函数来决策下一阶段，该决策基于覆盖度状态、当前阶段、最大轮次数和人工评审信号。

---

## 下一步学习建议

完成本页面学习后，建议继续深入以下主题：

- **状态管理机制**：了解 [InterviewGraphState设计与持久化](7-zhuang-tai-guan-li-interviewgraphstateshe-ji-yu-chi-jiu-hua)，深入理解状态如何在LangGraph工作流中传递
- **执行轨迹追踪**：学习 [执行轨迹API：Run Trace的前后端契约](17-zhi-xing-gui-ji-api-run-tracede-qian-hou-duan-qi-yue)，掌握运行时追踪的完整方案
- **日志子系统**：阅读 [日志子系统：JSONL结构化日志设计](16-ri-zi-zi-xi-tong-jsonljie-gou-hua-ri-zhi-she-ji)，了解可观测性基础设施

这些文档将帮助你建立对系统调试与可观测性的完整认知。