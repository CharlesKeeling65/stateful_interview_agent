export type Locale = 'en' | 'zh-CN'

export const LOCALE_STORAGE_KEY = 'stateful-interview-agent:locale'

const translations = {
  en: {
    'app.title': 'Stateful Interview Agent',
    'app.subtitle': 'Readable orchestration workspace for long-form project interviews.',
    'app.language': 'Language',
    'app.activeSession': 'Active session',
    'app.noSelection': 'No project selected',
    'app.turns': 'Turns',
    'app.stage': 'Stage',
    'app.runtime': 'Runtime',
    'app.interviewFlow': 'Interview flow',
    'app.interviewFlowHint': 'Read the current state first, act in the composer, then inspect turn history only when needed.',
    'nav.workspace': 'Workspace',
    'nav.analytics': 'Analytics',
    'status.start': 'Start interview',
    'status.snapshot': 'Runtime snapshot',
    'status.sessionHealth': 'Session health',
    'status.export': 'Transcript export',
    'status.copyTranscript': 'Copy transcript',
    'status.exportTxt': 'Export .txt',
    'status.exportMd': 'Export .md',
    'status.error': 'Error',
    'status.info': 'Latest update',
    'status.started': 'Interview started. The first question is ready.',
    'status.created': 'Project created. Start the interview to generate the first question.',
    'status.updated': 'Project metadata updated.',
    'status.deleted': 'Project deleted.',
    'status.generating': 'Generating the next question...',
    'status.regeneratingCurrent': 'Regenerating the current question...',
    'status.generated': 'Answer submitted. The next question is ready.',
    'status.finished': 'Interview finished. Maximum turn limit reached.',
    'status.regeneratedCurrent': 'Current question regenerated successfully.',
    'status.projectStatus': 'Project status',
    'status.projectId': 'Project ID',
    'status.currentStage': 'Current stage',
    'status.runs': 'Runs',
    'status.totalGeneration': 'Total generation',
    'status.averageRun': 'Average run',
    'status.minimumGoal': 'Minimum goal',
    'status.latestAnswered': 'Latest answered',
    'status.noProject': 'No active project. Pick one from the left column or create a new session.',
    'status.exportHint': 'Copy the full transcript or export it as plain text or Markdown. The body stays hidden here so this rail remains easy to scan.',
    'status.exportReady': 'Exports are generated client-side from the latest backend transcript.',
    'status.exportLocked': 'Transcript actions unlock after the interview has generated at least one turn.',
    'status.reached': 'Reached',
    'status.notYet': 'Not yet',
    'status.waiting': 'Waiting',
    'status.noTurns': 'No turns yet',
    'composer.submit': 'Submit answer and generate next question',
    'composer.title': 'Paste the latest answer and move the interview forward.',
    'composer.section': 'Answer composer',
    'composer.placeholder.ready': 'Paste the latest opencode answer here...',
    'composer.placeholder.notStarted': 'Start the interview to receive the first question.',
    'composer.placeholder.finished': 'This interview is finished.',
    'composer.review': 'Human review signal',
    'composer.reviewHint': 'Optional. Use this to steer the next question when the answer is incomplete, drifted, or ready to close a phase.',
    'composer.verdict': 'Verdict',
    'composer.direction': 'Direction',
    'composer.focus': 'Preferred next focus',
    'composer.phaseReady': 'Mark the current phase as sufficiently complete',
    'composer.note': 'Human note',
    'composer.noteHint': 'Optional note: what is still unclear, where the interview drifted, or which branch matters most.',
    'composer.noExplicitReview': 'No explicit review',
    'composer.noExplicitFocus': 'No explicit focus',
    'composer.estimate': 'Estimated next call',
    'composer.answerInput': 'Answer input',
    'composer.nextPrompt': 'Next prompt',
    'composer.nextOutput': 'Next output',
    'composer.estimateHint': 'Estimate only. Actual usage comes from the backend after generation.',
    'composer.finishedHint': 'No more turns can be submitted after the session finishes.',
    'composer.lockedHint': 'The composer unlocks after the first question is generated.',
    'composer.readyHint': 'Long answers remain intact. Add optional human guidance only when you want to redirect or close the current investigation thread.',
    'sidebar.recentSessions': 'Recent sessions',
    'sidebar.title': 'Local orchestration console for project interview sessions.',
    'sidebar.copy': 'Create a project, start the interview, paste each answer, and keep the thread durable turn by turn.',
    'sidebar.newProject': 'New project',
    'sidebar.seedSession': 'Seed a local interview session',
    'sidebar.projectName': 'Project name',
    'sidebar.systemPrompt': 'System prompt',
    'sidebar.createProject': 'Create project',
    'sidebar.quickDemo': 'Quick demo',
    'sidebar.pleaseWait': 'Please wait...',
    'sidebar.projectList': 'Project list',
    'sidebar.empty': 'No project yet. Create one from the panel above.',
    'sidebar.createdAt': 'Created',
    'sidebar.updatedAt': 'Updated',
    'sidebar.totalTokens': 'Total tokens',
    'sidebar.selectProject': 'Select project',
    'sidebar.rename': 'Rename',
    'sidebar.save': 'Save',
    'sidebar.cancel': 'Cancel',
    'sidebar.delete': 'Delete',
    'sidebar.editProjectTitle': 'Edit project title',
    'sidebar.demoPlaceholder': 'Stateful Interview Demo',
    'sidebar.currentStage': 'Current stage',
    'sidebar.turnsSuffix': 'turns',
    'transcript.emptyEyebrow': 'Transcript',
    'transcript.emptyTitle': 'Select a project to inspect its interview thread.',
    'transcript.emptyCopy': 'Once the interview starts, each generated question and pasted answer will accumulate here in chronological order.',
    'transcript.active': 'Active transcript',
    'transcript.readingTitle': 'Readable turn history',
    'transcript.readingCopy': 'Questions, answers, review signals, and orchestration rationale are grouped together so you can scan context before diving into raw details.',
    'transcript.stageSummary': 'Current stage',
    'transcript.copyLatest': 'Copy latest question',
    'transcript.copied': 'Copied',
    'transcript.emptyTurns': 'Interview not started yet. Use the controls on the right to generate the first turn.',
    'transcript.question': 'Question',
    'transcript.answer': 'Answer',
    'transcript.answerWaiting': 'Waiting for the latest pasted answer.',
    'transcript.summaryStored': 'A compact summary of this answer is stored for future question planning.',
    'transcript.showMore': 'Show more',
    'transcript.showLess': 'Show less',
    'transcript.version': 'Version',
    'transcript.versionHistory': 'Question version history',
    'transcript.versionDiff': 'What changed from the previous version',
    'transcript.diffBefore': 'Previous wording',
    'transcript.diffAfter': 'Updated wording',
    'transcript.diffShared': 'Unchanged context',
    'transcript.regeneratedTimes': 'Regenerated',
    'transcript.humanRegenTokens': 'Human regeneration tokens',
    'transcript.reviewAndRegenerate': 'Review and regenerate current question',
    'transcript.reviewAndRegenerateHint': 'If the current question is too broad, drifted, or aimed at the wrong branch, guide the agent and regenerate this same turn before answering.',
    'transcript.regenerate': 'Regenerate current question',
    'transcript.whyThisQuestion': 'Why this question',
    'transcript.followedReview': 'Followed human review',
    'transcript.driftRepair': 'Drift repair',
    'transcript.humanReview': 'Human review',
    'transcript.phaseReady': 'The human marked this phase as sufficiently complete.',
    'transcript.turnUsage': 'Turn token usage',
    'transcript.waiting': 'Waiting',
    'transcript.answered': 'Answered',
    'transcript.trace': 'Trace',
    'transcript.page': 'Page',
    'transcript.showingTurns': 'Showing turns',
    'transcript.of': 'of',
    'transcript.perPage': 'per page',
    'trace.title': 'Execution trace',
    'trace.currentRun': 'Current run',
    'trace.active': 'Active generation',
    'trace.activeTitle': 'Generating the next question',
    'trace.activeCopy': 'The agent is moving through the orchestration steps below. This panel updates while the run is active.',
    'trace.live': 'Live',
    'trace.total': 'Total',
    'trace.duration': 'Duration',
    'trace.next': 'Next',
    'trace.running': 'Running',
    'trace.steps': 'steps',
    'token.input': 'Input',
    'token.output': 'Output',
    'token.total': 'Total',
    'token.estimated': 'Includes estimated tokens when the provider did not return usage.',
    'delete.title': 'Delete project',
    'delete.copy': 'This permanently removes the project, its turns, summaries, transcript, and recorded token usage.',
    'delete.warning': 'This action cannot be undone.',
    'language.enLabel': 'English',
    'language.zhLabel': '中文',
    'language.en': 'EN',
    'language.zh-CN': '中文',
    'analytics.workspace': 'Analytics workspace',
    'analytics.subtitle': 'Track cost, runtime, regeneration pressure, and stage movement for the selected project while comparing it against the broader project list.',
    'analytics.currentStage': 'Current stage',
    'analytics.totalTokens': 'Total tokens',
    'analytics.totalRuntime': 'Total runtime',
    'analytics.totalRegenerations': 'Total regenerations',
    'analytics.latestRunAverage': 'Average run',
    'analytics.tokens': 'Tokens',
    'analytics.tokenMix': 'Token mix',
    'analytics.turnFlow': 'Turn flow',
    'analytics.stageDistribution': 'Stage distribution',
    'analytics.timeline': 'Timeline',
    'analytics.stageTimeline': 'Stage timeline',
    'analytics.portfolio': 'Portfolio',
    'analytics.projectComparison': 'Project token comparison',
    'analytics.emptyTitle': 'Choose a project to inspect its metrics.',
    'analytics.emptyCopy': 'The analytics page compares token load, runtime, stage spread, and regeneration patterns once a project is selected.',
  },
  'zh-CN': {
    'app.title': 'Stateful Interview Agent',
    'app.subtitle': '面向长程项目访谈的可读化编排工作台。',
    'app.language': '语言',
    'app.activeSession': '当前会话',
    'app.noSelection': '未选择项目',
    'app.turns': '轮次',
    'app.stage': '阶段',
    'app.runtime': '运行时长',
    'app.interviewFlow': '访谈流程',
    'app.interviewFlowHint': '先读当前状态，再在下方提交回答；只有需要追溯细节时再展开历史轨迹。',
    'nav.workspace': '主工作台',
    'nav.analytics': '数据统计',
    'status.start': '开始访谈',
    'status.snapshot': '运行快照',
    'status.sessionHealth': '会话健康度',
    'status.export': '导出访谈记录',
    'status.copyTranscript': '复制全文',
    'status.exportTxt': '导出 .txt',
    'status.exportMd': '导出 .md',
    'status.error': '错误',
    'status.info': '最新状态',
    'status.started': '访谈已开始，首个问题已生成。',
    'status.created': '项目已创建，可以开始生成首个问题。',
    'status.updated': '项目元信息已更新。',
    'status.deleted': '项目已删除。',
    'status.generating': '正在生成下一问...',
    'status.regeneratingCurrent': '正在重生成当前问题...',
    'status.generated': '回答已提交，下一问已生成。',
    'status.finished': '访谈已结束，已达到最大轮次限制。',
    'status.regeneratedCurrent': '当前问题已重新生成。',
    'status.projectStatus': '项目状态',
    'status.projectId': '项目 ID',
    'status.currentStage': '当前阶段',
    'status.runs': '运行次数',
    'status.totalGeneration': '累计生成时长',
    'status.averageRun': '平均单次运行',
    'status.minimumGoal': '最低目标',
    'status.latestAnswered': '最近一轮回答',
    'status.noProject': '当前没有活动项目。请在左侧选择已有项目，或创建一个新会话。',
    'status.exportHint': '你可以复制完整 transcript，或导出为纯文本和 Markdown。正文不直接放在这里，避免右侧状态栏过于拥挤。',
    'status.exportReady': '导出内容基于后端返回的最新 transcript，在前端本地生成。',
    'status.exportLocked': '至少生成一轮访谈后，导出操作才会解锁。',
    'status.reached': '已达到',
    'status.notYet': '尚未达到',
    'status.waiting': '待回答',
    'status.noTurns': '尚无轮次',
    'composer.submit': '提交回答并生成下一问',
    'composer.title': '粘贴最新回答，继续推进访谈。',
    'composer.section': '回答编辑区',
    'composer.placeholder.ready': '请在这里粘贴最新的 opencode 回答...',
    'composer.placeholder.notStarted': '先开始访谈，才能收到第一个问题。',
    'composer.placeholder.finished': '本次访谈已结束。',
    'composer.review': '人工评审信号',
    'composer.reviewHint': '可选。若回答信息不足、已经跑偏，或当前阶段可以收束，可在这里影响下一问。',
    'composer.verdict': '评审结论',
    'composer.direction': '下一步方向',
    'composer.focus': '优先追问焦点',
    'composer.phaseReady': '将当前阶段标记为“信息已足够”',
    'composer.note': '人工备注',
    'composer.noteHint': '可选备注：仍不清楚的地方、访谈跑偏的位置、或最值得追问的分支。',
    'composer.noExplicitReview': '不设置明确评审',
    'composer.noExplicitFocus': '不指定焦点',
    'composer.estimate': '下一次调用预估',
    'composer.answerInput': '回答输入',
    'composer.nextPrompt': '下一问 prompt',
    'composer.nextOutput': '下一问输出',
    'composer.estimateHint': '仅为预估。实际 token 以后端返回结果为准。',
    'composer.finishedHint': '会话结束后，不能再继续提交新的轮次。',
    'composer.lockedHint': '首个问题生成后，回答区才会解锁。',
    'composer.readyHint': '长回答会完整保留。只有在你希望纠偏、重定向或收束当前调查线程时，才需要额外加人工信号。',
    'sidebar.recentSessions': '最近会话',
    'sidebar.title': '面向项目访谈的本地编排控制台。',
    'sidebar.copy': '创建项目、启动访谈、逐轮粘贴回答，并让整条访谈链路持续可追溯。',
    'sidebar.newProject': '新建项目',
    'sidebar.seedSession': '初始化一个本地访谈会话',
    'sidebar.projectName': '项目名称',
    'sidebar.systemPrompt': '系统提示词',
    'sidebar.createProject': '创建项目',
    'sidebar.quickDemo': '快速示例',
    'sidebar.pleaseWait': '请稍候...',
    'sidebar.projectList': '项目列表',
    'sidebar.empty': '还没有项目。可以先在上方面板创建一个。',
    'sidebar.createdAt': '创建于',
    'sidebar.updatedAt': '更新于',
    'sidebar.totalTokens': '累计 Tokens',
    'sidebar.selectProject': '选择项目',
    'sidebar.rename': '重命名',
    'sidebar.save': '保存',
    'sidebar.cancel': '取消',
    'sidebar.delete': '删除',
    'sidebar.editProjectTitle': '编辑项目名称',
    'sidebar.demoPlaceholder': 'Stateful Interview 示例',
    'sidebar.currentStage': '当前阶段',
    'sidebar.turnsSuffix': '轮',
    'transcript.emptyEyebrow': '访谈记录',
    'transcript.emptyTitle': '选择一个项目后，即可查看完整访谈线程。',
    'transcript.emptyCopy': '访谈开始后，每一轮生成的问题和粘贴的回答都会按时间顺序沉淀在这里。',
    'transcript.active': '当前记录',
    'transcript.readingTitle': '可阅读的轮次历史',
    'transcript.readingCopy': '问题、回答、人工评审和编排依据被组织在同一张卡片里，便于先理解上下文，再下钻到原始细节。',
    'transcript.stageSummary': '当前阶段',
    'transcript.copyLatest': '复制最新问题',
    'transcript.copied': '已复制',
    'transcript.emptyTurns': '访谈尚未开始。请先在右侧控制区生成第一轮问题。',
    'transcript.question': '问题',
    'transcript.answer': '回答',
    'transcript.answerWaiting': '等待粘贴本轮最新回答。',
    'transcript.summaryStored': '系统已为这段回答保存紧凑摘要，用于后续问题规划。',
    'transcript.showMore': '展开全文',
    'transcript.showLess': '收起',
    'transcript.version': '版本',
    'transcript.versionHistory': '问题版本历史',
    'transcript.versionDiff': '与上一版本相比的变化',
    'transcript.diffBefore': '上一版表述',
    'transcript.diffAfter': '更新后表述',
    'transcript.diffShared': '未变化的上下文',
    'transcript.regeneratedTimes': '重生成次数',
    'transcript.humanRegenTokens': '人工介入重生成 Tokens',
    'transcript.reviewAndRegenerate': '评审并重生成当前问题',
    'transcript.reviewAndRegenerateHint': '如果当前问题太泛、已经跑偏，或问到了错误分支，可以先给出人工反馈，再对这一轮原地重生成，然后再回答。',
    'transcript.regenerate': '重新生成当前问题',
    'transcript.whyThisQuestion': '为什么会问这一题',
    'transcript.followedReview': '已遵循人工评审',
    'transcript.driftRepair': '纠偏提问',
    'transcript.humanReview': '人工评审',
    'transcript.phaseReady': '人工评审已将当前阶段标记为“足够完整”。',
    'transcript.turnUsage': '本轮 Token 使用',
    'transcript.waiting': '待回答',
    'transcript.answered': '已回答',
    'transcript.trace': '轨迹',
    'transcript.page': '第',
    'transcript.showingTurns': '当前显示',
    'transcript.of': '/',
    'transcript.perPage': '每页',
    'trace.title': '执行轨迹',
    'trace.currentRun': '当前运行',
    'trace.active': '实时生成',
    'trace.activeTitle': '正在生成下一问',
    'trace.activeCopy': 'Agent 正在依次经过下方编排步骤，面板会在运行期间持续刷新。',
    'trace.live': '实时',
    'trace.total': '总耗时',
    'trace.duration': '耗时',
    'trace.next': '下一步',
    'trace.running': '运行中',
    'trace.steps': '步',
    'token.input': '输入',
    'token.output': '输出',
    'token.total': '总计',
    'token.estimated': '当模型供应商未返回用量时，会包含估算 token。',
    'delete.title': '删除项目',
    'delete.copy': '这会永久删除该项目，以及其轮次、摘要、transcript 和所有 token 记录。',
    'delete.warning': '此操作不可撤销。',
    'language.enLabel': 'English',
    'language.zhLabel': '中文',
    'language.en': 'EN',
    'language.zh-CN': '中文',
    'analytics.workspace': '统计工作台',
    'analytics.subtitle': '围绕当前选中的项目观察 token 消耗、运行时长、重生成压力与阶段推进，同时保留项目间的对比视角。',
    'analytics.currentStage': '当前阶段',
    'analytics.totalTokens': '总 Tokens',
    'analytics.totalRuntime': '总运行时长',
    'analytics.totalRegenerations': '总重生成次数',
    'analytics.latestRunAverage': '平均单次运行',
    'analytics.tokens': 'Token 分布',
    'analytics.tokenMix': 'Token 构成',
    'analytics.turnFlow': '轮次流转',
    'analytics.stageDistribution': '阶段分布',
    'analytics.timeline': '时间线',
    'analytics.stageTimeline': '阶段推进时间线',
    'analytics.portfolio': '项目对比',
    'analytics.projectComparison': '项目 Token 对比',
    'analytics.emptyTitle': '先选择一个项目，再查看统计。',
    'analytics.emptyCopy': '选中项目后，这里会展示 token、耗时、阶段分布和重生成等统计视图。',
  },
} as const

