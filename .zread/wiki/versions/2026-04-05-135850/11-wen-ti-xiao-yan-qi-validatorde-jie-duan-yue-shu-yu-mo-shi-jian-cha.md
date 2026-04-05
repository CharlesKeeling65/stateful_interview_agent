在状态化访谈Agent的架构中，问题生成并非单一步骤，而是一个**生成→校验→修正→再校验**的闭环过程。Validator作为这个闭环中的"质量守门人"，承担着确保生成的问题符合阶段目标、模式要求和语义唯一性的关键职责。本文档将深入剖析Validator的设计原理、阶段约束机制、模式检查策略，以及它在整个工作流中的集成方式。

## 核心定位：Validator在问题生成流水线中的角色

Validator并不是一个独立的校验服务，而是一套分层校验逻辑的集合。在实际实现中，这个问题校验体系由三个核心组件构成，它们各司其职又相互配合：

**第一层是`question_Validator`中的`validate_question_for_stage`函数**，负责基于当前访谈阶段的约束检查，它验证问题是否与该阶段的认知目标相匹配。例如，在"全景映射"阶段不应出现深度实现细节，而在"代码细节补全"阶段则必须聚焦具体的代码工件。**第二层是`validate_question_against_repository`函数**，它检查问题中引用的文件路径和符号是否存在于当前提供给Agent的证据束（evidence bundle）中，确保问题的 grounding 基础。**第三层是`question_ Reviewer`中的`review_question_text`函数**，它在问题生成的更上游阶段工作，负责检查Planner输出的决策是否符合模式的意图约束。

这三个层次的校验分布在问题生成流水线的不同位置。`question_Validator`的执行时机是在LLM生成问题文本之后，此时问题已经完成初步的格式化处理，但还需要通过阶段和模式的双重检验。如果校验失败，系统会触发重试机制，将具体的错误原因反馈给LLM进行修正。这种设计体现了"**快速失败、快速修正**"的工程哲学，避免了将不合格的问题直接送往下游。

