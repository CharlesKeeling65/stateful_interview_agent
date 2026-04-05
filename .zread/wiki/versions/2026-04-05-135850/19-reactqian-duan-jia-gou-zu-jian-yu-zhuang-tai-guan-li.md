本页面详细阐述状态化访谈Agent的前端架构设计，涵盖技术栈选型、核心状态管理模式、组件层次结构以及前后端数据契约。该架构采用**自定义Hook集中式状态管理**模式，配合**严格类型化的TypeScript接口**和**Tailwind CSS现代样式方案**，实现了简洁高效的React应用构建。

## 技术栈概览

前端项目基于现代React生态构建，采用轻量级依赖策略。核心依赖包括React 19作为UI框架、Vite 8作为构建工具、TypeScript提供静态类型检查、Tailwind CSS 4处理样式系统，以及Vitest用于单元测试。这种选型在保持功能完整性的同时，最大程度控制了依赖体积和构建复杂度。Sources: [package.json](frontend/package.json#L1-L38)

| 层级 | 技术选型 | 版本 | 职责说明 |
|------|----------|------|----------|
| UI框架 | React | 19.2.4 | 组件化用户界面 |
| 构建工具 | Vite | 8.0.1 | 开发服务器与生产构建 |
| 类型系统 | TypeScript | 5.9.3 | 静态类型检查与IDE支持 |
| 样式方案 | Tailwind CSS | 4.1.15 | 原子化CSS类名 |
| 测试框架 | Vitest | 4.1.2 | 单元与集成测试 |
| 国际化 | 自实现 | — | 中英文双语切换 |

## 架构设计原则

### 状态管理模式

该前端采用**自定义Hook集中管理**模式，而非引入Redux或Zustand等外部状态库。核心状态管理逻辑封装在 `useProject` Hook中，该Hook位于 `frontend/src/hooks/hook.ts`，集中管理项目、会话、轮次、执行轨迹等所有前端状态。这种设计的核心理念是：状态与状态操作应同源，避免跨文件的状态分发复杂性。Sources: [useProject.ts](frontend/src/hooks/hook.ts#L56-L512)

```
App.tsx
  └── useProject() — 全局状态容器
        ├── projects[] — 项目列表
        ├── project — 当前选中项目
        ├── turns[] — 访谈轮次历史
        ├── status — 项目实时状态
        ├── transcript — 完整对话记录
        └── runs[] — 执行轨迹历史
```

### 前后端数据契约

前端通过 `api/hook.ts` 中的专用函数与后端通信。所有API调用遵循统一的错误处理模式和响应解析逻辑。接口设计采用RESTful风格，路径参数直接嵌入URL，查询参数通过可选payload传递。每个API函数都声明了精确的返回类型，与TypeScript类型定义形成完整契约。Sources: [client.ts](frontend/src/api/hook.ts#L1-L123)

| API端点 | 方法 | 功能说明 | 返回类型 |
|---------|------|----------|----------|
| `/projects` | GET | 列出所有项目 | ProjectRead[] |
| `/projects` | POST | 创建新项目 | ProjectRead |
| `/:id/start` | POST | 启动访谈 | ProjectStartResponse |
| `/:id/answer` | POST | 提交回答 | AnswerSubmitResponse |
| `/:id/next` | POST | 生成下一问题 | ProjectNextResponse |
| `/:id/turns/:turnId/regenerate-question` | POST | 重写当前问题 | CurrentQuestionRegenerateResponse |
| `/:id/status` | GET | 获取项目状态 | ProjectStatusResponse |
| `/:id/transcript` | GET | 获取完整对话 | TranscriptResponse |
| `/:id/runs` | GET | 获取执行轨迹 | RunRead[] |

## 核心状态管理：`useProject` Hook

`useProject` Hook是整个前端状态管理的核心枢纽，它封装了项目列表、当前项目、会话轮次、实时状态、对话记录、执行轨迹等全部状态，以及创建项目、选择项目、保存回答、生成问题、重写问题、更新项目、删除项目等核心业务操作。状态更新采用React的 `startTransition` API，确保大规模状态更新时UI仍保持响应。Sources: [useProject.ts](frontend/src/hooks/hook.ts#L56-L90)

### 状态定义

```typescript
// 核心状态声明
const [projects, setProjects] = useState<ProjectRead[]>([])
const [project, setProject] = useState<ProjectRead | null>(null)
const [turns, setTurns] = useState<TurnRead[]>([])
const [status, setStatus] = useState<ProjectStatusResponse | null>(null)
const [transcript, setTranscript] = useState<TranscriptResponse |null>(null)
const [runs, setRuns] = useState<RunRead[]>([])
const [activeRun, setActiveRun] = useState<RunRead | null>(null)
const [loading, setLoading] = useState(false)
const [busyAction, setBusyAction] = useState<BusyAction>(null)
const [error, setError] = useState('')
const [lastMessageKey, setLastMessageKey] = useState('')
```

### 忙碌状态管理

`busyAction` 状态用于追踪当前正在进行的异步操作，并在UI中向用户展示进度反馈。该状态设计为联合类型，包含初始化、选择、创建、启动、保存回答、生成下一问题、重写问题、更新、删除等九种操作状态。这种设计使UI层能够精确判断何时禁用交互元素、何时显示加载动画、何时展示操作提示。Sources: [useProject.ts](frontend/src/hooks/hook.ts#L39-L55)

```typescript
export type BusyAction =
  | 'initializing'
  | 'selecting'
  | 'creating'
  | 'starting'
  | 'saving_answer'
  | 'generating_next'
  | 'regenerating'
  | 'updating'
  | 'deleting'
  | null
```

### 轮询机制

在生成下一问题和重写当前问题的流程中，前端实现了主动轮询机制以追踪后端执行轨迹。通过 `getLatestProjectRun` 接口每700毫秒查询一次最新运行状态，直到后端返回最终结果或运行状态为非running。该机制确保了长时间运行的LLM任务能够在UI中得到实时反馈。Sources: [useProject.ts](frontend/src/hooks/hook.ts#L244-L292)

## 数据类型体系

前端定义了完整的TypeScript类型体系，与后端SQLAlchemy模型一一对应。类型定义位于 `types/hook.ts`，涵盖项目、会话、轮次、执行轨迹、Token使用量等核心实体。这些类型既用于API响应反序列化，也用于组件props类型声明，形成了前后端数据流动的完整类型安全链。Sources: [api.ts](frontend/src/types/hook.ts#L1-L332)

### 核心数据类型

| 类型名 | 定义位置 | 用途 |
|--------|----------|------|
| ProjectRead | api.ts L145-L166 | 项目基础信息与配置 |
| TurnRead | api.ts L204-L232 | 单轮访谈记录 |
| RunRead | api.ts L130-L148 | Agent执行轨迹 |
| RunStepRead | api.ts L112-L128 | 执行步骤详情 |
| ProjectStatusResponse | api.ts L244-L268 | 项目实时状态 |
| TranscriptResponse | api.ts L270-L276 | 格式化对话文本 |
| HumanReviewInput | api.ts L36-L44 | 人工评审信号 |
| QuestionPlanRead | api.ts L46-L82 | 问题生成规划 |

## 组件架构

### 组件目录结构

```
frontend/src/components/
├── ActionButton.hook.ts         # 通用操作按钮
├── AnswerComposer.hook.ts       # 回答输入组件
├── ConfirmDeleteDialog.hook.tsx # 删除确认弹窗
├── CreateProjectForm.hook.tsx   # 项目创建表单
├── ExecutionTraceSection.hook.tsx # 执行轨迹展示
├── GenerationControlPanel.hook.tsx # 生成控制面板
├── Icons.hook.tsx               # SVG图标组件
├── ProjectMetadataEditor.hook.tsx # 项目元数据编辑器
├── ProjectSidebar.hook.tsx      # 项目侧边栏
├── ProjectStatusBadge.hook.tsx  # 项目状态徽章
├── RegenerationFeedbackBanner.hook.tsx # 重写反馈横幅
├── StatsDashboard.hook.tsx      # 统计仪表盘
├── StatusPanel.hook.tsx         # 状态面板
├── TokenUsagePanel.hook.tsx     # Token使用面板
├── TranscriptPagination.hook.tsx # 访谈记录分页
├── TranscriptPanel.hook.tsx     # 访谈记录面板
├── TurnCard.hook.tsx            # 单轮记录卡片
└── pretext/                     # 前文本动画组件
```

### 组件设计模式

组件采用**Props向下传递、事件向上冒泡**的标准React模式。每个组件都声明了精确的Props类型接口，组件内部不管理业务状态，仅处理UI交互逻辑。这种设计使得组件高度可复用，业务逻辑完全由 `useProject` Hook统一处理。以 `ProjectSidebar` 为例，它仅接收项目列表、选中状态、回调函数等props，不包含任何业务状态或API调用逻辑。Sources: [ProjectSidebar.tsx](frontend/src/components/hook.tsx#L1-L147)

### 主应用组件：`App.tsx`

`App.tsx` 是前端应用的入口组件，它调用 `useProject` Hook获取所有状态和操作函数，然后将这些数据以props形式传递给子组件。`App.tsx` 本身不执行业务逻辑，仅负责UI布局、页面切换（工作区/分析区）、国际化语言切换等全局状态管理。这种分层设计确保了业务逻辑与视图逻辑的清晰分离。Sources: [App.tsx](frontend/src/App.hook.ts#L1-L363)

```typescript
function App() {
  const {
    busyAction,
    project,
    projects,
    turns,
    status,
    transcript,
    runs,
    activeRun,
    // ... 全部状态和操作函数
  } = useProject()
  
  // UI布局与组件组装
  return (
    <div className="app-container">
      <ProjectSidebar {...sidebarProps} />
      <div className="workspace">
        <AnswerComposer {...composerProps} />
        <GenerationControlPanel {...controlProps} />
        <TranscriptPanel {...transcriptProps} />
      </div>
    </div>
  )
}
```

## 国际化方案

国际化采用自实现的轻量级方案，基于扁平键值对的翻译字典实现中英文切换。`i18n.ts` 文件定义了 `Locale` 类型、翻译字典对象和 `createTranslator` 工厂函数。所有UI文本均通过翻译函数 `t(key)` 获取，key采用点号分隔的层级命名（如 `app.title`、`sidebar.createProject`），与组件解耦。语言偏好存储在浏览器localStorage中，页面加载时自动恢复。Sources: [i18n.ts](frontend/src/i18n.ts#L1-L200)

```typescript
export type Locale = 'en' | 'zh-CN'

const translations = {
  en: { 'app.title': 'Stateful Interview Agent', ... },
  'zh-CN': { 'app.title': '状态化访谈Agent', ... }
}

export function createTranslator(locale: Locale) {
  return function t(key: string): string {
    return translations[locale][key] ?? key
  }
}
```

## 样式系统

前端样式基于Tailwind CSS 4构建，采用原子化类名策略。所有样式类名直接编写在JSX中，无需额外的CSS文件或样式模块。这种设计减少了样式与组件的分离，减少了维护成本。组件使用响应式设计断点（如 `sm:`、`lg:`、`xl:`）适配不同屏幕尺寸，色彩系统基于Tailwind的slate、amber、white等调色板，并通过透明度修饰符（如 `bg-white/80`）实现层次感。Sources: [App.tsx](frontend/src/App.hook.ts#L90-L150)

### 典型样式模式

```typescript
// 响应式容器
<div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">

// 背景层次
<div className="bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_28%)]">

// 玻璃拟态效果
<div className="bg-white/80 backdrop-blur border border-white/60">

// 阴影系统
<div className="shadow-[0_20px_50px_rgba(148,163,184,0.16)]">
```

## 页面流转与状态联动

前端页面流转围绕项目生命周期设计。用户创建项目后通过 `startProject` 启动访谈，此时后端生成第一个问题并返回第一轮记录。用户在 `AnswerComposer` 中填写回答并保存，然后通过 `GenerationControlPanel` 提交以生成下一问题。整个过程中，`StatusPanel` 实时显示项目状态、执行轨迹和对话记录。页面左侧的 `ProjectSidebar` 始终显示项目列表，支持快速切换。Sources: [App.tsx](frontend/src/App.hook.ts#L220-L310)

```
创建项目 → 启动访谈 → 生成问题 → 保存回答 → 生成下一问题
    ↓           ↓           ↓          ↓            ↓
ProjectSidebar   TurnCard    TurnCard  AnswerComposer  GenerationControlPanel
               展示问题    展示问题    收集回答       触发下一轮
```

## 相关文档

- [环境配置：.env变量与API密钥设置](20-huan-jing-pei-zhi-envbian-liang-yu-apimi-yao-she-zhi) — 了解前端如何配置后端API地址
- [双语支持：i18n国际化实现](21-shuang-yu-zhi-chi-i18nguo-ji-hua-shi-xian) — 深入理解国际化实现细节
- [后端架构概览：FastAPI + SQLAlchemy + LangGraph](5-hou-duan-jia-gou-gai-lan-fastapi-sqlalchemy-langgraph) — 了解后端技术选型
- [执行轨迹API：Run Trace的前后端契约](17-zhi-xing-gui-ji-api-run-tracede-qian-hou-duan-qi-yue) — 理解执行轨迹的数据结构