export type TranslationKey = keyof typeof translations.en
export type Translator = ReturnType<typeof createTranslator>

const stageLabels: Record<string, Record<Locale, string>> = {
  panorama_mapping: {
    en: 'Panorama Mapping',
    'zh-CN': '全景梳理',
  },
  architecture_understanding: {
    en: 'Architecture Understanding',
    'zh-CN': '架构理解',
  },
  code_detail_completion: {
    en: 'Code Detail Completion',
    'zh-CN': '代码细节补全',
  },
  use_cases_scenarios: {
    en: 'Use Cases & Scenarios',
    'zh-CN': '场景与用例',
  },
  wrap_up: {
    en: 'Wrap Up',
    'zh-CN': '收束总结',
  },
}

const verdictLabels: Record<string, Record<Locale, string>> = {
  sufficient: {
    en: 'Sufficient',
    'zh-CN': '信息充分',
  },
  insufficient: {
    en: 'Insufficient',
    'zh-CN': '信息不足',
  },
  drifted: {
    en: 'Drifted',
    'zh-CN': '已跑偏',
  },
}

const directionLabels: Record<string, Record<Locale, string>> = {
  continue: {
    en: 'Continue',
    'zh-CN': '继续当前分支',
  },
  redirect: {
    en: 'Redirect',
    'zh-CN': '调整下一问方向',
  },
}

