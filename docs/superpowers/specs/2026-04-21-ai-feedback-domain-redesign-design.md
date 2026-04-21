# AI 反馈域重构设计文档

**日期**: 2026-04-21  
**范围**: 提交附件评价、学生主动 AI 总评、评价可见性与异步任务编排  
**目标**: 将当前提交级 `ai_feedback` 重构为以 AI 反馈为核心的独立模型，支持附件级评价、学生主动总评与后续业务扩展

---

## 1. 背景与问题

### 当前实现
- `Submission.ai_feedback` 使用 JSON 字段存储整次提交的 AI 评语
- AI 异步任务 `generate_ai_feedback(submission_id)` 以提交为单位处理
- 教师总评与分数存储在 `submission.score`、`submission.teacher_feedback`
- 提交图片已改为 `Attachment` 模型，`Submission` 通过 `attachment_ids` 关联附件

### 当前问题
- 评价粒度与附件模型不一致：实际评价对象是单张附件图片，但数据挂在提交上
- 触发策略不匹配：每次新增附件只应评价新增图片，而不是重扫整次提交
- 可见性混杂：附件级共享评价、学生私有 AI 总评、教师总评属于不同语义层
- 扩展性不足：未来若出现其他 AI 评价对象，继续堆在 `submission.ai_feedback` 会导致职责失衡

### 设计目标
- 以 AI 反馈为核心建模，而不是把反馈附着在某个单一业务表字段上
- 附件级 AI 评价以“单附件”为最小处理单元
- 学生可主动触发基于当前全部附件的 AI 总评，并且只保留最新结果
- 教师总评与分数继续作为提交主业务结果保留在 `submission`
- 为未来扩展不同反馈对象预留统一模型

---

## 2. 业务规则

### 2.1 评价类型
- `附件级 AI 评价`
  - 面向单个提交附件
  - 一张图片对应一条当前有效评价
  - 教师和学生都可见

- `学生 AI 总评`
  - 面向整次提交
  - 由学生主动点击触发
  - 只保留最新一条
  - 仅学生本人可见

- `教师总评与分数`
  - 面向整次提交
  - 继续存储于 `submission.score`、`submission.teacher_feedback`
  - 教师和学生都可见

### 2.2 触发规则
- 新增附件并成功关联到提交后，仅为新增附件触发一次附件级 AI 评价任务
- 更新提交时，已存在附件不重复自动重评
- 学生主动点击“生成 AI 总评”时，触发一次提交级 AI 总评任务
- 学生重复点击时覆盖旧总评，不保留历史版本

### 2.3 可见性规则
- 附件级 AI 评价：教师、学生可见
- 教师总评与分数：教师、学生可见
- 学生主动 AI 总评：仅学生本人可见，教师不可见

---

## 3. 数据模型设计

### 3.1 新增统一 `AIFeedback` 实体

建议新增独立表 `ai_feedback`，以 AI 反馈为核心统一承载不同业务对象的评价结果。

建议字段：
- `id`
- `management_system_id`
- `target_type`
- `target_id`
- `feedback_scope`
- `visibility_scope`
- `status`
- `generated_by`
- `result_payload`
- `created_at`
- `updated_at`

### 3.2 字段语义
- `target_type`
  - 当前值建议：
  - `submission_attachment`
  - `submission`

- `target_id`
  - 对应目标对象主键
  - 当 `target_type=submission_attachment` 时，对应 `attachment.id`
  - 当 `target_type=submission` 时，对应 `submission.id`

- `feedback_scope`
  - 区分同一对象上的不同反馈层级
  - 当前值建议：
  - `attachment_item`
  - `student_summary`

- `visibility_scope`
  - 当前值建议：
  - `shared_teacher_student`
  - `student_only`

- `status`
  - 当前值建议：
  - `pending`
  - `done`
  - `failed`

- `generated_by`
  - 当前值建议：
  - `system`
  - `student`

- `result_payload`
  - 使用 JSON 存储结构化内容
  - 附件级反馈与学生总评采用不同 payload 结构，但统一挂在该字段下

### 3.3 唯一性与当前有效记录

当前设计不保留历史版本，直接覆盖最新结果，因此建议通过唯一约束确保每个反馈槽位只有一条当前记录：

- 附件级 AI 评价：
  - 唯一键：`target_type + target_id + feedback_scope`
