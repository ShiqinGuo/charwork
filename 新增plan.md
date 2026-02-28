# 新增功能增量设计

## 1. 新增功能概述
在现有汉字管理系统基础上，新增**教学管理模块**，包含教师/学生用户体系、作业管理、作业提交、留言评论、消息收发功能。本次设计为增量方案，不修改原有汉字管理、导入导出等核心模块。

---

## 2. 新增技术栈与依赖
无需新增核心技术栈，复用现有 FastAPI + SQLAlchemy 2.0 Async + Celery + Redis 架构。

---

## 3. 新增数据模型设计

### 3.1 核心模型关系图
```
User (用户基表)
├── Teacher (教师扩展)
└── Student (学生扩展)

Assignment (作业) ←── Teacher (创建者)
    └── Submission (作业提交) ←── Student (提交者)

Comment (留言/评论) ──→ 关联 Assignment/Submission
Message (消息) ──→ User (收发双方)
```

### 3.2 新增表结构
ID统一采用雪花算法
#### （1）用户基表 `user`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 用户ID（雪花算法）  |
| `username`      | String(50)   | UNIQUE        | 用户名                   |
| `email`         | String(100)  | UNIQUE        | 邮箱                     |
| `hashed_password` | String(255) | NOT NULL      | 加密密码                 |
| `role`          | Enum         | NOT NULL      | 角色：`teacher`/`student`|
| `is_active`     | Boolean      | DEFAULT True  | 账号是否激活             |
| `created_at`    | DateTime     | DEFAULT now() | 创建时间                 |
| `updated_at`    | DateTime     | DEFAULT now() | 更新时间                 |

#### （2）教师扩展表 `teacher`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 教师ID                   |
| `user_id`       | String       | FOREIGN KEY   | 关联 `user.id`           |
| `name`          | String(50)   | NOT NULL      | 教师姓名                 |
| `department`    | String(100)  | NULLABLE      | 所属院系                 |
| `created_at`    | DateTime     | DEFAULT now() | 创建时间                 |

#### （3）学生扩展表 `student`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 学生ID                   |
| `user_id`       | String       | FOREIGN KEY   | 关联 `user.id`           |
| `name`          | String(50)   | NOT NULL      | 学生姓名                 |
| `class_name`    | String(50)   | NULLABLE      | 班级                     |
| `created_at`    | DateTime     | DEFAULT now() | 创建时间                 |

#### （4）作业表 `assignment`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 作业ID                   |
| `teacher_id`    | String       | FOREIGN KEY   | 关联 `teacher.id`        |
| `title`         | String(200)  | NOT NULL      | 作业标题                 |
| `description`   | Text         | NULLABLE      | 作业描述                 |
| `hanzi_ids`     | JSON         | NULLABLE      | 关联汉字ID列表 `[id1, id2]` |
| `due_date`      | DateTime     | NULLABLE      | 截止时间                 |
| `status`        | Enum         | DEFAULT `draft` | 状态：`draft`/`published`/`closed` |
| `created_at`    | DateTime     | DEFAULT now() | 创建时间                 |
| `updated_at`    | DateTime     | DEFAULT now() | 更新时间                 |

#### （5）作业提交表 `submission`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 提交ID                   |
| `assignment_id` | String       | FOREIGN KEY   | 关联 `assignment.id`     |
| `student_id`    | String       | FOREIGN KEY   | 关联 `student.id`        |
| `content`       | Text         | NULLABLE      | 文字内容                 |
| `image_paths`   | JSON         | NULLABLE      | 提交图片路径列表         |
| `status`        | Enum         | DEFAULT `submitted` | 状态：`submitted`/`graded` |
| `score`         | Integer      | NULLABLE      | 分数（0-100）            |
| `feedback`      | Text         | NULLABLE      | 教师反馈                 |
| `submitted_at`  | DateTime     | DEFAULT now() | 提交时间                 |
| `graded_at`     | DateTime     | NULLABLE      | 批改时间                 |

#### （6）留言/评论表 `comment`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 评论ID                   |
| `user_id`       | String       | FOREIGN KEY   | 评论者ID（关联 `user.id`） |
| `target_type`   | Enum         | NOT NULL      | 关联类型：`assignment`/`submission` |
| `target_id`     | String       | NOT NULL      | 关联对象ID               |
| `content`       | Text         | NOT NULL      | 评论内容                 |
| `created_at`    | DateTime     | DEFAULT now() | 创建时间                 |

#### （7）消息表 `message`
| 字段名          | 类型         | 约束          | 说明                     |
|-----------------|--------------|---------------|--------------------------|
| `id`            | String       | PRIMARY KEY   | 消息ID                   |
| `sender_id`     | String       | FOREIGN KEY   | 发送者ID（关联 `user.id`） |
| `receiver_id`   | String       | FOREIGN KEY   | 接收者ID（关联 `user.id`） |
| `title`         | String(200)  | NULLABLE      | 消息标题                 |
| `content`       | Text         | NOT NULL      | 消息内容                 |
| `is_read`       | Boolean      | DEFAULT False | 是否已读                 |
| `created_at`    | DateTime     | DEFAULT now() | 发送时间                 |

