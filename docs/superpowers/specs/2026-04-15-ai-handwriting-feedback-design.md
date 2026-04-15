# AI 手写体评语功能设计文档

**日期**：2026-04-15  
**状态**：已确认

---

## 背景

书法教学管理系统已有手写 OCR 识别能力（百度 OCR）和 AI 对话服务（火山引擎 Ark）。  
本功能目标：学生提交单字手写作业后，系统自动调用多模态大模型生成结构化 AI 评语，教师可独立补充自己的评语，两者分开存储展示。

---

## 方案选型

采用 **OCR + 多模态双输入** 方案：将图片（base64）和 OCR 识别文字同时发给 Ark 视觉模型。  
OCR 文字作为"锚点"补偿视觉模型对笔画细节理解不稳定的问题，复用现有 Celery 基础设施，工程成本最低。

---

## 数据层

### Submission 模型变更

新增两个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ai_feedback` | JSON, nullable | AI 生成的结构化评语 |
| `teacher_feedback` | Text, nullable | 教师独立评语（原 `feedback` 字段重命名） |

原 `feedback` 字段重命名为 `teacher_feedback`，`score` 字段保留给教师打分。

### ai_feedback JSON 结构

`image_paths` 是列表，每张图片对应一个汉字，`ai_feedback` 存储与 `image_paths` 等长的列表，按索引对应。

```json
{
  "status": "done",
  "generated_at": "2026-04-15T10:00:00",
  "items": [
    {
      "image_index": 0,
      "char": "永",
      "stroke_score": 7,
      "structure_score": 8,
      "overall_score": 6,
      "summary": "横画起笔较重，收笔略显仓促..."
    }
  ]
}
```

`status` 枚举值：`pending` | `done` | `failed`  
`items` 为空列表时表示无可评内容（如图片为空）。

---

## 服务层

### 触发链路

```
学生提交 → SubmissionService.create_submission()
         → Celery task: generate_ai_feedback.delay(submission_id)
```

提交主流程不等待 AI 生成，异步解耦。

### AIFeedbackService

新增独立服务类，职责：

1. 从 DB 取 `submission`，读取 `image_paths`（单字图片）
2. 调用现有 `OCRService.recognize_image()` 获取识别文字
3. 将图片转 base64 + OCR 文字组装 Prompt，调用 Ark 视觉模型
4. 解析 JSON 响应，写入 `submission.ai_feedback`（status=done）
5. 任意步骤失败时写 `{"status": "failed"}`，静默处理，不影响主流程

### Prompt 结构

```
你是书法评审专家。图片是一个学生手写的汉字"[OCR识别字]"。
请从以下三个维度评分（1-10分）并给出总评：
- stroke_score：笔画质量（起收笔、粗细变化）
- structure_score：结构布局（间架比例、重心）
- overall_score：整体气韵
以 JSON 格式返回，不要输出其他内容。
```

---

## API 层

### 新增接口

```
GET  /api/v1/submissions/{id}/ai-feedback
```
返回 `ai_feedback` 字段，前端可轮询 `status` 字段判断生成状态。

```
POST /api/v1/submissions/{id}/teacher-feedback
Body: { "teacher_feedback": "string", "score": int }
```
教师独立保存评语和分数，不覆盖 `ai_feedback`。

### 保留接口

原 `POST /api/v1/submissions/{id}/grade` 保留，`feedback` 参数语义对应 `teacher_feedback`。

---

## 前端展示

- AI 评语区块与教师评语区块独立展示，互不干扰
- AI 评语区块根据 `status` 显示三种状态：生成中 / 已生成 / 生成失败
- 教师评语区块始终可编辑

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| Ark 视觉模型调用失败 | 写 `status=failed`，不重试，不抛异常 |
| JSON 解析失败 | 写 `status=failed`，记录日志 |
| OCR 识别为空 | Prompt 中标注"字符未识别"，仍发送图片继续生成 |
| submission 不存在 | Celery task 静默退出 |
