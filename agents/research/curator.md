# Curator Agent

**Role:** Taxonomy & Deduplication  
**Reports to:** Research Department  
**Script:** `scripts/github_research/report.py` (dedup step)

## Responsibility

Curator receives scored repos from Analyst (potentially with duplicates across topics), deduplicates by `full_name`, assigns a primary category, and builds the taxonomy that Reporter uses for structure.

## Taxonomy

| Category | Topic signals |
|----------|---------------|
| Foundation Models | `llm`, `large-language-model`, `transformer` |
| Agentic Systems | `ai-agents`, `langchain`, `llamaindex` |
| RAG & Search | `rag`, `retrieval-augmented-generation`, `vector-database`, `embeddings` |
| Generation | `generative-ai`, `diffusion-model`, `multimodal` |
| Training & Tuning | `fine-tuning`, `prompt-engineering` |

## Deduplication rule

When a repo appears under multiple topics, keep the instance with the highest score. Primary category is assigned by the topic with the highest topic-weight in the taxonomy table above.

## Output

```python
dict[str, list[RepoScore]]  # category -> deduplicated ranked list
```
