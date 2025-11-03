import os
from typing import Optional, Union

import hnswlib
import numpy as np
from colorama import Fore, Style
from fastembed import TextEmbedding
from tqdm import tqdm

from sanguine.db.fts import CodeEntity
from sanguine.utils import app_dir, decode_path, encode_path, normalize_path

dim = 384
model: Union[None, TextEmbedding] = None
indices_dir = os.path.join(app_dir, "indices")
indices = {}


if os.path.isdir(indices_dir):
    for index_file in os.listdir(indices_dir):
        index = hnswlib.Index(space="cosine", dim=dim)
        index_file = os.path.join(indices_dir, index_file)
        encoded_repo_path = os.path.splitext(os.path.basename(index_file))[0]
        index.load_index(index_file)
        norm_repo_path = decode_path(encoded_repo_path)
        indices[norm_repo_path] = index
else:
    os.makedirs(indices_dir)


def init_embedder(use_cuda: bool):
    global model

    providers = ["CPUExecutionProvider"]
    if use_cuda:
        providers.append("CUDAExecutionProvider")

    model = TextEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        providers=providers,
    )


def make_hnsw_index(repo_path: str) -> hnswlib.Index:
    num_entities = (
        CodeEntity.select()
        .where(CodeEntity.file.startswith(repo_path))
        .count()
    )
    max_elements = max(1000, num_entities + 100)
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=max_elements, M=64)
    indices[repo_path] = index
    return index


def find_apt_hnsw_index(path: str) -> Optional[hnswlib.Index]:
    for repo_path, index in indices.items():
        # NOTE: 'normalize_path' here is for handling trailing slashes
        if normalize_path(os.path.commonpath([repo_path, path])) == repo_path:
            return index
    return None


def embed(texts: str) -> list[np.ndarray]:
    return list(model.embed(texts))


def hnsw_add_symbol(texts: list[str], ids: list[int], index: hnswlib.Index):
    embeddings = embed(texts)
    new_count = index.get_current_count() + len(ids)
    if new_count > index.get_max_elements():
        index.resize_index(max(new_count, index.get_max_elements() * 2))
    index.add_items(embeddings, ids)


def hnsw_search(
    query: str, index: hnswlib.Index, k: int = 10
) -> tuple[list[int], list[float]]:
    if index.get_current_count() == 0:
        return []

    index.set_ef(max(50, k * 2))
    query_vec = embed([query])
    labels, distances = index.knn_query(query_vec, k=k)
    return labels[0].tolist(), [1 - d for d in distances[0].tolist()]


def hnsw_remove_symbol(id: int, index: Optional[hnswlib.Index] = None):
    if index is None:
        return
    index.mark_deleted(id)


def refresh_hnsw_index(batch_size: int = 512):
    total_entities = CodeEntity.select().count()
    if total_entities == 0:
        return

    pbar = tqdm(
        total=total_entities,
        ncols=80,
        bar_format=f"{Fore.GREEN}|{{bar}}|{Style.RESET_ALL}",
    )
    for repo_path in indices:
        index = hnswlib.Index(space="cosine", dim=dim)
        index.init_index(max_elements=max(total_entities, 1000), M=64)
        batch_ids, batch_texts = [], []

        for entity in (
            CodeEntity.select()
            .where(CodeEntity.file.startswith(repo_path))
            .iterator()
        ):
            batch_ids.append(entity.id)
            batch_texts.append(entity.name)

            if len(batch_ids) >= batch_size:
                embeddings = embed(batch_texts)
                index.add_items(embeddings, batch_ids)
                batch_ids.clear()
                batch_texts.clear()
                pbar.update(len(batch_ids))

        if batch_ids:
            embeddings = embed(batch_texts)
            index.add_items(embeddings, batch_ids)
            pbar.update(len(batch_ids))

        indices[repo_path] = index

    save_indices()
    print()


def save_indices():
    for repo_path, index in indices.items():
        filename = f"{encode_path(repo_path)}.bin"
        index.save_index(os.path.join(indices_dir, filename))