---

## 4. 新增目录结构
```
app/
  # 原有目录保持不变
  api/
    v1/
      # 新增路由
      routes_teachers.py
      routes_students.py
      routes_assignments.py
      routes_submissions.py
      routes_comments.py
      routes_messages.py
  models/
    # 新增模型
    user.py
    teacher.py
    student.py
    assignment.py
    submission.py
    comment.py
    message.py
  schemas/
    # 新增Schema
    user.py
    teacher.py
    student.py
    assignment.py
    submission.py
    comment.py
    message.py
  services/
    # 新增服务层
    user_service.py
    teacher_service.py
    student_service.py
    assignment_service.py
    submission_service.py
    comment_service.py
    message_service.py
  repositories/
    # 新增仓储层
    user_repo.py
    teacher_repo.py
    student_repo.py
    assignment_repo.py
    submission_repo.py
    comment_repo.py
    message_repo.py
  tasks/
    # 新增异步任务
    notification_tasks.py
```

---

## 5. 新增API接口设计

### 5.1 接口分组
| 路由前缀                | 说明                     |
|-------------------------|--------------------------|
| `/api/v1/teachers`      | 教师管理                 |
| `/api/v1/students`      | 学生管理                 |
| `/api/v1/assignments`   | 作业管理                 |
| `/api/v1/submissions`   | 作业提交与批改           |
| `/api/v1/comments`      | 留言/评论                |
| `/api/v1/messages`      | 消息收发                 |

### 5.2 核心接口示例
#### （1）作业管理
| 方法 | 路径                          | 说明                     |
|------|-------------------------------|--------------------------|
| POST | `/api/v1/assignments`         | 教师创建作业             |
| GET  | `/api/v1/assignments`         | 作业列表（教师/学生）    |
| GET  | `/api/v1/assignments/{id}`    | 作业详情                 |
| PUT  | `/api/v1/assignments/{id}`    | 更新作业                 |
| DELETE| `/api/v1/assignments/{id}`   | 删除作业                 |

#### （2）作业提交
| 方法 | 路径                          | 说明                     |
|------|-------------------------------|--------------------------|
| POST | `/api/v1/assignments/{id}/submissions` | 学生提交作业       |
| GET  | `/api/v1/assignments/{id}/submissions` | 查看作业提交列表   |
| GET  | `/api/v1/submissions/{id}`    | 提交详情                 |
| PUT  | `/api/v1/submissions/{id}/grade` | 教师批改作业         |

#### （3）消息收发
| 方法 | 路径                          | 说明                     |
|------|-------------------------------|--------------------------|
| POST | `/api/v1/messages`            | 发送消息                 |
| GET  | `/api/v1/messages`            | 消息列表（收/发件箱）    |
| PUT  | `/api/v1/messages/{id}/read`  | 标记已读                 |

---

## 6. 新增业务逻辑与分层设计

### 6.1 服务层核心职责
| 服务类               | 核心方法                                                                 |
|----------------------|--------------------------------------------------------------------------|
| `AssignmentService`  | 创建/发布作业、关联汉字、截止时间校验                                   |
| `SubmissionService`  | 提交作业（含图片上传）、自动触发消息通知、教师批改与分数校验           |
| `MessageService`     | 发送消息、批量标记已读、未读计数（Redis缓存）                          |
| `CommentService`     | 发表评论、关联目标对象权限校验                                           |

### 6.2 异步任务设计
在 `tasks/notification_tasks.py` 中新增：
- `send_submission_notification.delay(submission_id)`：学生提交作业后，异步通知教师
- `send_grade_notification.delay(submission_id)`：教师批改后，异步通知学生
- `batch_send_reminder.delay(assignment_id)`：作业截止前N小时，批量提醒未提交学生

---

## 7. 与现有系统的集成点
1. **汉字关联**：作业表 `hanzi_ids` 关联原有 `hanzi` 表，复用汉字查询逻辑
2. **文件存储**：作业提交图片复用现有 `uploads` 目录与文件处理工具
3. **异步框架**：新增通知任务复用现有 Celery + Redis 架构
4. **权限控制**：在现有依赖注入中新增 `get_current_teacher`/`get_current_student` 依赖

---

## 8. 验收标准
- 教师/学生用户注册、登录、信息管理功能正常
- 作业创建、发布、提交、批改全流程闭环
- 消息收发与已读状态实时更新
- 留言评论支持关联作业/提交记录
- 异步通知任务触发准确，无延迟或遗漏
- 所有新增接口通过压力测试（并发100+无异常）