"""Contains methods for building the multi-coverage lookup queries for our HDBSCAN cluster, given a input query. 

Uses a small LLM to split a scene title + scene description into specific items needed to answer the scene, 
and embeds them into vector representations for cluster exemplar lookup.
Concatates and returns a structured list of relevant sentences from the retrieved cluster(s). 

Example: 
    1. Input: "This scene summarizes the forecasted local impacts to the local region of Cebu" 
                        [ LLM: "What information is needed for this scene" ]
    2. LLM Query decomposition: "Wind forecasts," "local terrain," "Cebu warnings" etc. 
                         [ HDBSCAN query with the decomposed query vectors ]
    3. Structured output: 
        relevant_sentences = {
                                "decomposed query one": decomposed query one relevant sentences
                                "decomposed query two": decomposed query two relevant sentences
                            }
"""