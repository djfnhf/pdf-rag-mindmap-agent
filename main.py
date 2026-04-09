import os
# 使用国内镜像，避免直连 huggingface.co 超时
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import AsyncOpenAI
import chromadb
from chromadb.utils import embedding_functions

# 1. 加载环境变量
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# OpenAI SDK对接DeepSeek时，基础路径为 https://api.deepseek.com
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not DEEPSEEK_API_KEY:
    raise ValueError("请在 .env 文件中设置 DEEPSEEK_API_KEY")

# 2. 初始化 OpenAI 异步客户端 (用它来兼容 DeepSeek API)
client_ai = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=120.0)

# 3. 初始化 FastAPI 应用
app = FastAPI(title="密码学专有知识库 RAG 智能体")

# 4. 初始化 ChromaDB 与嵌入模型
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db", "chroma_data")
COLLECTION_NAME = "cryptography_knowledge"

# 这里确保与建立离线库时所用的嵌入模型保持绝对一致
emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="shibing624/text2vec-base-chinese"
)

# 启动时连接集合，如果在初始化知识库前启动了服务，就暂存 None 避免直接崩溃
client_db = chromadb.PersistentClient(path=DB_DIR)
try:
    collection = client_db.get_collection(name=COLLECTION_NAME, embedding_function=emb_fn)
except Exception as e:
    print(f"未能加载 ChromaDB 集合 '{COLLECTION_NAME}'，请确认是否已执行过了 build_vector_db.py")
    collection = None

#================ API 接口与数据模型定义 ================#

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: list[Message] = []

# 定义学术专家的人设 Prompt，以及规定 Mermaid 思维导图强制输出
SYSTEM_PROMPT = """你是一位专门研究密码学和《密码学中的可证明安全性》的顶级学术专家，态度严谨求实。
（⚠️最高准则：由于你是一个基于 RAG 的局部检索增强系统，每次只能命中部分零散段落。如果内容看似零散拼凑，**请绝不在回答中抱怨或提到“参考内容不完整/找不到”！** 你必须凭借你的专家知识水准，结合检索碎片，自然大方地直接给出一个连贯、宏观的专业解答。）
请基于下方[领域知识参考册]中的检索段落内容解答问题。若其未涵盖全貌，务必结合自身密码学知识强行缝合并引申，保持极高的专业度解答态度。
同时你的回答必须要具有层级，分作两部分：

### 1. 详细文字解答
（在此处写下严谨、清晰的文字解答，使用标准学术措辞）

### 2. 思维导图总结
将上述解答的核心概念脉络归纳为一张思维导图。必须要包含在 markdown 的 mermaid 代码块中。
【极其重要防报错规范】：
1. 你的所有 Mermaid 节点内容（特别是涉及括号、数学符号或标点的），**必须全部使用标准的双引号严格包裹**！
2. 示例规范：`A["可证明安全性(Provable)"] --> B["规约证明"]`
3. 以 `graph TD;` 头开始。
示例：
```mermaid
graph TD;
    A["伪随机生成器"] --> B["单向函数"];
```

======================
下面是基于你的提问从本地专有知识库检索回来的相关信息[领域知识参考册]：
{context}
======================
"""

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not collection:
        raise HTTPException(status_code=500, detail="本地知识向量数据库未就绪。")

    try:
        # A. 检索增强环节 (RAG Retrieval)
        # 获取与当前请求文本最相关匹配的前 15 段切片信息，扩大上下文范围抵抗碎片化零散阅读！
        results = collection.query(
            query_texts=[request.query],
            n_results=15
        )
        
        # 提取并拼接命中的分块文档文本内容
        documents = results["documents"][0] if results["documents"] else []
        retrieved_context = "\n\n---\n\n".join(documents)
        print(f"-> 命中了 {len(documents)} 条相关的专有知识材料文档。")

        # B. Prompt 组装与指令生成
        formatted_system_prompt = SYSTEM_PROMPT.format(context=retrieved_context)
        
        # 拼接历史记录，确保能够多轮追问思维导图内容
        api_messages = [{"role": "system", "content": formatted_system_prompt}]
        for msg in request.history:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        # 将用户最新的提问追加进去
        api_messages.append({"role": "user", "content": request.query})

        # C. 异步调用大模型推理聊天接口
        response = await client_ai.chat.completions.create(
            model="deepseek-chat",
            messages=api_messages,
            temperature=0.3,  # 温度设为 0.3，减少幻觉保障学术严谨性
            max_tokens=2048   # 放宽Token限制以确保 Mermaid 绘制完整
        )
        
        answer = response.choices[0].message.content
        return JSONResponse(content={"answer": answer})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"后端报错详见终端日志：{str(e)}")

#================ 静态前端托管 ================#

# 确保预先创建静态资源的根目录
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

# 挂载后方的路由，使得 /static/xxx 重定向到静态物理目录
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "前端静态文件未找到，等待下一步构建前端！"

if __name__ == "__main__":
    print(">>> 启动 FastAPI 服务，运行在 http://localhost:8000")
    # 为了方便热更新调试，设置为 reload=True
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