const runtimeStatusLabels: Record<string, Record<Locale, string>> = {
  finished: {
    en: 'Finished',
    'zh-CN': '已完成',
  },
  in_progress: {
    en: 'In progress',
    'zh-CN': '进行中',
  },
  ready: {
    en: 'Ready to start',
    'zh-CN': '可开始',
  },
  empty: {
    en: 'No project selected',
    'zh-CN': '未选择项目',
  },
}

const runStatusLabels: Record<string, Record<Locale, string>> = {
  running: {
    en: 'In progress',
    'zh-CN': '运行中',
  },
  failed: {
    en: 'Failed',
    'zh-CN': '失败',
  },
  completed: {
    en: 'Completed',
    'zh-CN': '已完成',
  },
  pending: {
    en: 'Pending',
    'zh-CN': '等待中',
  },
}

export function normalizeLocale(value: string | null | undefined): Locale {
  return value === 'zh-CN' ? 'zh-CN' : 'en'
}

export function createTranslator(locale: Locale) {
  return function translate(key: TranslationKey) {
    return translations[locale][key] ?? translations.en[key]
  }
}

function humanizeSnakeCase(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function getDisplayStageLabel(rawStage: string | null | undefined, locale: Locale) {
  if (!rawStage) {
    return locale === 'zh-CN' ? '未开始' : 'Not started'
  }

  const normalizedStage = rawStage.trim().toLowerCase().replace(/\s+/g, '_')
  return stageLabels[normalizedStage]?.[locale] ?? humanizeSnakeCase(normalizedStage)
}

export function getReviewVerdictLabel(verdict: string | null | undefined, locale: Locale) {
  if (!verdict) {
    return locale === 'zh-CN' ? '未标注' : 'Not set'
  }

  return verdictLabels[verdict]?.[locale] ?? humanizeSnakeCase(verdict)
}

export function getReviewDirectionLabel(direction: string | null | undefined, locale: Locale) {
  if (!direction) {
    return locale === 'zh-CN' ? '默认' : 'Default'
  }

  return directionLabels[direction]?.[locale] ?? humanizeSnakeCase(direction)
}

export function getRuntimeStatusText(status: 'finished' | 'in_progress' | 'ready' | 'empty', locale: Locale) {
  return runtimeStatusLabels[status][locale]
}

export function getRunStatusLabel(status: string | null | undefined, locale: Locale) {
  if (!status) {
    return runStatusLabels.pending[locale]
  }

  return runStatusLabels[status]?.[locale] ?? humanizeSnakeCase(status)
}

export function getStepStatusLabel(status: string | null | undefined, locale: Locale) {
  return getRunStatusLabel(status, locale)
}

export function getQuestionIntentLabel(value: string | null | undefined, locale: Locale) {
  if (!value) {
    return locale === 'zh-CN' ? '未标注' : 'Not set'
  }

  const labels: Record<string, Record<Locale, string>> = {
    explore_architecture: {
      en: 'Explore architecture',
      'zh-CN': '追问架构',
    },
    expand_code_detail: {
      en: 'Expand code detail',
      'zh-CN': '补充代码细节',
    },
    validate_scenario: {
      en: 'Validate scenario',
      'zh-CN': '验证场景',
    },
    drift_repair: {
      en: 'Drift repair',
      'zh-CN': '拉回主线',
    },
  }

  return labels[value]?.[locale] ?? humanizeSnakeCase(value)
}

export function getOperationTypeLabel(operationType: string, locale: Locale) {
  const labels: Record<string, Record<Locale, string>> = {
    question_generation: {
      en: 'Question generation',
      'zh-CN': '问题生成',
    },
    answer_summarization: {
      en: 'Answer summarization',
      'zh-CN': '回答摘要',
    },
  }

  return labels[operationType]?.[locale] ?? humanizeSnakeCase(operationType)
}

export function getBooleanLabel(
  value: boolean | null | undefined,
  locale: Locale,
  options?: {
    trueLabel?: string
    falseLabel?: string
    nullLabel?: string
  },
) {
  if (value == null) {
    return options?.nullLabel ?? (locale === 'zh-CN' ? '暂无' : 'Not available')
  }

  return value
    ? options?.trueLabel ?? (locale === 'zh-CN' ? '是' : 'Yes')
    : options?.falseLabel ?? (locale === 'zh-CN' ? '否' : 'No')
}