- 学生 AI 总评：
  - 唯一键：`target_type + target_id + feedback_scope`

这两个场景虽然都是同一组唯一键，但依靠不同 `target_type` 与 `feedback_scope` 实现隔离。

### 3.4 现有 `Submission` 字段策略
- `submission.ai_feedback`
  - 不再作为新功能主存储
  - 短期保留，仅作为兼容字段
  - 新接口不再依赖该字段读取

- `submission.score`
  - 继续保留

- `submission.teacher_feedback`
  - 继续保留

---

## 4. 结果结构设计

### 4.1 附件级 AI 评价 `result_payload`

建议结构：

```json
{
  "attachment_id": "att_001",
  "char": "永",
  "stroke_score": 7,
  "structure_score": 8,
  "overall_score": 6,
  "summary": "笔画较清晰，结构略松散。"
}
```

说明：
- 一条附件反馈对应一张图片，不再使用 `items[]`
- 单附件天然不需要 `image_index`
- 若未来需要保存 OCR 原始结果，可追加 `ocr_text` 等字段

### 4.2 学生 AI 总评 `result_payload`

建议结构：

```json
{
  "submission_id": "sub_001",
  "attachment_count": 3,
  "summary": "整体书写较稳定，结构把控较好，但个别字重心偏移。",
  "strengths": ["笔画基本清楚", "结构感较好"],
  "improvements": ["部分字重心不稳", "个别起笔较弱"],
  "overall_level": "良好"
}
```

说明：
- 总评不重复存储每张附件的详细分项结果
- 其输入来源于当前提交下所有附件的最新附件级 AI 评价

---

## 5. 服务与模块边界

### 5.1 新增 `AIFeedbackRepository`

职责：
- 按目标对象读取 AI 反馈
- 按唯一槽位创建或覆盖反馈
- 按身份与可见性过滤反馈

核心能力：
- `upsert_feedback()`
- `get_feedback_by_target()`
- `get_visible_feedbacks()`

### 5.2 拆分现有 AI 服务

