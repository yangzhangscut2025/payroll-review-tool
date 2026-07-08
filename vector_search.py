"""向量检索引擎：分块MD文件 → 嵌入向量 → ChromaDB → 相似度检索。"""
import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings

# 全局单例（延迟加载）
_collection = None
_model = None

MODEL_NAME = 'BAAI/bge-m3'
DB_DIR = os.path.join(os.path.dirname(__file__), 'vectordb')


def get_model():
    """延迟加载 BGE-M3 模型。"""
    global _model
    if _model is None:
        print('Loading BGE-M3 model...', file=sys.stderr)
        _model = SentenceTransformer(MODEL_NAME)
        print('Model loaded.', file=sys.stderr)
    return _model


def get_collection(collection_name):
    """获取或创建 Chroma 集合。"""
    global _collection
    client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(anonymized_telemetry=False))
    collections = client.list_collections()
    existing = [c.name for c in collections]
    if collection_name not in existing:
        # 已存在就不用重建
        _collection = client.get_or_create_collection(name=collection_name)
    else:
        _collection = client.get_collection(name=collection_name)
    return _collection


def chunk_md_text(text, max_chars=500):
    """将 MD 文本按段落分块，每块不超过 max_chars。"""
    chunks = []
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            # 长段落按句子拆分
            sentences = para.replace('\n', ' ').split('. ')
            current = ''
            for sent in sentences:
                if len(current) + len(sent) < max_chars:
                    current += sent + '. '
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    current = sent + '. '
            if current.strip():
                chunks.append(current.strip())
    return chunks


def build_index(md_dir, project_id):
    """遍历 MD 目录，分块嵌入，存入 Chroma。"""
    collection_name = f'project_{project_id}'
    client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(anonymized_telemetry=False))

    # 删除旧集合
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass

    coll = client.create_collection(name=collection_name)
    model = get_model()

    ids = []
    docs = []
    metas = []
    idx = 0

    md_files = sorted([f for f in os.listdir(md_dir) if f.endswith('.md')])
    total_files = len(md_files)

    # 进度文件
    progress_file = os.path.join(DB_DIR, f'build_progress_{project_id}.txt')
    def write_progress(msg):
        with open(progress_file, 'w', encoding='utf-8') as f:
            f.write(msg)

    write_progress(f'0/{total_files} 文件')

    for fi, fname in enumerate(md_files):
        path = os.path.join(md_dir, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            continue

        chunks = chunk_md_text(text)
        for i, chunk in enumerate(chunks):
            ids.append(f'blk_{idx:06d}')
            docs.append(chunk)
            metas.append({'file': fname, 'chunk_idx': i, 'row': int(fname.split('_')[0]) if fname[0].isdigit() else 0})
            idx += 1

            if len(ids) >= 500:
                embeddings = model.encode(docs, show_progress_bar=False).tolist()
                coll.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
                ids, docs, metas = [], [], []

        write_progress(f'{fi+1}/{total_files} 文件, {idx} 段落')

    if ids:
        embeddings = model.encode(docs, show_progress_bar=False).tolist()
        coll.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    write_progress(f'完成: {total_files} 文件, {idx} 段落')
    return idx


def search_similar(project_id, query_text, top_k=5):
    """搜索与查询文本最相似的段落。"""
    if not query_text.strip():
        return []

    collection_name = f'project_{project_id}'
    client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(anonymized_telemetry=False))

    try:
        coll = client.get_collection(name=collection_name)
    except Exception:
        return []

    model = get_model()
    query_vec = model.encode([query_text], show_progress_bar=False).tolist()
    results = coll.query(query_embeddings=query_vec, n_results=top_k)

    hits = []
    if results['ids'] and results['ids'][0]:
        for i in range(len(results['ids'][0])):
            hits.append({
                'id': results['ids'][0][i],
                'doc': results['documents'][0][i] if results['documents'] else '',
                'file': results['metadatas'][0][i].get('file', '') if results['metadatas'] else '',
                'distance': results['distances'][0][i] if results['distances'] else 0,
            })
    return hits


def index_exists(project_id):
    """检查索引是否已构建。"""
    collection_name = f'project_{project_id}'
    client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(anonymized_telemetry=False))
    try:
        client.get_collection(name=collection_name)
        return True
    except Exception:
        return False


def build_progress(project_id):
    """读取构建进度。"""
    progress_file = os.path.join(DB_DIR, f'build_progress_{project_id}.txt')
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ''