# FLOW.md — AI Livestream Hub

> Navigation structure, screen relationships, 
> We'll use this as the authoriative source of truth for UI/UX flow in our web app. 
> We consolidate this as a markdown file in our repo so that it is agent-friendly. 

---

## 1. Navigation hierarchy (depth)

> Every user-facing screen, indented by nav depth. We plan to use a hierarchical navigation system reflecting the sequential depth-based structure of our standard user workflow. User navigation from one screen to the other is determined by what screens are directly above / below it in depth. This **purely** reflects navigation depth — dependencies are explicitly stated in our screen relationships section. 

```
- Dashboard
  - Graph Editor
    - Scene Card
    - Live Monitor
    - Save Broadcast
  - Script Generation
- Settings
  - [ Settings outside of MVP scope ]
```

---

## 2. Screen relationships (dependencies)

> Single Mermaid graph with every page-to-page navigation edge.
> Use subgraph blocks to group related screens.
> Label edges only when the nav type is non-obvious.

```mermaid
flowchart LR
  %% --- Subgraph specific connections 
  subgraph hub
    dashboard
  end

  subgraph graph_editor
    graph_editor --> scene_card
    graph_editor --> save_broadcast
  end

  subgraph script_generator
    script_generator
  end

  subgraph live_monitor
    live_monitor
  end

  subgraph settings
    settings
  end
  
  %% --- Subgraph-to-subgraph connections  
  hub --> settings
  hub --> graph_editor
  graph_editor --> script_generator
  script_generator --> live_monitor
  graph_editor -.-> live_monitor
  live_monitor --> graph_editor
```

## 3. Transition model

> Navigation uses a horizontal slide transition tied to depth.
> Deeper screens slide in from the right; backing out slides left.
> A persistent top bar shows `< [parent] | [next screen (if it exists)] >` 
> with tap targets for forward/back.
