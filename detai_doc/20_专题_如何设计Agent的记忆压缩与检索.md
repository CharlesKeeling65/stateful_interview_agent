# 专题：如何设计 Agent 的记忆压缩与检索

这是 AI Agent 工程里最容易被做坏的一层。

很多项目只有两种做法：

1. 全历史都塞进模型  
2. 只保留最近几轮  

这两种都不够。

这个项目已经演进到一个更合理的思路：
- 历史不只是“截断”
- 而是“压缩 + 结构化 + 检索”

---

## 1. 为什么单纯“保留最近历史”不够

因为很多 agent 任务不是只看最近连续性，而是需要：
- 回到较早但重要的 branch
- 知道哪些 gap 还没填
- 避免重复问已经问过的目标

如果只看最近几轮，系统就很容易：
- 一直跟着上一句往下走
- 忘掉早期重要主线
- 丢失全局目标

---

## 2. 这个项目里的记忆结构是怎么分层的

关键代码：
- [`app/services/coverage_service.py`](../app/services/coverage_service.py)
- [`app/services/context_engineering.py`](../app/services/context_engineering.py)
- [`app/services/repetition_guard.py`](../app/services/repetition_guard.py)

可以抽象成三层：

### 2.1 recent raw context

最近几轮保留更高 fidelity。

### 2.2 summarized historical memory

旧 answer 会压缩成 summary，不必保留全文。

### 2.3 structured retrieval memory

额外维护：
- branches
- framework gaps
- question_history

这才是比“仅截断历史”更强的地方。

---

## 3. 为什么“压缩”和“检索”必须一起设计

很多人只做压缩，不做检索。

结果是：
- 历史虽然更短了
- 但模型仍然不知道该看 summary 里的哪一块

真正有效的设计是：

1. 先压缩旧历史
2. 再用结构化状态决定该检索哪些片段

这个项目里，检索至少会参考：
- stage
- framework gaps
- branch priority
- novelty penalty
- recent question history

---

## 4. 这个项目的记忆压缩最值得学习的点

### 4.1 answer summary 不等于 transcript summary

它是面向后续编排使用的 compact evidence，而不是给用户看的摘要。

### 4.2 branch 是“主题簇”

branch 不是单轮 turn，而是对多个 turn 的主题聚合。

### 4.3 question_history 是“已问过什么”

这层记忆和 branch 不同，它服务的是去重和 novelty。

这三者组合起来，系统才不会只跟着最近一句跑。

---

## 5. 检索层为什么不能只靠 embedding

embedding 很有用，但它不是全部。

原因：

1. 它不懂阶段目标  
2. 它不懂 rubric gap  
3. 它不懂 human review  
4. 它不懂“这个 branch 最近已经问过很多轮了”  

所以更稳的结构是：

```text
rule-based structure + optional embedding refinement
```

而不是：

```text
一切都交给向量相似度
```

---

## 6. 如何自己设计一个可迁移的记忆压缩与检索系统

建议按这个顺序做：

### 第一步：先定义你到底要记住什么

例如：
- 已覆盖任务
- 未解决点
- 主题分支
- 最近动作历史

### 第二步：把旧历史压缩成可复用证据

例如：
- summary
- extracted facts
- action outcomes

### 第三步：再定义检索规则

例如：
- 当前阶段最缺什么
- 哪个 branch 优先
- 哪些 branch 近期不能再选

### 第四步：最后才考虑 embedding

embedding 应该是增强层，不是第一层。

---

## 7. 一个非常值得你做的练习

练习目标：
- 给 `question_history` 增加一个你自己定义的字段，例如：
  - `artifact_kind`

然后你再修改 planner / retrieval，让它在选 branch 时也考虑这个字段。

你会更清楚：
- 记忆结构一旦变了，规划和检索也会跟着变

---

## 8. 一句话总结

Agent 的长期记忆不是“把聊天历史塞进去”，而是：

**把历史压缩成结构化证据，再按当前目标做选择性检索。**
