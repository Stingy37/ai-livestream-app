# Usability test plan — AI Livestream Hub (round 1)

## Goal

Validate whether a first-time user can complete the core broadcast creation flow end-to-end using the hi-fi prototype, and identify where the navigation model, screen layout, or interaction patterns break down.

This is the first round of testing. The prototype covers only the core user flow (going from an empty graph editor to a running broadcast.) Therefor, the main hifi screens being tested are Hub, Scene Card Editor, Scene Graph, Broadcast Configuration, and Schedule Orchestrator.


## Participant criteria

3–5 participants with fresh eyes on the project. We'll give a profile summary of each participant below:

| Who | Why they're useful | Bias to watch for |
|-----|-------------------|-------------------|
| Lab supervisor | Smart and direct; will give honest feedback + technical background | They already know what the project is about (but we aren't even testing onboarding to begin with) |


## Setup

- Prototype: [insert Claude Design share link or URL]
- Screen recording: on
- Script: One task prompt asking to accomplish the core user flow we are testing. 


## Task Prompts

### Task 1:  Create a broadcast from scratch
**Read to participant:**
> "You're covering a typhoon making landfall in Guangzhou. Create a new broadcast with two scenes: a scene covering the forecast of the storm and a scene covering local impacts."

**What this tests:** Full end-to-end flow across all four screens. This is the critical path.

**Success criteria:**
- Participant creates a broadcast (Broadcast Config)
- Creates two scene cards (Scene Card Editor)
- Connects them in order to form a valid graph (Scene Graph)
- Initiates the broadcast
- Completes without asking for help

## Debrief questions (after all tasks)

1. "What was the hardest part?"
2. "If you had to explain this app to a friend, how would you describe the workflow?"
3. "Anything you expected to find that wasn't there?"



