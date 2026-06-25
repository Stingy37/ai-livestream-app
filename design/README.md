## General

All the major user-facing components of our apps workflow will have hifi mockups for initial UI development. The standard user workflow should be completely described 
with hifi mockups, supporting user-facing testing with a interactive prototype. 

Smaller items (such as states, specific settings, and one-off user interactions that do not need to be part of this prototype) will have a corresponding wireframe. 


The project location in claude design has the work in progress mockups, while the mockups present on the repo are authoritariative versions. This can be thought of as a more traditional local / remote relationship, where commits are handled through prompting claude in claude design.

## Claude

For claude specifically: 
- Agents should use both the png and raw html in tasks involving the frontend UI. Never guess or deviate from the mocked UI unless necessary. 
- Agents should refer to FLOW.md as the source of truth for UI/UX flow. 