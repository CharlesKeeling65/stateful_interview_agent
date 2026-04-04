# 专题：如何设计 Human-in-the-loop 产品交互

这篇专题专门讲产品层面的一个关键问题：

> Human-in-the-loop 不只是后端支持人工输入，而是前后端共同设计一种“低负担、真生效、可见证”的协作体验。

这个项目在这方面已经做出了很好的学习样板。

---

## 1. 一个糟糕的人机协作交互长什么样

常见失败模式：

1. 用户要填很多复杂字段，负担太重  
2. 用户填了，但系统几乎不理会  
3. 系统理会了，但 transcript 看不出来  
4. 系统看起来像支持协作，实际仍是 AI 自己主导  

这种系统表面上“有人类参与”，但没有形成真正的人机闭环。

---

## 2. 一个好的 human-in-the-loop 交互应该满足什么

至少满足 4 点：

1. **轻量**
- 不要让用户每轮填一堆表

2. **结构化**
- 输入不能只是散乱备注

3. **真实生效**
- planner / stage controller 能消化它

4. **可见**
- transcript 和 UI 能看出人类影响了轨迹

这个项目的 `human_review` 已经在往这四点收敛。

---

## 3. 为什么前端是 human-in-the-loop 的核心，而不是附属

关键前端代码：
- [`frontend/src/components/AnswerComposer.tsx`](../frontend/src/components/AnswerComposer.tsx)
- [`frontend/src/components/TurnCard.tsx`](../frontend/src/components/TurnCard.tsx)
- [`frontend/src/hooks/useProject.ts`](../frontend/src/hooks/useProject.ts)

前端承担的不是“展示输入框”这么简单，而是：

### 3.1 收集结构化信号

例如：
- verdict
- direction
- preferred_next_focus
- note
- phase_ready

### 3.2 用低负担方式让用户表达判断

比如：
- 折叠面板
- 非必填字段
- 可以只提供局部 signal

### 3.3 把协作结果展示出来

让 transcript 看得出：
- 这题为什么跟着 human redirect

---

## 4. 为什么“真实生效”比“字段很多”更重要

很多系统会犯一个错：
- 表单设计得很完整
- 但 planner 并没有优先尊重这些输入

这会让用户很快失去信任：
- 我都填了，系统还是照自己原路走

这个项目最值得学习的是：
- human review 一旦触发 redirect，会优先进入 planner 分支

这就是“真实生效”。

---

## 5. 什么样的人类输入最有价值

从这个项目的经验看，最实用的不是长备注，而是：

### 5.1 verdict
- sufficient / insufficient / drifted

它回答的是：
- 上一轮值不值得继续

### 5.2 direction
- continue / redirect

它回答的是：
- 轨迹应不应该变向

### 5.3 preferred_next_focus

它回答的是：
- 变向之后该往哪走

### 5.4 phase_ready

它回答的是：
- 这个阶段是否可以推进

这些字段都比“随便写一句 note”更容易被 agent 消化。

---

## 6. transcript 为什么必须显示协作痕迹

如果 human review 只存在后台状态里，而 transcript 看不见，最终交付还是会像：
- AI 自问自答

所以 transcript 至少要能让人看出来：
- 用户做了 redirect
- 用户认为上一轮 insufficient
- 系统因此改了下一题

这不仅是 UX，也是 deliverable 质量的一部分。

---

## 7. 如何把这种设计迁移到别的 agent

### code agent

human review 可以是：
- fix direction ok?
- inspect another file?
- stop editing and explain?

### research agent

human review 可以是：
- evidence enough?
- go deeper?
- switch source?

### workflow agent

human review 可以是：
- approve next tool call?
- reroute to branch B?

所以本质上不是“采访系统特有交互”，而是通用的人机协作模式。

---

## 8. 一个很适合你的练习

练习目标：
- 新增一个 `preferred_next_focus = error_handling`

你需要同时改：
- 前端选项
- schema
- planner
- transcript 展示

这是一个非常好的跨前后端 human-in-the-loop 练习。

---

## 9. 一句话总结

Human-in-the-loop 产品交互的关键不是“让用户说点话”，而是：

**让用户能以低负担方式给出结构化判断，并让这些判断真实进入 agent 的规划与展示闭环。**
