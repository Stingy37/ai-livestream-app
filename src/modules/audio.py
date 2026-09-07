"""Contains methods in charge of decoding a given audio file and streaming to CABLE input of some virtual device. 

Fits into app pipeline during graph traversal: the current node's audio file is expected as input into this module. 
Also, seperately contains methods for generating and saving the audio to a database.  
"""