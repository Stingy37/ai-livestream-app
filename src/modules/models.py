"""Contains methods serving as a public (to other modules) interface for interacting with the various models used in the project. 

Includes both loading, serving, and standardized api (vLLM) for local models and a custom standardized api for interacting with provider models (ex. OpenAI, Anthropic families.)
Models included in this project include LLMs, NER + Coreference task families, and NLI Classifer cross encoders. 
"""