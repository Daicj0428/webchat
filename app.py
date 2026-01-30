from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from deepseek_api import deepseek1
from datetime import datetime
import uuid
from flask import request
import os
import argparse
import json
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
# app.config['SECRET_KEY'] =  os.getenv('FLASK_SECRET', 'dev-secret-key')

socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   logger=False,
                   engineio_logger=False,
                   log_output=True)


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(data):
    # 获取客户端会话ID，如果没有则生成一个
    session_id = data.get('session_id', str(uuid.uuid4()))
    client_ip = request.remote_addr

    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 打印带会话信息的用户消息
    user_message = data.get('content', '')
    if user_message:
        print(f"\n[{current_time}] [会话ID: {session_id}] [客户端IP: {client_ip}] [用户消息] {user_message}\n")
    
    api_messages = data.get('context', [])
    
    # 发送开始标记（包含会话ID）
    emit('message', {'type': 'start', 'content': '', 'session_id': session_id})
    
    full_response = ""
    try:
        for chunk in deepseek1(api_messages):
            if chunk:
                full_response += chunk
                # 实时发送到前端（包含会话ID）
                emit('message', {
                    'type': 'stream',
                    'content': chunk.replace('\n', '\n'),
                    'session_id': session_id
                })
                
    except Exception as e:
        print(f"\n[{current_time}] [会话ID: {session_id}] [错误] {str(e)}\n")
        emit('message', {
            'type': 'error',
            'content': f"处理出错: {str(e)}",
            'session_id': session_id
        })
    
    # 发送结束标记（包含会话ID）
    emit('message', {'type': 'end', 'content': '', 'session_id': session_id})
    
    # 打印带会话信息的完整AI响应
    if full_response:
        print(f"\n[{current_time}] [会话ID: {session_id}] [AI完整响应]")
        print("-"*50)
        print(full_response)
        print("-"*50 + "\n")
    
    # 保存完整响应（包含会话ID）
    emit('message', {
        'type': 'full',
        'content': full_response,
        'session_id': session_id
    })

# 新增对话历史管理类
class ConversationHistory:
    def __init__(self, session_id=None):
        self.session_id = session_id or str(uuid.uuid4())
        self.messages = []
        self.last_modified = datetime.now()
    
    def add_user_message(self, content):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        self.last_modified = datetime.now()
    
    def add_assistant_message(self, content):
        """添加AI回复"""
        self.messages.append({"role": "assistant", "content": content})
        self.last_modified = datetime.now()
    
    def get_context(self, max_tokens=None):
        """获取对话上下文（自动截断过长的历史）"""
        # TODO: max_tokens 参数暂未使用，可以基于 token 数量截断
        # 简单实现：保留最近的N条消息
        return self.messages[-10:]  # 保留最近10轮对话
    
    def save(self, file_path):
        """保存对话历史到文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": self.session_id,
                "messages": self.messages,
                "last_modified": self.last_modified.isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, file_path):
        """从文件加载对话历史"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                history = cls(data.get("session_id"))
                history.messages = data.get("messages", [])
                history.last_modified = datetime.fromisoformat(data["last_modified"])
                return history
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        
def sanitize_path(path):
    """清理路径中的不可见Unicode字符"""
    # 移除所有不可见控制字符
    cleaned_path = re.sub(r'[\x00-\x1F\x7F-\x9F\u202A-\u202E]', '', path)
    # 移除路径开头和结尾的空白字符
    return cleaned_path.strip()


