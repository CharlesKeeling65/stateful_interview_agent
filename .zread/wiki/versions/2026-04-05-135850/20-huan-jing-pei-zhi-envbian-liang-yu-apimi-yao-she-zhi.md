本页面将指导您完成状态化访谈Agent的运行环境配置。我们将详细讲解所有必需的`.env`环境变量、它们的作用，以及如何正确设置API密钥以确保应用正常运行。

## 为什么需要环境变量？

环境变量是配置应用程序的标准方式，它们允许您将敏感信息（如API密钥）与代码分离，从而实现：

- **安全性**：敏感凭证不会提交到版本控制系统
- **灵活性**：不同环境（开发、测试、生产）使用不同配置
- **便捷性**：无需修改代码即可切换服务提供商

本项目使用[pydantic-settings](https://docs.pydantic.dev/latest/api/pydantic_settings/)库加载环境变量，它会自动从`.env`文件读取配置并提供类型验证功能。

Sources: [app/core/config.py](app/core/config.py#L1-L34), [pyproject.toml](pyproject.toml#L1-L25)

## 配置文件详解

### 第一步：复制示例配置文件

项目根目录提供了`.env.示例`文件，您需要将其复制为`.env`文件：

```bash
cp .env.example .env
```

复制后，使用文本编辑器打开`.env`文件，根据您的实际需求修改各项配置。

Sources: [.env.example](.env.example#L1-L8)

### 环境变量完整清单

下表列出了所有可用的环境变量，按功能分组说明：

| 变量分类 | 变量名 | 必需 | 默认值 | 说明 |
|---------|--------|------|--------|------|
| **应用基础** | `APP_NAME` | 否 | `Stateful Interview Agent` | 应用显示名称 |
| | `APP_ENV` | 否 | `dev` | 运行环境标识（dev/prod） |
| **日志配置** | `LOG_LEVEL` | 否 | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| | `LOG_DIR` | 否 | `./logs` | 日志文件存储目录 |
| | `LOG_LLM_PAYLOADS` | 否 | `True` | 是否记录LLM请求详情 |
| | `LOG_ARTIFACTS_ENABLED` | 否 | `False` | 是否保存大型工件 |
| **LLM配置** | `OPENAI_API_KEY` | **是** | 无 | OpenAI兼容API密钥 |
| | `OPENAI_BASE_URL` | 否 | `https://api.scnet.cn/api/llm/v1` | API端点URL |
| | `OPENAI_MODEL` | 否 | `MiniMax-M2.5` | 主模型名称 |
| | `OPENAI_EMBEDDING_MODEL` | 否 | 无 | 向量嵌入模型（可选） |
| **重复检测** | `DUPLICATE_GUARD_USE_EMBEDDINGS` | 否 | `false` | 是否使用embedding检测重复 |
| | `DUPLICATE_GUARD_EMBEDDING_THRESHOLD` | 否 | `0.9` | 相似度阈值（0-1） |
| **访谈配置** | `INTERVIEW_MIN_TURNS` | 否 | `35` | 最小访谈轮次 |
| | `INTERVIEW_MAX_TURNS` | 否 | `40` | 最大访谈轮次 |
| **数据库** | `DATABASE_URL` | 否 | `sqlite:///./data/app.db` | 数据库连接字符串 |

Sources: [app/core/config.py](app/core/config.py#L1-L34), [.env.example](.env.example#L1-L8)

## 核心配置详解

### LLM API配置

这是最关键的配置项，决定了应用能否正常调用大语言模型服务。

```bash
# OpenAI API密钥（必需）
OPENAI_API_KEY=your_actual_api_key_here

# API端点URL - 支持OpenAI兼容的任何服务
OPENAI_BASE_URL=https://api.scnet.cn/api/llm/v1

# 使用的模型名称
OPENAI_MODEL=MiniMax-2.5
```

配置加载后，系统会在初始化`OpenAI`客户端时使用这些参数：

```python
# app/core/llm_client.py 中的实现
def get_openai_client() -> OpenAI:
    client_kwargs = {
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_base_url,
    }
    return OpenAI(**client_kwargs)
```

Sources: [app/core/llm_client.py](app/core/llm_client.py#L1-L33), [app/core/config.py](app/core/config.py#L13-L17)

### 数据库配置

项目默认使用SQLite作为数据库，适合本地开发：

```bash
DATABASE_URL=sqlite:///./data/app.db
```

首次启动时，应用会自动创建数据库文件并初始化表结构。如果使用其他数据库（如PostgreSQL），只需修改连接字符串：

```bash
# PostgreSQL示例
DATABASE_URL=postgresql://user:password@localhost:5432/interview_agent
```

数据库初始化逻辑如下：

```python
# app/core/database.py
engine = create_engine(settings.database_url)
Base = declarative_base()

def ensure_database_schema():
    Base.metadata.create_all(bind=engine)
    # 自动执行迁移，添加新字段
```

Sources: [app/core/database.py](app/core/database.py#L1-L30)

### 日志配置

日志系统默认将JSON格式的日志输出到`./logs`目录，按日期和类别分组存储：

```bash
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_LLM_PAYLOADS=true    # 记录完整的LLM请求/响应
LOG_ARTIFACTS_ENABLED=false
```

日志采用JSONL格式输出，便于后续分析和检索：

Sources: [.env.example](.env.example#L1-L8), [app/logger/config.py](app/logger/config.py#L1-L56)

## 配置流程图

以下流程图展示了环境配置在应用启动过程中的位置：

```mermaid
flowchart TD
    A[应用启动] --> B[加载 .env 文件]
    B --> C{pydantic-settings 解析}
    C -->|验证通过| D[初始化数据库连接]
    C -->|验证失败| E[抛出配置错误]
    D --> F[配置日志系统]
    F --> G[初始化LLM客户端]
    G --> H[启动FastAPI服务]
    
    style A fill:#e1f5fe
    style B fill:#fff3e0
    style G fill:#e8f5e9
    style H fill:#f3e5f5
```

## 完整配置示例

以下是一个典型的开发环境配置文件：

```bash
# ========== 应用基础配置 ==========
APP_NAME=Stateful Interview Agent
APP_ENV=dev

# ========== 日志配置 ==========
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_LLM_PAYLOADS=true
LOG_ARTIFACTS_ENABLED=false

# ========== LLM API配置（关键） ==========
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.scnet.cn/api/llm/v1
OPENAI_MODEL=MiniMax-2.5

# ========== 重复检测配置 ==========
DUPLICATE_GUARD_USE_EMBEDDINGS=false

# ========== 访谈配置 ==========
INTERVIEW_MIN_TURNS=35
INTERVIEW_MAX_TURNS=40

# ========== 数据库配置 ==========
DATABASE_URL=sqlite:///./data/app.db
```

## 常见问题排查

### 问题1：提示"OPENAI_API_KEY is required"

这是最常见的错误，表示您未设置API密钥。解决步骤：

1. 确认`.env`文件已创建在项目根目录
2. 检查密钥格式是否正确（不应包含多余空格）
3. 验证文件编码为UTF-8

```bash
# 检查文件是否存在
ls -la .env

# 检查内容（注意不要泄露密钥）
head -3 .env
```

### 问题2：无法连接LLM API

如果您能启动应用但调用LLM时出错：

1. 确认`OPENAI_BASE_URL`正确（不同服务提供商URL不同）
2. 检查网络能否访问该URL
3. 验证API密钥是否有效且未过期

### 问题3：数据库初始化失败

如果看到数据库相关错误：

1. 确认`./data`目录存在且有写入权限
2. 如果使用SQLite，检查路径格式（需要三个斜杠`///`）
3. 对于其他数据库类型，确认数据库服务器已启动

### 问题4：日志文件未生成

检查以下配置：

1. `LOG_DIR`指定的目录是否有写入权限
2. `LOG_LEVEL`是否设置正确（设为DEBUG可获取更多信息）

Sources: [app/core/config.py](app/core/config.py#L1-L34), [app/core/llm_client.py](app/core/llm_client.py#L1-L33), [app/core/database.py](app/core/database.py#L1-L30)

## 下一步

配置完成后，您可以继续以下操作：

1. **启动后端服务** - 参考 [快速启动：5分钟搭建本地开发环境](2-kuai-su-qi-dong-5fen-zhong-da-jian-ben-di-kai-fa-huan-jing)
2. **了解后端架构** - 阅读 [后端架构概览：FastAPI + SQLAlchemy + LangGraph](5-hou-duan-jia-gou-gai-lan-fastapi-sqlalchemy-langgraph)
3. **配置前端** - 查看 [React前端架构：组件与状态管理](19-reactqian-duan-jia-gou-zu-jian-yu-zhuang-tai-guan-li)

如果您使用的是不同的LLM服务提供商，请确保其API与OpenAI兼容，否则可能需要修改`app/core/llm_client.py`中的客户端初始化逻辑。