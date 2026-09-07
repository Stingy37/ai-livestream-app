"""Contains methods and the class representing the cluster formed from HDBSCAN of the scrapped sentences. 

Methods pertaining to building and interacting with the cluster class go here, including splitting the sentences, 
converting into their embedding representation, HDBSCAN algorithm + hyperparameters, exemplar lookup, returning a cluster, etc. 

However, logic for building the lookup for querying this cluster belongs in retrieval.py. 
We expect ths module to recieve sentences (for initial building) and cluster query requests (for querying the built clusters,) and output a HDBSCAN class which acts as a interface. 
"""