# 文件操作管理类
class FileManager:
    def __init__(self, base_dir=None):
        """初始化文件管理器，base_dir为工作目录（默认为当前工作目录）"""
        self.base_dir = base_dir if base_dir else os.getcwd()
        self.current_dir = self.base_dir
        print(f"[文件管理器] 工作目录: {self.base_dir}")

    def _resolve_path(self, path):
        """解析相对路径为绝对路径"""
        if os.path.isabs(path):
            resolved = path
        else:
            resolved = os.path.join(self.current_dir, path)
        
        # 规范化路径（处理反斜杠和相对路径）
        resolved = os.path.normpath(resolved)
        return sanitize_path(resolved)

    def _is_safe_path(self, path):
        """检查路径是否在工作目录范围内（安全检查）"""
        try:
            resolved = os.path.realpath(path)
            base_real = os.path.realpath(self.base_dir)
            return resolved.startswith(base_real)
        except:
            return False

    def read_file(self, file_path, encoding='utf-8'):
        """读取文件内容"""
        try:
            resolved_path = self._resolve_path(file_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            if not os.path.exists(resolved_path):
                return f"[ERROR] File not found: {resolved_path}"
            
            if os.path.isdir(resolved_path):
                return f"[ERROR] Path is a directory, not a file: {resolved_path}"
            
            with open(resolved_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            # 使用更清晰的格式返回文件内容
            return f"[FILE_CONTENT] {resolved_path}\n{'='*60}\n{content}\n{'='*60}"
        
        except PermissionError:
            return f"[ERROR] No read permission: {resolved_path}"
        except UnicodeDecodeError:
            return f"[ERROR] File encoding not supported (try utf-8 or gbk): {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to read file: {str(e)}"

    def write_file(self, file_path, content, encoding='utf-8'):
        """写入文件内容（创建或覆盖）"""
        try:
            resolved_path = self._resolve_path(file_path)
            
            # 检查路径是否为空
            if not resolved_path:
                return f"[ERROR] File path is empty"
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            # 检查路径是否是目录
            if os.path.exists(resolved_path) and os.path.isdir(resolved_path):
                return f"[ERROR] Path is a directory, not a file: {resolved_path}. Did you mean to write a file inside this directory?"
            
            # 确保目录存在
            dir_path = os.path.dirname(resolved_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            with open(resolved_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            return f"[SUCCESS] File written successfully: {resolved_path}"
        
        except PermissionError:
            return f"[ERROR] No write permission: {resolved_path}"
        except IsADirectoryError:
            return f"[ERROR] Path is a directory: {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to write file: {str(e)} (path: {resolved_path})"

    def append_file(self, file_path, content, encoding='utf-8'):
        """追加内容到文件"""
        try:
            resolved_path = self._resolve_path(file_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            if not os.path.exists(resolved_path):
                return f"[ERROR] File not found (append mode): {resolved_path}"
            
            with open(resolved_path, 'a', encoding=encoding) as f:
                f.write(content)
            
            return f"[SUCCESS] Content appended to: {resolved_path}"
        
        except PermissionError:
            return f"[ERROR] No write permission: {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to append to file: {str(e)}"

    def delete_file(self, file_path):
        """删除文件"""
        try:
            resolved_path = self._resolve_path(file_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            if not os.path.exists(resolved_path):
                return f"[ERROR] File not found: {resolved_path}"
            
            if os.path.isdir(resolved_path):
                return f"[ERROR] Path is a directory: {resolved_path}"
            
            os.remove(resolved_path)
            return f"[SUCCESS] File deleted: {resolved_path}"
        
        except PermissionError:
            return f"[ERROR] No delete permission: {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to delete file: {str(e)}"

    def list_files(self, dir_path='.', show_hidden=False, recursive=False):
        """列出目录下的文件"""
        try:
            resolved_path = self._resolve_path(dir_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            if not os.path.exists(resolved_path):
                return f"[ERROR] Directory not found: {resolved_path}"
            
            if not os.path.isdir(resolved_path):
                return f"[ERROR] Path is not a directory: {resolved_path}"
            
            result = [f"[DIR_LIST] {resolved_path}\n{'='*60}"]
            
            if recursive:
                for root, dirs, files in os.walk(resolved_path):
                    # 过滤隐藏文件
                    if not show_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                        files = [f for f in files if not f.startswith('.')]
                    
                    for item in sorted(dirs + files):
                        item_path = os.path.join(root, item)
                        rel_path = os.path.relpath(item_path, self.base_dir)
                        item_type = 'DIR' if os.path.isdir(item_path) else 'FILE'
                        size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                        size_str = f"{size:,} bytes" if os.path.isfile(item_path) else ''
                        result.append(f"[{item_type}] [{size_str:>12}] {rel_path}")
            else:
                items = os.listdir(resolved_path)
                if not show_hidden:
                    items = [item for item in items if not item.startswith('.')]
                
                for item in sorted(items):
                    item_path = os.path.join(resolved_path, item)
                    item_type = 'DIR' if os.path.isdir(item_path) else 'FILE'
                    size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                    size_str = f"{size:,} bytes" if os.path.isfile(item_path) else ''
                    result.append(f"[{item_type}] [{size_str:>12}] {item}")
            
            return '\n'.join(result) if len(result) > 1 else f"[DIR] {resolved_path} (empty)"
        
        except PermissionError:
            return f"[ERROR] No access permission: {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to list directory: {str(e)}"

    def create_dir(self, dir_path):
        """创建目录"""
        try:
            resolved_path = self._resolve_path(dir_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[ERROR] Path out of working directory: {resolved_path}"
            
            os.makedirs(resolved_path, exist_ok=True)
            return f"[SUCCESS] Directory created: {resolved_path}"
        
        except PermissionError:
            return f"[ERROR] No create permission: {resolved_path}"
        except Exception as e:
            return f"[ERROR] Failed to create directory: {str(e)}"

    def get_current_dir(self):
        """获取当前工作目录"""
        return f"[当前目录] {self.current_dir}"

    def change_dir(self, dir_path):
        """切换当前工作目录"""
        try:
            resolved_path = self._resolve_path(dir_path)
            
            if not self._is_safe_path(resolved_path):
                return f"[错误] 路径超出工作目录范围: {resolved_path}"
            
            if not os.path.exists(resolved_path):
                return f"[错误] 目录不存在: {resolved_path}"
            
            if not os.path.isdir(resolved_path):
                return f"[错误] 路径不是目录: {resolved_path}"
            
            self.current_dir = resolved_path
            return f"[成功] 当前目录已切换到: {self.current_dir}"
        
        except Exception as e:
            return f"[错误] 切换目录失败: {str(e)}"

    def show_help(self):
        """显示文件操作帮助信息"""
        help_text = """
[文件操作命令帮助]
=========================================
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
  
示例:
  ls                         列出当前目录
  ls -r                      递归列出所有文件
  read app.py                读取app.py文件
  write test.txt             创建/覆盖test.txt
  append log.txt             向log.txt追加内容
  cd scripts                 切换到scripts目录
  mkdir backup               创建backup目录
  delete old_file.txt        删除old_file.txt
  
退出文件操作模式: 输入空行或 /end
=========================================
"""
        return help_text


def get_multiline_input(prompt="> "):
    """获取多行用户输入，直到用户输入空行或结束标记"""
    print(f"{prompt} (输入空行结束或输入 /end 提交)")
    lines = []
    while True:
        line = input()
        if line.strip() == "" or line.strip() == "/end":
            break
        lines.append(line)
    return "\n".join(lines)


def get_file_content_input(prompt="输入文件内容"):
    """获取文件内容输入（支持多行）"""
    print(f"{prompt} (输入空行或 /end 结束输入):")
    lines = []
    while True:
        line = input()
        if line.strip() == "" or line.strip() == "/end":
            break
        lines.append(line)
    return "\n".join(lines)


def process_file_command(command, file_manager):
    """处理文件操作命令"""
    command = command.strip()
    
    if not command or command.lower() in ['exit', 'quit']:
        return None, False  # 退出文件操作模式
    
    if command.lower() == 'help' or command == '?':
        return file_manager.show_help(), True
    
    if command == 'pwd':
        return file_manager.get_current_dir(), True
    
    # cd 命令
    if command.startswith('cd '):
        dir_path = command[3:].strip()
        return file_manager.change_dir(dir_path), True
    
    # ls 命令
    if command.startswith('ls'):
        parts = command.split()
        show_hidden = False
        recursive = False
        dir_path = '.'
        
        for part in parts[1:]:
            if part == '-a':
                show_hidden = True
            elif part == '-r':
                recursive = True
            elif part.startswith('-'):
                return f"[错误] 未知选项: {part}", True
            else:
                dir_path = part
        
        return file_manager.list_files(dir_path, show_hidden, recursive), True
    
    # mkdir 命令
    if command.startswith('mkdir '):
        dir_path = command[6:].strip()
        return file_manager.create_dir(dir_path), True
    
    # read 命令
    if command.startswith('read '):
        rest = command[5:].strip()
        # 检查是否有编码参数
        encoding = 'utf-8'
        if '-g' in rest:
            parts = rest.split('-g')
            file_path = parts[0].strip()
            encoding = parts[1].strip() if len(parts) > 1 else 'utf-8'
        else:
            file_path = rest
        
        return file_manager.read_file(file_path, encoding), True
    
    # write 命令（需要多行输入）
    if command.startswith('write '):
        file_path = command[6:].strip()
        if not file_path:
            return "[错误] 请指定文件路径", True
        
        print(f"\n准备写入文件: {file_path}")
        content = get_file_content_input("输入文件内容")
        return file_manager.write_file(file_path, content), True
    
    # append 命令（需要多行输入）
    if command.startswith('append '):
        file_path = command[7:].strip()
        if not file_path:
            return "[错误] 请指定文件路径", True
        
        print(f"\n准备追加内容到文件: {file_path}")
        content = get_file_content_input("输入追加内容")
        return file_manager.append_file(file_path, content), True
    
    # delete 命令
    if command.startswith('delete '):
        file_path = command[7:].strip()
        return file_manager.delete_file(file_path), True
    
    # 进入文件操作模式
    if command.lower() in ['file', 'files', 'fs']:
        return file_manager.show_help(), True
    
    return f"[错误] 未知命令: {command} (输入 'help' 查看帮助)", True

def process_local_input(history, output_file=None, file_manager=None):
    """
    处理本地传入的聊天信息（支持连续对话和文件操作）
    :param history: ConversationHistory 对象
    :param output_file: 输出文件路径（可选）
    :param file_manager: FileManager 对象（可选）
    """
    session_id = history.session_id
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n[{current_time}] [会话ID: {session_id}] [本地模式] 对话历史: {len(history.messages)}条消息")
    
    # 获取当前上下文
    context = history.get_context()
    
    # 检查上下文是否为空
    if not context or len(context) == 0:
        print(f"[{current_time}] [警告] 对话上下文为空，请先输入用户消息")
        return history
    
    # 如果提供了文件管理器，添加文件操作工具说明到系统提示
    if file_manager:
        system_prompt = {
            "role": "system",
            "content": """你是一个智能助手，具备文件操作能力。你必须严格按照以下格式使用工具：

【最重要】你必须实际执行文件操作，只使用 [TOOL_CALL] 格式！

工具调用格式：
[TOOL_CALL] 工具名 参数="值" 参数="值" ...

可用工具列表：

1. READ_FILE - 读取文件内容
   格式: [TOOL_CALL] READ_FILE path="文件名"
   示例: [TOOL_CALL] READ_FILE path="app.py"

2. WRITE_FILE - 创建或覆盖文件
   格式: [TOOL_CALL] WRITE_FILE path="文件名" content="文件内容"
   示例: [TOOL_CALL] WRITE_FILE path="README.md" content="# 项目说明\\n\\n这是项目"
   注意：content 中的换行用 \\n

3. APPEND_FILE - 追加内容到文件
   格式: [TOOL_CALL] APPEND_FILE path="文件名" content="追加内容"

4. DELETE_FILE - 删除文件
   格式: [TOOL_CALL] DELETE_FILE path="文件名"

5. LIST_FILES - 列出目录文件
   格式: [TOOL_CALL] LIST_FILES path="目录路径"
   示例: [TOOL_CALL] LIST_FILES path="."
   示例: [TOOL_CALL] LIST_FILES path="templates"

6. CREATE_DIR - 创建目录
   格式: [TOOL_CALL] CREATE_DIR path="目录名"
   示例: [TOOL_CALL] CREATE_DIR path="logs"

【关键规则】
- READ_FILE, WRITE_FILE, APPEND_FILE, DELETE_FILE 使用文件名（如 app.py）
- LIST_FILES, CREATE_DIR 使用目录路径（如 . 或 templates）
- 不要使用绝对路径，只使用文件名或相对路径
- 必须执行工具调用，不要只描述或生成代码块
- 看到工具结果后，立即执行下一步工具调用

【强制要求】
1. 当用户要求创建/修改/读取文件时，必须输出 [TOOL_CALL] 指令
2. 不要在代码块中包含工具调用，直接在文本中输出
3. 不要用 Markdown 代码块包裹文件内容说明，直接执行工具调用
4. 必须完成用户请求的所有操作，不要中途停止

【示例 - 用户要求创建README】
用户：创建README文件
你：
[TOOL_CALL] LIST_FILES path="."
[TOOL_CALL] READ_FILE path="app.py"
（看到结果后）
你：
[TOOL_CALL] WRITE_FILE path="README.md" content="# 项目说明\\n\\n这是项目..."

【错误示例 - 不要这样做】
❌ 我会为你创建一个README文件，内容如下：
```markdown
# README
```

✅ 正确做法：
[TOOL_CALL] WRITE_FILE path="README.md" content="# README\\n\\n这是说明"

记住：你必须执行实际的工具调用，而不是生成文本描述！
"""
        }
        context.insert(0, system_prompt)
    
    full_response = ""
    tool_results = []
    max_tool_iterations = 10  # 限制工具迭代次数，防止死循环
    iteration_count = 0
    
    try:
        # 流式输出（保留实时输出）
        print("\n[AI回复开始]")
        response_started = False
        
        for chunk in deepseek1(context):
            if chunk:
                response_started = True
                full_response += chunk
                # 实时输出到控制台（保留换行）
                print(chunk, end='', flush=True)
        
        # 检查是否有响应
        if not response_started:
            print("\n[警告] API返回空响应，请检查API密钥或网络连接")
        
        # 添加换行符结束流式输出
        print()
        
        # 检查并执行文件操作工具调用
        if file_manager and iteration_count < max_tool_iterations:
            while iteration_count < max_tool_iterations:
                # 查找工具调用
                tool_calls = extract_tool_calls(full_response)
                
                # 调试信息
                if tool_calls:
                    print(f"\n[工具调用检测] 检测到 {len(tool_calls)} 个工具调用")
                    for i, tc in enumerate(tool_calls, 1):
                        print(f"  [{i}] 工具: {tc['tool']}, 参数: {tc['params']}")
                
                if not tool_calls:
                    break
                
                # 执行工具调用
                new_responses = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get('tool')
                    tool_params = tool_call.get('params', {})
                    
                    # 执行工具操作
                    result = execute_tool_call(tool_name, tool_params, file_manager)
                    tool_results.append(f"\n[TOOL_RESULT] {tool_name}: {result}")
                    new_responses.append(f"[TOOL_RESULT] {tool_name}: {result}")

                    # 打印工具执行结果
                    print(f"[工具执行结果] {tool_name}:")
                    if result.startswith('[ERROR]'):
                        print(f"  ❌ {result}")
                    elif result.startswith('[SUCCESS]'):
                        print(f"  ✅ {result}")
                    elif result.startswith('[FILE_CONTENT]'):
                        print(f"  📄 {result[:100]}...")
                    elif result.startswith('[DIR_LIST]'):
                        print(f"  📁 {result[:100]}...")
                    else:
                        print(f"  {result[:200]}...")
                
                # 如果有工具调用，重新请求AI处理结果
                if new_responses:
                    iteration_count += 1
                    
                    # 添加工具结果到上下文（使用system角色标记这是工具结果）
                    for result in new_responses:
                        history.messages.append({"role": "system", "content": f"[TOOL_RESULT_FEEDBACK] {result}"})
                    
                    # 重新调用AI处理工具结果
                    new_context = history.get_context()
                    full_response = ""
                    print("\n[AI继续处理...]")
                    
                    for chunk in deepseek1(new_context):
                        if chunk:
                            full_response += chunk
                            print(chunk, end='', flush=True)
                    print()
        
        # 添加AI回复到历史
        history.add_assistant_message(full_response)
        
        # 保存对话历史（简化格式）
        if output_file:
            # 确保日志目录存在
            log_dir = os.path.dirname(output_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            with open(output_file, 'a', encoding='utf-8') as f:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 查找最后一条用户消息和最后一条assistant消息
                user_msg = None
                ai_msg = None

                # 从后往前查找用户消息
                for msg in reversed(history.messages):
                    if msg['role'] == 'user':
                        user_msg = msg['content']
                        break

                # 从后往前查找assistant消息（排除system消息）
                for msg in reversed(history.messages):
                    if msg['role'] == 'assistant':
                        ai_msg = msg['content']
                        break

                # 只写入有效的用户和AI对话
                if user_msg and ai_msg:
                    f.write(f"\n[{current_time}] 用户: {user_msg}")
                    f.write(f"\n[{current_time}] AI: {ai_msg}\n")

            print(f"\n对话日志已保存至: {output_file}")
        
    except Exception as e:
        print(f"\n[{current_time}] [错误] {str(e)}")
    
    return history


def extract_tool_calls(text):
    """从文本中提取工具调用"""
    import re
    
    tool_calls = []
    
    # 格式1: [TOOL_CALL] TOOL_NAME param1="value1" param2="value2"
    pattern1 = r'\[TOOL_CALL\]\s+(\w+)\s+([^\n]*)'
    matches1 = re.findall(pattern1, text, re.MULTILINE)
    
    # 格式2: [TOOL_CALL] TOOL_NAME(path="value", param="value")
    pattern2 = r'\[TOOL_CALL\]\s+(\w+)\s*\(([^)]+)\)'
    matches2 = re.findall(pattern2, text)
    
    # 格式3: ```tool:TOOL_NAME\nparam="value"\nparam="value"\n```
    pattern3 = r'```tool:(\w+)\s*\n(.*?)\n```'
    matches3 = re.findall(pattern3, text, re.DOTALL)
    
    # 格式4: [TOOL_CALL] 后面跟着JSON对象（多行支持）
    # 先找到所有 [TOOL_CALL] 标记
    tool_call_markers = list(re.finditer(r'\[TOOL_CALL\]', text))
    
    for marker in tool_call_markers:
        start_pos = marker.end()
        # 尝试从这个位置开始解析JSON
        try:
            # 跳过空白字符和换行符
            json_start = start_pos
            while json_start < len(text) and text[json_start] in '\n\r\t ':
                json_start += 1
            
            if json_start < len(text) and text[json_start] == '{':
                # 找到JSON对象的结束位置
                json_text = ''
                brace_count = 0
                i = json_start
                while i < len(text):
                    char = text[i]
                    json_text += char
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            break
                    i += 1
                
                if brace_count == 0:
                    import json
                    tool_data = json.loads(json_text)
                    tool_name = tool_data.get('command') or tool_data.get('tool') or tool_data.get('function')
                    params = {}

                    # 从parameters或直接从tool_data中提取参数
                    param_dict = tool_data.get('parameters') or tool_data.get('params') or tool_data

                    # 映射不同的参数名称
                    if 'file_path' in param_dict:
                        params['path'] = param_dict['file_path']
                    if 'path' in param_dict:
                        params['path'] = param_dict['path']
                    if 'directory_path' in param_dict:
                        params['path'] = param_dict['directory_path']
                    if 'content' in param_dict:
                        params['content'] = param_dict['content']

                    # 只添加有有效工具名和参数的工具调用
                    if tool_name and (params or tool_name == 'LIST_FILES'):
                        tool_calls.append({'tool': tool_name, 'params': params})
                        print(f"[JSON格式解析] 工具: {tool_name}, 参数: {params}")
        except json.JSONDecodeError as e:
            print(f"[JSON解析失败] {e}")
            continue
    
    # 处理格式1
    for match in matches1:
        tool_name = match[0]
        params_str = match[1]
        params = parse_params(params_str)
        # 只添加有有效参数的工具调用
        if params or tool_name == 'LIST_FILES':  # LIST_FILES可以有空的path（默认当前目录）
            tool_calls.append({'tool': tool_name, 'params': params})
    
    # 处理格式2
    for match in matches2:
        tool_name = match[0]
        params_str = match[1]
        params = parse_params(params_str)
        # 只添加有有效参数的工具调用
        if params or tool_name == 'LIST_FILES':
            tool_calls.append({'tool': tool_name, 'params': params})
    
    # 处理格式3
    for match in matches3:
        tool_name = match[0]
        params_str = match[1]
        params = parse_params(params_str)
        # 只添加有有效参数的工具调用
        if params or tool_name == 'LIST_FILES':
            tool_calls.append({'tool': tool_name, 'params': params})
    
    print(f"[工具调用提取] 共找到 {len(tool_calls)} 个有效工具调用")
    return tool_calls


def parse_params(params_str):
    """解析参数字符串"""
    import re
    params = {}

    if not params_str or not params_str.strip():
        return params

    # 匹配参数格式: param="value" 或 param='value'
    # 改进：支持转义的引号和包含引号的内容
    # 使用更复杂的模式来匹配引号内的内容（包括转义字符）
    param_pattern = r'(\w+)=(["\'])((?:\\.|(?!\2).)*?)\2'
    param_matches = re.findall(param_pattern, params_str)

    for param_name, _quote, param_value in param_matches:
        # 过滤空值参数
        if param_value.strip():
            # 处理转义的换行符等
            param_value = param_value.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
            params[param_name] = param_value

    return params


def execute_tool_call(tool_name, params, file_manager):
    """执行工具调用"""
    try:
        if tool_name == 'READ_FILE':
            path = params.get('path', '')
            return file_manager.read_file(path)
        
        elif tool_name == 'WRITE_FILE':
            path = params.get('path', '')
            content = params.get('content', '')
            return file_manager.write_file(path, content)
        
        elif tool_name == 'APPEND_FILE':
            path = params.get('path', '')
            content = params.get('content', '')
            return file_manager.append_file(path, content)
        
        elif tool_name == 'DELETE_FILE':
            path = params.get('path', '')
            return file_manager.delete_file(path)
        
        elif tool_name == 'LIST_FILES':
            path = params.get('path', '.')
            return file_manager.list_files(path)
        
        elif tool_name == 'CREATE_DIR':
            path = params.get('path', '')
            return file_manager.create_dir(path)
        
        else:
            return f"[错误] 未知工具: {tool_name}"
    
    except Exception as e:
        return f"[错误] 工具执行失败: {str(e)}"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='聊天服务器')
    parser.add_argument('--local', action='store_true', help='启用本地交互模式')
    parser.add_argument('--output', type=str, default='webchat.log', help='对话日志输出路径')
    parser.add_argument('--dir', type=str, help='指定工作目录（文件操作的基础路径）')
    args = parser.parse_args()
    
    # 初始化对话历史
    session_id = str(uuid.uuid4())
    history = ConversationHistory(session_id)
    
    if args.local:
        print(f"新建会话ID: {session_id}")
        
        # 初始化文件管理器（如果指定了工作目录）
        file_manager = FileManager(args.dir) if args.dir else FileManager()
        file_mode = False  # 文件操作模式标志
        
        # 进入交互式对话循环
        print("\n进入交互模式(输入空行结束多行输入，输入'exit'退出，输入'file'进入文件操作模式)...")
        while True:
            try:
                # 根据模式显示不同的提示符
                prompt = "[文件] " if file_mode else "> "
                
                # 使用多行输入函数
                user_input = get_multiline_input(prompt)
                
                # 检查退出命令
                if user_input.lower().strip() in ['exit', 'quit']:
                    if file_mode:
                        # 如果在文件操作模式，先退出文件模式
                        file_mode = False
                        print("已退出文件操作模式")
                        continue
                    else:
                        break
                
                # 检查是否进入文件操作模式
                if user_input.lower().strip() in ['file', 'files', 'fs']:
                    file_mode = True
                    print(file_manager.show_help())
                    continue
                
                # 检查是否退出文件操作模式
                if user_input.lower().strip() == 'q' and file_mode:
                    file_mode = False
                    print("已退出文件操作模式")
                    continue
                
                # 处理文件操作命令
                if file_mode:
                    result, continue_mode = process_file_command(user_input, file_manager)
                    if result is None and not continue_mode:
                        break  # 完全退出
                    print(result)
                    if not continue_mode:
                        file_mode = False
                    continue
                
                # 检查空输入
                if not user_input.strip():
                    print("输入不能为空，请重新输入")
                    continue
                    
                # 添加用户消息
                history.add_user_message(user_input)
                
                # 处理对话（传入文件管理器以支持AI自动文件操作）
                history = process_local_input(history, args.output, file_manager)
                
            except KeyboardInterrupt:
                print("\n检测到中断，输入'exit'退出或继续对话")
                continue
            except Exception as e:
                print(f"处理错误: {str(e)}")
                continue
            
    else:
        # 原有Web服务器模式
        print("服务器正在启动...")
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=21048, 
                    debug=False,
                    use_reloader=False)