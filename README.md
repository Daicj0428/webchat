# Web Chat with File Operations

一个基于Flask和DeepSeek API的Web聊天应用，支持实时对话和文件操作功能。

## 项目概述

这是一个功能丰富的聊天应用，具有以下特点：
- Web界面聊天（支持Markdown渲染）
- 本地交互模式（命令行）
- 文件操作功能（读取、写入、删除、列出文件等）
- 对话历史管理
- 会话管理

## 项目结构

```
scripts/
├── app.py              # 主应用文件（Flask服务器）
├── deepseek_api.py     # DeepSeek API接口
├── templates/
   └── index.html      # Web聊天界面
```

## 功能特性

### 1. Web聊天模式
- 实时流式响应
- Markdown格式支持
- 代码复制功能
- 会话历史保存
- 多会话管理

### 2. 本地交互模式
- 命令行界面
- 连续对话
- 文件操作集成
- 对话日志记录

### 3. 文件操作功能
- 读取文件内容
- 创建/覆盖文件
- 追加文件内容
- 删除文件
- 列出目录内容
- 创建目录
- 切换工作目录

## 安装与配置

### 环境要求
- Python 3.7+
- Flask 2.0+
- Flask-SocketIO
- DeepSeek API密钥

### 安装步骤

1. 克隆或下载项目
2. 安装依赖：

```bash
pip install flask flask-socketio
```

3. 配置DeepSeek API密钥：
   在 `deepseek_api.py` 中设置你的API密钥

## 使用方法

### 启动Web服务器

```bash
python app.py
```

服务器将在 `http://0.0.0.0:21048` 启动

### 使用本地交互模式

```bash
python app.py --local
```

可选参数：
- `--local`：启用本地交互模式
- `--output <file>`：指定对话日志输出文件（默认：webchat.log）
- `--dir <path>`：指定工作目录（文件操作的基础路径）

### 文件操作命令（本地模式）

在本地交互模式中，输入 `file` 进入文件操作模式：

```
基础命令:
  pwd                        显示当前目录
  cd <目录>                  切换到指定目录
  ls [目录]                  列出当前目录或指定目录的文件
  mkdir <目录>               创建目录

文件操作:
  read <文件>                读取文件内容
  write <文件>               写入文件（覆盖模式，需要多行输入）
  append <文件>              追加内容到文件（需要多行输入）
  delete <文件>              删除文件

选项:
  ls -r [目录]               递归列出所有文件
  ls -a [目录]               显示隐藏文件
  read <文件> -g <编码>      指定编码读取文件（如gbk）
```

### AI驱动的文件操作

在聊天中，AI可以自动执行文件操作：

```
用户：读取app.py文件
AI：[TOOL_CALL] READ_FILE path="app.py"

用户：创建README文件
AI：[TOOL_CALL] WRITE_FILE path="README.md" content="# 项目说明\
\
这是项目..."

用户：列出当前目录
AI：[TOOL_CALL] LIST_FILES path="."
```

## API接口

### WebSocket端点
- `ws://localhost:21048/socket.io` - WebSocket连接

### 消息格式

发送消息：
```json
{
  "content": "用户消息",
  "context": [
    {"role": "user", "content": "历史消息1"},
    {"role": "assistant", "content": "历史回复1"}
  ],
  "session_id": "会话ID"
}
```

接收消息：
```json
{
  "type": "stream" | "start" | "end" | "error",
  "content": "消息内容",
  "session_id": "会话ID"
}
```

## 配置说明

### 主要配置文件

1. **app.py** - 主应用配置
   - Flask应用设置
   - SocketIO配置
   - 文件管理器设置
   - 对话历史管理

2. **deepseek_api.py** - API配置
   - DeepSeek API密钥
   - 模型参数
   - 流式响应设置

### 环境变量

建议设置以下环境变量：
```bash
export FLASK_SECRET="your-secret-key"
export DEEPSEEK_API_KEY="your-api-key"
```

## 开发指南

### 添加新功能

1. **添加新的文件操作工具**：
   - 在 `FileManager` 类中添加新方法
   - 在 `execute_tool_call` 函数中添加处理逻辑
   - 更新AI系统提示

2. **扩展聊天功能**：
   - 修改 `process_local_input` 函数
   - 更新WebSocket消息处理
   - 扩展对话历史管理

### 调试技巧

1. 启用详细日志：
```python
# 在app.py中设置
socketio = SocketIO(app, logger=True, engineio_logger=True)
```

2. 检查文件操作权限
3. 验证API密钥有效性
4. 查看浏览器控制台日志

## 故障排除

### 常见问题

1. **WebSocket连接失败**
   - 检查防火墙设置
   - 验证端口21048是否可用
   - 检查SocketIO版本兼容性

2. **API调用失败**
   - 验证DeepSeek API密钥
   - 检查网络连接
   - 查看API配额限制

3. **文件操作权限错误**
   - 检查工作目录权限
   - 验证文件路径安全性
   - 确保目录存在

4. **编码问题**
   - 使用 `-g` 参数指定编码
   - 确保文件使用UTF-8编码
   - 处理特殊字符

### 日志文件

- `webchat.log` - 对话日志（本地模式）
- Flask应用日志 - 服务器运行日志
- 浏览器控制台 - Web客户端日志

## 安全注意事项

1. **API密钥安全**
   - 不要将API密钥提交到版本控制
   - 使用环境变量存储敏感信息
   - 定期轮换API密钥

2. **文件操作安全**
   - 限制文件操作范围到工作目录
   - 验证所有文件路径
   - 防止目录遍历攻击

3. **Web安全**
   - 在生产环境使用HTTPS
   - 设置强密钥
   - 限制CORS来源

## 性能优化

### 内存管理
- 限制对话历史长度
- 定期清理旧会话
- 使用流式响应减少内存占用

### 响应速度
- 启用缓存
- 优化文件操作
- 使用异步处理

## 扩展计划

### 计划功能
1. 用户认证系统
2. 文件上传/下载
3. 数据库支持（SQLite/PostgreSQL）
4. 多模型支持（OpenAI、Claude等）
5. 插件系统
6. 移动端适配

### 技术栈升级
1. 迁移到FastAPI
2. 添加TypeScript支持
3. 实现微服务架构
4. 容器化部署（Docker）

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 查看项目文档

---

**提示**：首次运行前，请确保已正确配置DeepSeek API密钥。
