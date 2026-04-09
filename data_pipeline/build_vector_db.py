import os
# 使用国内镜像，避免直连 huggingface.co 超时
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import re
import fitz  # PyMuPDF
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.utils import embedding_functions

# 配置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(BASE_DIR, "book", "密码学中的可证明安全性-杨波.pdf")
DB_DIR = os.path.join(BASE_DIR, "db", "chroma_data")
COLLECTION_NAME = "cryptography_knowledge"

def clean_text(text: str) -> str:
    """对提取出的文字进行基本清洗"""
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    """使用 PyMuPDF 提取纯文本或者通过 OCR 挖掘扫描版图片"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到指定的PDF文件: {pdf_path}")
    
    print(f"正在读取 PDF 文件: {pdf_path}")
    doc = fitz.open(pdf_path)
    
    # 验证本本是不是毫无电子文字底层的纯图片扫描本
    test_text = ""
    for i in range(min(5, len(doc))):
        test_text += doc[i].get_text("text")
        
    full_text = ""
    
    if len(test_text.strip()) > 50:
        print("检测到文本层，走普通快速提取通道...")
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text("text") + "\n"
    else:
        print("🚨 检测报告：这本课本为【完全纯照片的扫描 PDF】，内置提取结果为 0 字符。")
        print("🤖 系统将接管调用本地 RapidOCR 视觉引擎暴力破译识别整本书的内容！")
        print("⚠️ 警告：OCR 是非常重度的视觉分析算法，229 页扫描件全程可能需要 10～20 分钟以上。")
        print("请倒一杯咖啡，保持计算机唤醒，耐心等待入库完成......")
        
        ocr = RapidOCR()
        for i in range(len(doc)):
            page = doc[i]
            # 使用高倍渲染矩阵，否则 OCR 大量繁体/密集字可能糊掉
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            
            # 转为 RGB，再翻转通道成为 BGR (OpenCV格式)，喂给 RapidOCR
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
            bgr_img = img[:, :, ::-1].copy()
            
            try:
                result, _ = ocr(bgr_img)
                if result:
                    # 摘出识别到的文本段
                    page_text = "\n".join([line[1] for line in result])
                    full_text += page_text + "\n"
            except Exception as e:
                pass
                
            if (i+1) % 5 == 0:
                print(f"   -> OCR 破译进度: {i+1}/{len(doc)} 页已完成，当前字数积攒: {len(full_text)}...")

    print(f"提取完毕！总字符数(粗略估算): {len(full_text)}")
    return clean_text(full_text)

def split_text(text: str) -> list[str]:
    """文本切片: 保持一定的 overlap 避免破坏上下文"""
    print("开始进行文本切片 (Chunking)...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,     
        chunk_overlap=50,   
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "，", " "]
    )
    chunks = text_splitter.split_text(text)
    print(f"切片完成，共切分为 {len(chunks)} 个数据块。")
    return chunks

def build_vector_database(chunks: list[str]):
    """使用文本切片构建 ChromaDB 向量库"""
    
    # 如果 chunks 是空的，提前爆雷
    if not chunks:
        print("❌ 错误：没提取到任何内容！构建失败！")
        return
        
    print("正在初始化 ChromaDB 并在本地加载 Embedding 模型...")
    client = chromadb.PersistentClient(path=DB_DIR)
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="shibing624/text2vec-base-chinese"
    )
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"description": "密码学中的可证明安全性知识库"}
    )
    
    # 因为要覆盖掉以前的空数据，最好先清空它或者我们直接往里塞（利用Chunk_id相同会覆盖的特性）
    documents = []
    metadatas = []
    ids = []
    
    print("开始将真正的文本数据段注入向量数据库...")
    for idx, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({"source": "杨波扫描版", "chunk_id": idx})
        ids.append(f"chunk_{idx}")
    
    batch_size = 5000
    for i in range(0, len(chunks), batch_size):
        end_idx = min(i + batch_size, len(chunks))
        collection.upsert(
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx],
            ids=ids[i:end_idx]
        )
        print(f"--> 已安全入库 {end_idx}/{len(chunks)} 条片段...")
        
    print(f"🎉 完成！充盈着真实知识的向量数据库已持久化保存至: {DB_DIR}")

if __name__ == "__main__":
    try:
        raw_text = extract_text_from_pdf(PDF_PATH)
        chunks_list = split_text(raw_text)
        build_vector_database(chunks_list)
        print("\n🚀 带有纯扫面件 OCR 的全链条离线知识库构建大功告成！")
    except Exception as e:
        print(f"构建知识库时发生错误: {str(e)}")
