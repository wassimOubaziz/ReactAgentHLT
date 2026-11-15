import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from simpleeval import simple_eval


def paragraphs(items: list[dict]) -> list[tuple[str, str]]:
    """Unique (title, text) paragraphs from the sampled HotPotQA contexts."""
    seen: dict[str, str] = {}
    for item in items:
        for title, sentences in item["context"]:
            seen.setdefault(title, " ".join(sentences))
    return list(seen.items())


class Search:
    """Top-k passage retrieval over a fixed corpus, sparse (BM25) or dense (MiniLM)."""

    def __init__(self, paras: list[tuple[str, str]], kind: str = "sparse", k: int = 3):
        self.paras = paras
        self.kind = kind
        self.k = k
        docs = [f"{title}: {text}" for title, text in paras]
        if kind == "sparse":
            self.bm25 = BM25Okapi([doc.lower().split() for doc in docs])
        else:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.emb = self.model.encode(docs, normalize_embeddings=True)

    def _score(self, query: str) -> np.ndarray:
        if self.kind == "sparse":
            return np.asarray(self.bm25.get_scores(query.lower().split()))
        return self.emb @ self.model.encode([query], normalize_embeddings=True)[0]

    def _top(self, query: str) -> list[int]:
        scores = self._score(query)
        return [int(i) for i in np.argsort(-scores)[: self.k]]

    def retrieve(self, query: str, limit: int = 10) -> list[dict]:
        """Scored top-N hits for the viewer (the agent itself still gets self.k)."""
        scores = self._score(query)
        hits = []
        for i in np.argsort(-scores)[:limit]:
            hits.append({"title": self.paras[int(i)][0], "snippet": self.paras[int(i)][1][:280],
                         "score": round(float(scores[int(i)]), 3)})
        return hits

    def __call__(self, query: str) -> str:
        return "\n".join(f"[{self.paras[i][0]}] {self.paras[i][1]}"[:400] for i in self._top(query))

    def titles(self, query: str) -> list[str]:
        return [self.paras[i][0] for i in self._top(query)]


def calculate(expr: str) -> str:
    try:
        value = simple_eval(expr.replace("$", "").replace(",", "").strip())
        if isinstance(value, float):
            return f"{value:.10f}".rstrip("0").rstrip(".")
        return str(value)
    except Exception as e:
        return f"Error: {str(e)[:100]}"
