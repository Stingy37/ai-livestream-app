"""Contains methods serving as a public (to other modules) interface for interacting with the various models used in the project.

Includes both loading, serving, and standardized api (vLLM) for local models and a custom standardized api for interacting with provider models (ex. OpenAI, Anthropic families.)
Models included in this project include LLMs, NER + Coreference task families, and NLI Classifer cross encoders.

Shared folder — any team may import from any file here, but each file has one owning team:

    llm_api.py ........ Web Scraper team — provider LLM APIs (Claude, OpenAI, ...)
    local_llm_api.py .. RAG team — one unified caller for local LLMs
    qc.py ............. Quality Control team — models QC uses (NER, coreference, NLI, judge, ...)

Load model weights lazily (on first use), never at import time: every scene runs in its
own process, so a model loaded at import is loaded once per scene.
"""