当前 [ai_feedback_service.py](file:///d:/mywork/charwork/app/services/ai_feedback_service.py) 同时承担“提交流程读取 + 多图处理 + 写提交 JSON”的职责，建议拆为以下服务：

- `AttachmentAIFeedbackService`
  - 面向单附件生成评价
  - 负责 OCR、视觉模型调用、写入附件级反馈

- `SubmissionAISummaryService`
  - 面向整次提交生成学生总评
  - 负责汇总当前提交所有附件的最新附件级反馈
  - 生成并覆盖学生可见总评

- `AIFeedbackVisibilityService` 或查询层统一方法
  - 根据当前身份裁剪可见数据

### 5.3 保持 `SubmissionService` 聚焦业务主流程

`SubmissionService` 继续负责：
- 提交创建、更新
- 附件关联
- 教师评分与教师总评

`SubmissionService` 不再直接承载“整次提交 AI 评价生成”的细节，只负责在合适时机调度异步任务。

---

## 6. 异步任务设计

### 6.1 附件级 AI 评价任务

建议新增或替换为：
- `generate_attachment_ai_feedback(attachment_id: str)`

任务职责：
- 根据 `attachment_id` 读取附件
- 校验该附件是否已归属于某次提交
- 调用 `AttachmentAIFeedbackService` 生成单附件评价
- 将结果写入 `ai_feedback` 表对应槽位

触发时机：
- 新附件关联到提交后立即触发

幂等策略：
- 同一 `attachment_id` 重复执行时覆盖旧记录
- 不生成历史版本

### 6.2 学生主动 AI 总评任务

建议新增：
- `generate_submission_ai_summary(submission_id: str, student_user_id: str)`

任务职责：
- 读取提交当前所有附件
- 获取这些附件当前最新的附件级 AI 评价
- 如存在未完成或失败附件评价，采用明确策略处理
- 生成仅学生可见的总评并覆盖旧记录

推荐策略：
- 默认只基于已完成的附件级评价生成总评
- 若一张都没有完成，返回 `failed` 或业务提示“暂无可汇总的附件评价”

### 6.3 任务调度原则
- 提交创建或更新时：
  - 只调度新增附件的附件级 AI 评价
  - 不自动调度学生总评

- 学生主动点击时：
  - 只调度学生总评任务

- 教师评分时：
  - 不触发 AI 总评重算

---

## 7. 接口设计

### 7.1 提交详情接口

保留 [routes_submissions.py](file:///d:/mywork/charwork/app/api/v1/routes_submissions.py) 的提交详情主接口，继续返回：
- 提交基础信息
- 附件列表
- 教师总评
- 教师分数

不再把 AI 反馈主数据继续耦合到 `SubmissionResponse.ai_feedback`。

### 7.2 附件级 AI 评价查询接口

建议新增：
- `GET /submissions/{id}/attachment-feedbacks`

返回：
- 当前提交下所有附件的当前有效 AI 评价

权限：
- 学生：只能访问自己的提交
- 教师：可访问其有权限查看的学生提交

### 7.3 学生 AI 总评接口

建议新增：
- `POST /submissions/{id}/ai-summary`
  - 仅学生可调用
  - 触发异步总评生成

- `GET /submissions/{id}/ai-summary`
  - 仅学生可调用
  - 返回当前最新学生 AI 总评

### 7.4 现有 `GET /submissions/{id}/ai-feedback`

建议迁移策略：
- 短期保留但降级为兼容接口
- 明确标记废弃
- 不再作为新模型主入口

---

## 8. 可见性与权限控制

### 8.1 控制原则
- 可见性必须由后端查询层强制执行，不能只依赖前端隐藏
- 查询 `AIFeedback` 时必须同时判断：
  - 当前身份
  - 目标对象归属
  - `visibility_scope`

### 8.2 查询规则
- 教师查询：
  - 可获取 `shared_teacher_student`
  - 不可获取 `student_only`

- 学生查询本人提交：
  - 可获取 `shared_teacher_student`
  - 可获取 `student_only`

---

## 9. 状态流转

### 9.1 附件级 AI 评价
- `pending -> done`
- `pending -> failed`

### 9.2 学生 AI 总评
- `pending -> done`
- `pending -> failed`

### 9.3 与提交状态解耦
- AI 反馈状态不驱动 `submission.status`
- 附件级评价失败不会导致提交失败
- 学生总评失败不会改变提交业务状态

原因：
- 提交状态表示主业务流程
- AI 反馈属于派生能力，不能反向污染主状态机

---

## 10. 兼容与迁移

### 10.1 兼容策略
- 保留 `submission.ai_feedback` 字段，避免立即破坏旧代码
- 新写路径全部写入 `ai_feedback` 新表
- 新读路径优先读取 `ai_feedback` 新表

### 10.2 历史数据策略

可选两种：

- `策略 A：不迁移旧数据`
  - 新功能只对未来新附件和新生成总评生效
  - 成本最低

- `策略 B：迁移旧 submission.ai_feedback`
  - 将旧 `items[]` 转换为附件级反馈
  - 仅在能可靠映射旧图片与当前附件时使用

推荐：
- 先使用 `策略 A`
- 待新模型稳定后，再评估是否需要迁移历史数据

---

## 11. 实施顺序

建议分三步落地：

1. 新增 `AIFeedback` 模型、仓储与查询接口
2. 将附件上传后的异步任务改为 `attachment_id` 驱动
3. 新增学生主动生成与查询 AI 总评能力

这样可以先稳定附件级评价，再逐步接入总评功能，降低一次性变更风险。

---

## 12. 测试重点

- 新增附件后，仅新增附件触发 AI 评价任务
- 同一附件重复触发任务时，覆盖当前记录而不是新增多条有效记录
- 学生主动生成总评时，同一提交仅保留一条最新总评
- 教师可见附件级 AI 评价，但不可见学生私有总评
- 学生可见附件级 AI 评价、教师总评/分数、自己的 AI 总评
- 旧 `submission.ai_feedback` 不再被新链路写入

---

## 13. 取舍说明

### 为什么不继续使用 `submission.ai_feedback`
- 它无法清晰表达附件级与提交级两个层次
- 它难以表达不同可见性
- 它不利于未来扩展到更多 AI 反馈对象

### 为什么不把附件评价挂到 `Attachment` 表 JSON 字段
- 查询、筛选、权限控制与后续扩展都会越来越困难
- AI 反馈是独立业务对象，应该拥有自己的状态和生命周期

### 为什么教师总评不并入 `AIFeedback`
- 教师总评是主业务结果，不是模型派生结果
- 继续保留在 `submission` 上更符合业务语义，也更稳定
