# Question Network And User Intent Upgrade Plan

**Goal:** Upgrade the question-generation system from isolated single-question planning into a networked exploration engine that expands breadth and depth around concrete code evidence, preserves cross-question continuity, and better matches how real developers read code, trace call paths, debug failures, and reason about implementation details.

**Architecture:** Keep the existing five-stage interview model and one-visible-question-per-turn UX, but replace the current branch-first / single-target planning bias with a graph-aware orchestration model. Introduce an internal `question_graph` / `investigation_frontier` layer inside `coverage_state`, teach the planner to select the next question from a connected neighborhood rather than from a single branch label, and make retrieval, validation, review, and analytics all aware of question lineage, neighboring topics, and real developer intent distributions. Continue using queue-style decomposition for one visible question per turn, but extend it from linear follow-ups into a directed network of sibling, parent, child, upstream, downstream, and cross-module expansion opportunities.

**Tech Stack:** FastAPI, SQLAlchemy models with JSON-backed project state, LangGraph orchestration in `app/graphs`, service-layer planning and validation in `app/services`, React + TypeScript + Vite analytics frontend, unittest-based backend tests, existing debug APIs and run-trace instrumentation.

### Task 1: Extend the orchestration state from branch coverage to question-network coverage

**Files:**
- Modify: `app/services/coverage_service.py`
- Modify: `app/schemas/debug.py`
- Modify: `frontend/src/types/api.ts`
- Test: `tests/test_framework_orchestration.py`

**Step 1: Write failing tests for graph-aware state**

Add tests asserting that `default_coverage_state()`, `load_coverage_state()`, and `rebuild_coverage_state()` expose new top-level structures such as:
- `question_graph`
- `investigation_frontier`
- `developer_intent_coverage`
- `question_network_stats`

Also add a backward-compatibility test proving an older coverage blob is normalized into the new graph-aware shape without losing existing queue or file coverage data.

**Step 2: Add graph-aware state primitives**

Extend the coverage snapshot with JSON-serializable structures such as:
- `question_graph.nodes`: normalized question topics keyed by stable IDs
- `question_graph.edges`: typed relationships such as `follows_from`, `same_artifact`, `upstream_of`, `downstream_of`, `same_concept`, `error_path_of`, `optimization_of`
- `investigation_frontier`: ranked unresolved next-hop candidates
- `developer_intent_coverage`: distribution counters for developer intents such as `code_reading`, `bug_investigation`, `call_chain_trace`, `data_contract`, `edge_case`, `performance`, `dependency_usage`, `state_transition`
- `question_network_stats`: graph density, repeated-template ratio, isolated-node ratio, breadth/depth ratios

Keep the older branch and queue structures, but treat them as supporting evidence rather than the full planning model.

**Step 3: Rebuild graph state from existing history**

When rebuilding coverage from historical turns:
- create normalized topic nodes from `question_plan`, `answer_summary`, repo-selected paths, and branch summaries
- attach stable lineage fields such as `node_id`, `parent_node_id`, `source_turn_no`, `artifact_keys`, `intent_type`, `depth_level`
- derive edges from repeated artifacts, answer anchors, call-chain continuations, and planner decomposition metadata
- mark nodes as `covered`, `partial`, `needs_follow_up`, or `new_frontier`

**Step 4: Expose typed debug payloads**

Extend typed backend and frontend debug schemas so the graph and frontier are visible in the existing analytics surfaces rather than hidden in opaque dicts.

### Task 2: Replace single-target planning with graph-frontier planning

**Files:**
- Modify: `app/services/question_planner.py`
- Modify: `app/services/repetition_guard.py`
- Modify: `tests/test_question_planner.py`
- Test: `tests/test_framework_orchestration.py`

**Step 1: Write failing planner tests for question-network expansion**

Add tests proving:
- the planner can pick a follow-up from a connected neighbor instead of repeating the same exact artifact
- the planner can expand breadth from one file into upstream/downstream modules
- the planner can deepen from a surface question into implementation, state, error, or optimization subtopics
- the planner avoids creating isolated questions when a meaningful connected frontier exists
- repeated question forms against the same artifact are penalized even if the raw target label changes slightly

