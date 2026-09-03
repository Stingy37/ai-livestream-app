### **Template**

We log user test sessions with the following convention: 

```
[timestamp] [severity] observation
```

Severity codes:

- `OK` — smooth, no issues
- `H` — hesitation (paused 3+ seconds, scanned the page)
- `W` — wrong target (clicked something expecting different result)
- `F` — failure (could not complete without help)

Example raw notes:

```
0:00  OK  clicked "new broadcast" immediately
0:34  H   looked for "add scene" inside broadcast config, ~6s scan
0:52  OK  found scene editor via sidebar
1:28  F   couldn't find connector dot on scene graph cards, tried 3x
1:35  Q   "how do I connect these?"
2:15  H   scrolled past scheduling section twice
2:41  OK  task complete
```

---

### **Session One**

#### Tester: Lab supervisior — Wang Qianyue 

---

#### User Flow 

user opened broadcast
added two scenes without problem 
dragged edge without problem 
didn't understand sequential order (had branching on her graph) 
tried to undo but undo not present 
edge dragging doesn't snap -> some issues 

clicked into title -> scene editor, confused initially (overwhelemed) but quickly figured it out 
entered title on first scene card w/o trouble
entered topic description without trouble 
"I need to make the forecast" -> topic description
first scene card didn't enter websites

second scene card ->
thought the fields on the left are only what is needed -> need to make more clear what is required and what isn't 
didn't know that system instructions are addressed towards chatbot initially -> (didn't know what it is for)
    - needed to explain to user 
afterwards filled it out correctly 

Got used to opening scene card editor 

Hard to find generation button (did not know she was supposed to livestream)

---

#### Feedback 
1. not very clear on what each field does
2. arrows didn't snap — didn't know when an arrow was connected 
3. should be a tutorial at the start 
4. scene card is a little complicated 
    - topic description and title is a little redundant (especially topic description)
5. Add a autocomplete feature on the text editors in scene card (like copilot)
    - for example when the title is populated, the rest of the fields can be populated with suggestsions (also is a hint as to what the other frields should include)
6. loop isn't apparent 
7. The generation and live monitor stages are good 
8. Template saving is good 
