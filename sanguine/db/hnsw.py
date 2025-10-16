import os

import hnswlib
from sentence_transformers import SentenceTransformer

from sanguine.db.fts import CodeEntity
from sanguine.utils import app_dir

dim = 384
model = SentenceTransformer("all-MiniLM-L6-v2")
index_file = os.path.join(app_dir, "hnsw.bin")

if os.path.exists(index_file):
    index = hnswlib.Index(space="cosine", dim=dim)
    index.load_index(index_file)
else:
    num_entities = CodeEntity.select().count()
    max_elements = max(1000, num_entities + 100)
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=max_elements, M=64)


def hnsw_add_symbol(texts: list[str], ids: list[int]):
    embeddings = model.encode(texts, convert_to_numpy=True)
    new_count = index.get_current_count() + len(ids)
    if new_count > index.get_max_elements():
        index.resize_index(max(new_count, index.get_max_elements() * 2))
    index.add_items(embeddings, ids)


def hnsw_search(query: str, k: int = 10) -> tuple[list[int], list[float]]:
    if index.get_current_count() == 0:
        return []

    index.set_ef(max(50, k * 2))
    query_vec = model.encode([query], convert_to_numpy=True)
    labels, distances = index.knn_query(query_vec, k=k)
    return labels[0].tolist(), [1 - d for d in distances[0].tolist()]


def hnsw_remove_symbol(id: int):
    index.mark_deleted(id)


from colorama import Fore, Style
from tqdm import tqdm


def refresh_hnsw_index(batch_size: int = 512):
    total_entities = CodeEntity.select().count()
    if total_entities == 0:
        return

    global index
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=max(total_entities, 1000), M=64)

    batch_ids, batch_texts = [], []

    for entity in tqdm(
        CodeEntity.select().iterator(),
        total=total_entities,
        ncols=80,
        bar_format=f"{Fore.GREEN}|{{bar}}|{Style.RESET_ALL}",
    ):
        batch_ids.append(entity.id)
        batch_texts.append(entity.name)

        if len(batch_ids) >= batch_size:
            embeddings = model.encode(batch_texts, convert_to_numpy=True)
            index.add_items(embeddings, batch_ids)
            batch_ids.clear()
            batch_texts.clear()

    if batch_ids:
        embeddings = model.encode(batch_texts, convert_to_numpy=True)
        index.add_items(embeddings, batch_ids)

    save_index()
    print()


def save_index(path=index_file):
    index.save_index(path)