**Step 2: Introduce frontier candidate generation**

Add a planner step that builds ranked candidate nodes from:
- current artifact
- sibling implementation angles
- upstream/downstream call-chain nodes
- related files or symbols selected by repo grounding
- unresolved answer anchors
- under-covered developer intents

Each candidate should carry:
- `candidate_id`
- `source_node_id`
- `relation_type`
- `target_type`
- `target_label`
- `developer_intent`
- `depth_kind`
- `breadth_kind`
- `score_explanation`

**Step 3: Rank by connected value, not only branch score**

Replace the current branch-first selection bias with a blended rank such as:
- connection strength to the active topic
- unresolved technical depth
- breadth value from neighboring modules or flows
- developer-intent diversity bonus
- recency / repetition penalty
- file importance / exploration gap
- stage alignment

The planner should explicitly prefer:
- depth expansion when the current node is still shallow and unresolved
- breadth expansion when the current artifact is partially understood but its dependencies or downstream consumers remain unclear
- graph stitching when two nearby topics have not yet been connected by a question

**Step 4: Persist graph-aware planner reasoning**

Extend planner metadata with fields such as:
- `source_node_id`
- `target_node_id`
- `relation_type`
- `developer_intent`
- `depth_kind`
- `breadth_kind`
- `frontier_rank`
- `why_this_question`

The reasoning text should explain both the technical continuation and the user-behavior rationale.

### Task 3: Expand decomposition from linear queues into multi-branch investigation networks

**Files:**
- Modify: `app/services/question_queue_service.py`
- Modify: `app/graphs/interview_nodes.py`
- Modify: `tests/test_interview_nodes.py`

**Step 1: Write failing tests for non-linear follow-up generation**

Cover cases where:
- one question about an execution path creates multiple connected next hops such as error path, state transition, and downstream consumer
- one follow-up answer prunes one branch but leaves siblings active
- queued nodes preserve parent/child and sibling relationships
- the next surfaced question is chosen from ranked frontier items rather than simple FIFO ordering

**Step 2: Upgrade queue items into frontier items**

Extend queue objects with network-aware fields such as:
- `node_id`
- `parent_node_id`
- `relation_type`
- `developer_intent`
- `depth_kind`
- `artifact_keys`
- `priority_score`
- `blocked_by`
- `evidence_sources`

Preserve one-visible-question-per-turn behavior, but let the internal structure behave like a ranked frontier rather than a plain list.

**Step 3: Add sibling and derivative generation rules**

When a planner or answer identifies a rich topic, generate multiple derivatives such as:
- `implementation_detail`
- `parameter_contract`
- `state_transition`
- `error_path`
- `dependency_behavior`
- `performance_or_optimization`
- `boundary_condition`
- `caller_or_consumer`

Do this deterministically when the branch summary already contains clear markers, and only use the LLM as a fallback if structured heuristics cannot derive enough candidates.

**Step 4: Add answer-aware graph pruning**

After each answer:
- mark covered frontier items as resolved if the answer already covers them
- lower the score of nearby items whose informational value collapsed
- raise the score of newly revealed unresolved neighbors
- avoid resurfacing stale siblings when the active answer naturally moved the user to a better next-hop topic

### Task 4: Make retrieval graph-aware and neighbor-aware

**Files:**
- Modify: `app/services/context_engineering.py`
- Modify: `app/services/repo_grounding_service.py`
- Modify: `tests/test_context_retrieval.py`

**Step 1: Write failing retrieval tests**

Add tests proving retrieval can include:
- active node context
- parent and child nodes
- sibling implementation angles
- upstream/downstream repository evidence
- related symbols and files discovered from repo grounding

**Step 2: Build connected context bundles**

Replace the current “selected branches only” retrieval focus with a structured bundle:
- `active_topic_context`
- `question_lineage_context`
- `neighbor_topics_context`
- `repo_neighbor_context`
- `developer_intent_context`

The generation context should explicitly show how the next topic connects to the current one.

**Step 3: Expand repository query derivation**

`derive_repository_queries()` should stop relying only on `target_label` and latest answer keywords. Include:
- current node artifact keys
- parent and sibling artifacts
- upstream/downstream symbols
- failure markers
- data contract nouns
- dependency and protocol names from nearby nodes

**Step 4: Surface graph continuity in prompt context**

Add prompt-ready text describing:
- what the current investigation thread is
- what adjacent directions remain open
- why the selected next hop matches realistic developer reasoning

### Task 5: Model real developer intent and question distributions explicitly

**Files:**
- Create: `app/services/developer_intent_service.py`
- Modify: `app/services/question_planner.py`
- Modify: `app/services/question_validator.py`
- Modify: `app/services/question_reviewer.py`
- Test: `tests/test_question_planner.py`
- Test: `tests/test_question_generation_repair.py`

**Step 1: Write failing tests for intent-aware planning**

Add tests proving:
- repeated “how does this work” questions are penalized when other developer intents are under-covered
- the planner rotates across real developer intents in plausible proportions
- bug-investigation and call-chain questions are preferred when the current answer reveals failure-handling uncertainty
- performance or optimization questions are not asked too early without implementation grounding

**Step 2: Define the intent taxonomy**

Implement a small, explicit intent taxonomy aligned with real developer workflows, for example:
- `trace_execution`
- `understand_responsibility`
- `inspect_inputs_outputs`
- `investigate_failure`
- `follow_state_change`
- `check_dependency_usage`
- `understand_data_contract`
- `review_boundary_case`
- `evaluate_optimization_tradeoff`
- `connect_related_module`

Each question should carry exactly one primary developer intent plus optional secondary tags.

**Step 3: Add intent quotas and stage-aware distributions**

For each stage, define target distributions rather than letting one generic phrasing dominate:
- `Panorama Mapping`: purpose, workflow, boundaries, modules
- `Architecture Understanding`: responsibilities, collaboration, call chains, data flow
- `Code Detail Completion`: execution, state, errors, contracts, dependencies, boundary cases, optimization follow-ups
- `Use Cases & Scenarios`: actors, inputs/outputs, scenario variants, business-side failure handling

The planner should use these distributions to diversify questioning while staying stage-correct.

**Step 4: Use intent in validation and review**

Reject or down-rank questions that:
- have no clear developer intent
- repeat the same phrasing and intent pattern over recent turns
- feel generic enough that they could apply to almost any file
- do not connect to the active graph thread or a meaningful neighboring topic

### Task 6: Enforce non-isolated, non-template question quality

**Files:**
- Modify: `app/services/question_validator.py`
- Modify: `app/services/question_postprocessor.py`
- Modify: `app/services/question_reviewer.py`
- Modify: prompt assets under `app/prompts/assets/`
- Test: `tests/test_question_generation_repair.py`

**Step 1: Write failing tests for graph continuity and realism**

Cover cases where questions should be rejected because they:
- are too generic to a concrete code artifact
- do not connect to the active topic, parent, sibling, or neighbor
- repeat template stems too often
- ask obvious “AI checklist” questions instead of natural developer follow-ups

**Step 2: Add graph-continuity validation**

Require code-detail questions to satisfy at least one continuity condition:
- same artifact, deeper angle
- directly connected neighbor artifact
- explicit upstream/downstream relation
- answer-anchor follow-up
- scenario continuation from the same workflow

If none apply, the question should be treated as isolated and invalid unless the planner explicitly marks it as an intentional topic shift.

**Step 3: Add template and phrase-pattern pressure**

Track repeated openings and overused scaffolds such as:
- `How does X currently...`
- `What role does X play...`
- `Where does X...`
- repetitive “error path / main flow / state management” wording with no natural variation

Use a deterministic repair layer to vary framing while preserving technical precision.

**Step 4: Update prompt contracts**

Refresh prompt assets so they instruct the writer to:
- continue a real investigation thread
- sound like a developer reading or debugging current code
- prefer a concrete purpose over generic completeness
- expand around neighboring modules and realistic next-hop concerns
- avoid artificial checklist wording and textbook-style prompts

