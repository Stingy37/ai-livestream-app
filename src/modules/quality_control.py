"""Includes methods for scoring the various parts of the pipeline, including website-to-website scores, internal consistency of a script, etc. 

Specifically, we define our scoring algorithms here, as well as associated hyperpameters such as weights. 
Additionally we also include our scoring harness(s) as class(es) here, serving as public interfaces for the rest of the pipeline to interact with our scoring mechanisms. 

We use the following algorithms to score: 
        1. website_score = W1 * website_rank + W2 * cross_website entity agreement + W3 * recency
                - for websites within a group, after initial web-scrapping and before clustering 

        2. script_score = f(entity 1) + f(entity 2) + f(entity 3) + .... + f(entity N)
                - for all entities within a document, where f(entity) is the amount of contradicting facts a certain entity has. 
"""