Sources: [app/services/question_validator.py](app/services/question_validator.py#L117-L224)
Sources: [app/graphs/interview_nodes.py](app/graphs/interview_nodes.py#L216-L278)

## 阶段约束机制：五阶段验证矩阵

Validator的阶段约束设计基于一个核心洞察：**不同访谈阶段的认知目标截然不同，一个"好问题"的定义也随之改变**。系统定义了五个访谈阶段，每个阶段都有其独特的验证规则。这种设计的根本原因在于，访谈Agent需要在有限轮次内完成从宏观到微观的认知建构，每个阶段必须聚焦于特定的认知维度，任何偏离该维度的提问都会被视为低质量甚至有害的。

### 阶段定义与映射

系统通过`stage_manager`模块定义了清晰的阶段序列。根据访谈轮次的自然划分，系统会自动确定当前所处阶段：第1-5轮对应"Panorama Mapping"，第6-10轮对应"Architecture Understanding"，第11-32轮对应"Code Detail Completion"，第33轮及以后对应"Use Cases & Scenarios"。这个映射并非固定不变，可以根据实际访谈进展动态调整，但默认配置提供了一个稳健的基线。

Sources: [app/services/stage_manager.py](app/services/stage_manager.py#L36-L92)

### 各阶段的验证规则详解

**Panorama Mapping阶段**要求问题必须避免深度实现细节。该阶段的认知目标是帮助Agent建立对代码库的整体认知，理解系统的边界、主要模块和高层架构。因此，验证规则会拒绝包含`.py`、`.ts`、`.tsx`等文件扩展名，以及`class`、`method`、`function`等实现层面关键词的问题。如果问题中出现这些标记，Validator会返回"Panorama questions must avoid deep implementation detail"的拒绝原因。

**Architecture Understanding阶段**的验证规则更为微妙。该阶段既需要避免过早陷入文件级别的细节，又要确保问题确实聚焦于架构层面。验证规则采用双重检查：首先，问题必须包含架构相关的关键词，如`module`、`service`、`collabor`、`call chain`、`request path`、`communicat`、`responsibil`、`layer`等；其次，问题不能包含文件扩展名，避免直接指向具体代码文件。这种设计确保了问题始终在"模块协作"和"调用关系"的维度上展开。

**Code Detail Completion阶段**是验证规则最为复杂的阶段，因为该阶段需要同时满足多个条件：问题必须包含代码细节标记（如`.py`、`.ts`、`class`、`method`、`function`、`execution path`等），以确保问题的具体性；同时，在`understand_current_code`模式下，问题还必须包含"如何"（how does/how do）、"当前"（currently/current）、"追踪"（trace）等词汇，确保问题询问的是当前实现的行为而非建议修改。此外，该阶段明确拒绝任何变更建议标记，防止问题从"理解现有实现"滑向"规划修改方案"。

**Use Cases & Scenarios阶段**要求问题必须围绕角色、场景、输入输出和边界条件展开。验证规则会检查问题是否包含`scenario`、`user`、`role`、`input`、`output`、`boundary`、`extension`、`workflow`等关键词。同时，该阶段拒绝纯粹代码层面的问题——如果问题包含文件扩展名和类/方法关键词但缺少场景要素，会被视为不合格。这种设计确保了问题始终围绕业务语义展开。

**Final Wrap-up阶段**是一个收敛阶段，其验证规则相对简单：问题不应重新打开深度实现话题。如果问题包含`class`、`method`、`.py`、`.ts`等标记，会被拒绝。这个阶段的认知目标是总结和确认，而非探索新领域。

Sources: [app/services/question_validator.py](app/services/question_validator.py#L182-L219)

## 模式检查策略：理解模式与变更模式的博弈

除了阶段约束之外，Validator还实现了一套模式检查机制，用于识别问题的"意图类型"。这个机制的核心目标是**确保Agent始终在其声明的模式下运作**，避免"挂羊头卖狗肉"的情况——例如，声明要"理解当前代码"的问题实际上在询问"应该如何修改"。

### 变更建议模式的识别

系统维护了一个名为`CHANGE_PROPOSAL_MARKERS`的元组，包含超过20个常见的变更建议短语，如"should be changed"、"redesign"、"refactor"、"improve"、"modify"等。这个列表涵盖了从显式到隐式的多种变更建议表达方式。Validator会检查这些问题标记是否出现在问题的正文中，一旦发现，立即触发拒绝逻辑。

更精细的检查通过正则表达式模式实现。`CHANGE_PROPOSAL_PATTERNS`列表包含了10个复杂的正则表达式，能够捕捉更复杂的变更建议句式。例如，`r"should\s+be\s+(changed|modified|updated|refactored)"`可以匹配"should be changed"、"should be modified"等多种变体，而`r"(?:how|what)\s+(?:should|could|would)\s+we\s+(change|modify|fix|implement)"`则可以匹配"how should we change"、"what could we implement"等句式。

Sources: [app/services/question_validator.py](app/services/question_validator.py#L5-L38)

### 理解模式的识别与鼓励

与变更模式相对，系统也定义了"理解模式"应鼓励的句式。`UNDERSTANDING_PATTERNS`列表包含了一系列表明问题意图是理解而非修改的模式，如`how does`、`what does`、`why does`、`explain how`、`describe the`、`current implementation`等。这些模式的存在意义不仅在于验证，更在于为LLM提供明确的"好问题"示例，帮助其在生成时主动选择合适的表达方式。

### 模式与阶段的交叉验证

模式和阶段的验证是交叉进行的。在`understand_current_code`模式下，Validator会双重检查：既要验证问题符合当前阶段的约束（如Architecture阶段需要架构关键词），又要确保问题不包含任何变更建议标记。这种交叉验证确保了问题在"是什么阶段"和"是什么模式"两个维度上都是合规的。

Sources: [app/services/question_validator.py](app/services/question_validator.py#L146-L173)

## 语义冗余检查：基于签名的重复检测

Validator的另一个关键职责是检测语义上的重复问题。这个功能由`repetition_guard`模块实现，它采用了一种多层次的相似度检测策略。

### 问题签名机制

系统为每个问题构建一个签名（signature），由五个维度组成：`stage`（阶段）、`intent`（意图）、`branch_id`（分支ID）、`target_type`（目标类型）、`target_label`（目标标签）。这个签名的设计理念是：如果两个问题的签名完全相同，它们本质上是在询问同一件事。例如，两个都标记为"Architecture Understanding"阶段、意图为"architecture_clarification"、目标为同一文件的问题，无论措辞如何变化，都是重复的。

目标类型的推断是签名构建的关键环节。系统通过正则表达式从问题文本中自动提取：文件路径（匹配`.py`、`.ts`等扩展名）、方法名（匹配`method_name(`模式）、类名（匹配大写字母开头的标识符）。此外，系统还预设了几种特殊的目标类型：`error_path`（错误处理相关）、`library_usage`（库使用相关）、`execution_path`（执行路径相关）和`scenario`（场景相关）。

Sources: [app/services/repetition_guard.py](app/services/repetition_guard.py#L37-L82)

### 多层次相似度计算

除了精确的签名匹配，系统还提供了三种层次的相似度检测：

**第一层是精确签名匹配**。如果两个问题的签名字符串完全相同，直接判定为重复。这种检测最为严格，适用于完全相同的提问意图。

**第二层是基于编辑距离的词汇相似度检测**。系统使用Python的`SequenceMatcher`计算两个问题文本的相似度比率，默认阈值为0.76。如果两个问题的目标标签相同（如都指向同一个文件），且词汇相似度超过阈值，则判定为重复。这种检测能够捕捉措辞不同但实质相同的问题。

**第三层是基于嵌入向量的语义相似度检测**（可选，取决于配置）。当词汇相似度在0.45到0.76之间、且问题意图相同时，系统会计算问题的语义嵌入向量。如果语义相似度超过配置的阈值（默认0.85），也会判定为重复。这种检测能够发现措辞差异较大但语义相近的问题。

Sources: [app/services/repetition_guard.py](app/services/repetition_guard.py#L132-L173)

## 仓库证据校验：Grounding验证

`validate_question_against_repository`函数负责第三层验证：确保问题中提到的文件和符号在Agent可访问的证据范围内。这个验证对于确保问题的可回答性至关重要。

### 路径 grounding 检查

系统维护了一个已知路径集合，包括用户在项目配置中选定的代码路径（`selected_paths`）以及项目清单中标记的关键文件（`key_files`）。当问题文本中出现文件路径时（如`app/services/question_validator.py`），Validator会检查该路径是否在已知集合中。如果不在，会返回"Question references repository paths that were not found in the current evidence bundle"的错误。

### 符号 grounding 检查

在"Code Detail Completion"阶段，还有一个特殊的符号级检查。如果问题没有提及任何文件路径，系统会退而求其次，检查问题中是否提到了已知符号（如类名、函数名）。如果既没有已知路径也没有已知符号，问题会被拒绝。这个规则确保了该阶段的问题始终是"可grounded"的——Agent有足够的上下文来回答这个问题。

Sources: [app/services/question_validator.py](app/services/question_validator.py#L227-L270)

## 验证流程与重试机制

Validator的集成方式体现了"fail-fast, retry-with-context"的工程原则。在`interview_nodes.py`中，问题生成的完整流程如下：

LLM首先生成一个候选问题。随后，系统调用`validate_question_for_stage`和`validate_question_against_repository`进行两阶段验证。如果验证通过，问题进入下一环节。如果验证失败，系统会将具体的错误原因（`reasons`列表中的内容）组织成重试提示，返回给LLM要求重新生成。这个重试提示的形式为："The previous draft did not satisfy the stage-specific validator. Fix these issues and regenerate one better question: [具体错误原因]"。

重试后，系统会再次进行验证。如果第二次仍然失败，系统会进行最后一轮尝试。这是最后的机会——如果第三次仍然无法通过验证，系统会抛出`ValueError`异常，中断整个工作流。这个三重验证的设计平衡了"给LLM机会修正"和"防止无限重试"两个目标。

Sources: [app/graphs/interview_nodes.py](app/graphs/interview_nodes.py#L235-L278)

## 模式约束与AgentMode的协同

Validator的另一个重要维度是与`AgentMode`的协同。系统定义了三种Agent运行模式：`understand_current_code`（理解当前代码）、`review_current_code`（评审当前代码）、`propose_changes`（建议修改）。不同的模式有不同的约束规则。

在`understand_current_code`模式下，系统最为严格：不允许任何变更建议，完全聚焦于当前行为。reject markers列表包含了"should change"、"redesign"、"modify this"等20余个关键词。一旦检测到这些问题标记，会立即触发拒绝。

在`review_current_code`模式下，系统允许质量评估性质的问题，但仍然拒绝具体的实现方案。如"implement this"、"change this now"、"fix by doing"等直接指向实现的表述会被拒绝。

Sources: [app/services/mode_service.py](app/services/mode_service.py#L11-L65)
Sources: [app/services/mode_service.py](app/services/mode_service.py#L80-L129)

## 总结与架构演进建议

Validator的设计体现了状态化访谈Agent的一个核心工程理念：**约束即智能**。通过精细的阶段约束、模式检查和语义去重，Validator帮助Agent在有限的访谈轮次内始终聚焦于正确的认知目标，避免无效的、重复的或离题的问题。

从架构角度看，Validator的实现有几个值得注意的设计模式值得借鉴。首先是**分层验证**：格式验证→语义验证→grounding验证→模式验证，每层各司其职又相互配合。其次是**配置化的标记集合**：阶段标记、模式标记、重复阈值等都通过常量或配置管理，便于调整和扩展。再次是**有意义的错误消息**：验证失败时返回的`reasons`列表不仅告诉LLM"失败了"，还具体说明了"为什么失败"以及"应该如何修正"。最后是**有限重试 + 异常中断**：三重验证的设计平衡了容错性和可靠性。

在后续的架构演进中，可以考虑将Validator的设计原则推广到其他需要质量控制的环节，例如回答质量验证、覆盖度完整性验证等。同时，当前Validator的规则主要是基于关键词和正则的，未来可以考虑引入更智能的验证方式，例如使用小模型进行意图分类、或基于embedding的语义验证。