### Task 7: Add observability for the question network and developer-intent quality

**Files:**
- Modify: `app/api/routes/debug.py`
- Modify: `app/schemas/debug.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify analytics UI files under `frontend/src/`

**Step 1: Expose graph and intent diagnostics**

Add debug payloads for:
- active node and lineage
- frontier ranking
- edge list for the current thread
- isolated node count
- intent distribution
- template repetition counters
- graph breadth/depth metrics

**Step 2: Add analytics visualizations**

Add frontend panels for:
- current investigation thread
- neighboring open topics
- most repeated question stems
- developer intent coverage
- isolated vs connected question ratio
- frontier items by relation type

**Step 3: Extend run-trace metadata**

Add planner and writer trace metadata so operators can inspect:
- why a node was chosen
- which neighbors were considered
- why other frontier items lost
- whether the chosen question deepened, broadened, or stitched the graph

### Task 8: Add realistic scenario fixtures and end-to-end tests

**Files:**
- Modify: `tests/test_framework_orchestration.py`
- Modify: `tests/test_interview_nodes.py`
- Modify: `tests/test_context_retrieval.py`
- Create: `tests/test_question_network_planning.py`

**Step 1: Build realistic developer-workflow fixtures**

Create fixtures representing common developer behaviors:
- reading a new module and tracing where requests go next
- debugging a failure and expanding from symptom to error path to caller to state mutation
- understanding an API contract and then asking about consumers and boundary cases
- reviewing a dependency integration and then following retries, timeouts, and fallback handling

**Step 2: Add network-level assertions**

Write tests asserting:
- the generated question sequence forms a connected graph instead of isolated nodes
- breadth and depth both grow over time
- developer intent distribution is not collapsed into one question type
- graph continuity survives regeneration and human review redirects

**Step 3: Add regression protection**

Keep existing guarantees:
- one visible question per turn
- no drift into change-planning while in understand mode
- queue/frontier pruning after answers
- repository-grounded specificity

### Task 9: Roll out incrementally behind explicit planner flags

**Files:**
- Modify: `app/core/config.py`
- Modify: services that consume planner state
- Modify: README / `README_zh.md`

**Step 1: Add feature flags**

Introduce flags for:
- `question_graph_enabled`
- `graph_frontier_planning_enabled`
- `developer_intent_balancing_enabled`
- `graph_continuity_validation_enabled`

This keeps rollout safe and debuggable.

**Step 2: Document operational guidance**

Document:
- how graph continuity works
- how developer intent balancing affects question selection
- how to inspect isolated-question failures in debug tooling
- how human review should redirect a weak thread without breaking the network

**Step 3: Define success metrics**

Track metrics such as:
- isolated question ratio
- average connected frontier size
- unique developer-intent coverage per interview
- repeated-template ratio
- number of cross-module transitions with explicit rationale
- proportion of questions with parent/neighbor linkage

## Implementation Order

1. Extend `coverage_state` with graph and intent primitives.
2. Add failing tests for graph-frontier planning and continuity validation.
3. Implement graph candidate generation and frontier ranking in `question_planner.py`.
4. Upgrade queue handling in `interview_nodes.py` and `question_queue_service.py`.
5. Make retrieval and repo grounding neighbor-aware.
6. Add developer-intent modeling and diversity pressure.
7. Tighten validation, prompt contracts, and reviewer checks.
8. Expose analytics and debug surfaces.
9. Update docs and rollout flags.

## Risks And Tradeoffs

- Over-modeling the graph can make planning opaque if debug metadata is not first-class.
- Aggressive continuity enforcement can block healthy topic shifts; explicit shift markers and reviewer overrides are required.
- Intent balancing can become artificial if quotas are too rigid; distributions must be soft preferences, not hard loops.
- Graph expansion must stay repository-grounded; otherwise the network becomes wide but shallow.

## Immediate Next Step

Start with state-model and planner tests first. The current repository already has queue decomposition and file-coverage balancing; the new work should build on those mechanics rather than replace them.
