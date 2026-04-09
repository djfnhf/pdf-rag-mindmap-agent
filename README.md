# AI Mindmap — 密码学知识库问答 & 思维导图生成

一个基于 RAG（检索增强生成）的本地知识库问答工具。喂入一本 PDF 教材，就能通过对话检索书中内容，并自动生成 Mermaid 思维导图。

目前内置了《密码学中的可证明安全性》（杨波）作为示例知识库，也可以替换成其他 PDF。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-orange)

## 功能特性

- **RAG 检索问答**：对 PDF 进行 OCR 提取 → 文本切片 → 向量化入库，提问时自动检索相关段落辅助回答
- **思维导图生成**：回答自动附带 Mermaid 格式的思维导图，前端实时渲染
- **全屏查看**：导图支持一键放大全屏，解决小窗口下看不清的问题
- **深/浅色主题**：界面支持主题切换
- **多轮对话**：支持上下文记忆，可以针对导图内容追问

## 项目结构

```
ai_mindmap/
├── main.py                          # FastAPI 后端服务入口
├── .env                             # API Key 等环境变量
├── requirements.txt                 # Python 依赖
├── data_pipeline/
│   └── build_vector_db.py           # PDF → OCR → 切片 → 向量入库脚本
├── db/
│   └── chroma_data/                 # ChromaDB 持久化存储（自动生成）
├── static/
│   ├── index.html                   # 前端页面
│   ├── css/style.css                # 样式（含深/浅色主题）
│   └── js/app.js                    # 前端交互逻辑与导图渲染
└── book/
    └── 密码学中的可证明安全性-杨波.pdf  # 原始 PDF 教材
```

## 快速开始

### 1. 安装依赖

需要 Python 3.10 或更高版本。

```bash
pip install -r requirements.txt
```

> 首次安装会下载 PyTorch、Sentence-Transformers 等较大的包，耗时取决于网络情况。

### 2. 配置 API Key

编辑项目根目录下的 `.env` 文件：

```ini
DEEPSEEK_API_KEY=你的API密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. 构建知识库（仅需执行一次）

```bash
python data_pipeline/build_vector_db.py
```

这一步会对 PDF 进行 OCR 识别、文本切片和向量化，结果持久化保存在 `db/chroma_data/` 中。

对于扫描版 PDF（纯图片，无文字层），脚本会自动调用 RapidOCR 逐页识别，**整本书大约需要 10-20 分钟**。

看到终端输出 `大功告成` 即表示完成。

### 4. 启动服务

```bash
python main.py
```

看到以下输出说明启动成功：

```
>>> 启动 FastAPI 服务，运行在 http://localhost:8000
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

打开浏览器访问 **http://localhost:8000** 即可使用。

> **注意**：不要直接双击打开 `index.html`，必须通过上面的地址访问，否则 API 请求会失败。

## 技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + Uvicorn |
| PDF 解析 | PyMuPDF + RapidOCR（扫描件） |
| 文本切片 | LangChain RecursiveCharacterTextSplitter |
| 向量数据库 | ChromaDB（本地持久化） |
| 向量模型 | shibing624/text2vec-base-chinese |
| 大语言模型 | DeepSeek API |
| 前端渲染 | Marked.js（Markdown）+ Mermaid.js（导图） |

## 常见问题

**Q: 页面显示"无法访问此网页"？**

后端服务没在运行。在项目目录下重新执行 `python main.py` 即可。

**Q: 思维导图没有渲染出来，只显示文字？**

偶尔大模型输出的 Mermaid 语法不规范。在对话框中追问"请重新生成思维导图，严格使用 mermaid 语法"一般能解决。

**Q: 安装依赖时报 C++ 编译相关错误？**

部分依赖需要 C++ 编译工具。Windows 用户请安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，勾选"C++ 桌面开发"工作负载。

**Q: 如何替换成其他 PDF？**

将新的 PDF 放入 `book/` 目录，修改 `data_pipeline/build_vector_db.py` 中的 `PDF_PATH` 变量指向新文件，重新运行构建脚本即可。

## License

MIT license
