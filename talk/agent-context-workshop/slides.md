---
theme: default
title: The Agent Will Grep Anyway
info: |
  Building a context layer for coding agents — and getting the agent to use it.
  Brandon Callender, typedef · AI Engineer World's Fair 2026 (90-min workshop)
drawings:
  persist: false
transition: slide-left
mdc: true
duration: 90min
timer: countdown
layout: cover
---

<!--
=====================================================================
FACILITATOR RUN-OF-SHOW (target 90 min; hands-on segments in [HO])
  Act 1 — Frame the problem .......................... ~15 min
    cover · follow-along (repo QR) · cold-open collision · the problem · context layer · levels · three rungs
  Act 2 — Build it, then the reversal ................ ~45 min
    [HO] notebook 01 (~30 min): extract (Rung 0→1) → L2 wall → L3 graph + blast_radius
    the payoff · THE TURN · it grepped anyway · why: posttraining
  Act 3 — What actually works + zoom out ............. ~30 min
    lean into posttraining · [HO] nb02 live switch (naive→nudged) · the eval results [full 30-q: take-home] ·
    adoption rate · the harness thesis · close

SUNDAY PRE-FLIGHT (deck depends on these — see docs/superpowers/specs + memories):
  [x] ASSET FIX (resolved): assets/ committed (gzipped 4-crate seed); scripts/setup_data.sh hydrates it; nb01 runs on a fresh clone.
  [x] nb02 built (02_does_the_graph_beat_grep) + cache committed (data/eval/graph_vs_grep_cache.json, k=5).
      Numbers here are from the canonical run — gpt-5.4-mini k=5, path-fix + tokenized search:
      pass@5 22/26 · pass^5 19/11 (type-dep 12/6) · 7K/23K tok (~3×) · adoption 34%→72%.
  [x] Logo: inlined as components/TypedefLogo.vue (dark-bg variant). `bun run dev`, press `p` for Presenter Mode + notes.
  [x] No pre-workshop email — setup is LIVE in the room (cover note reflects this); nb02 runs fully cached, no Docker/key.
  [x] Headline: determinism-led (pass^5 19 vs 11; graph holds, grep collapses; type-dep 12 vs 6), efficiency (~3×) supporting beat, adoption 34→72 the closer. · Canonical: gpt-5.4-mini k=5. · Python coda: optional, time-permitting.
=====================================================================
-->

<!-- Theme lives in style.css (global). A <style> block here would only style THIS slide. -->

# The Agent Will Grep Anyway

Building a context layer for coding agents — and the harder part: getting the agent to use it.

Brandon Callender

<div class="mt-4 flex justify-center">
  <TypedefLogo />
</div>

<!--
Hi — I'm Brandon, I'm at typedef. You're going to hear various talks at the conference about how a coding agent is only as good as the context you put around it, and building that context is the actual job. This one is the hands-on version. Over the next 90 minutes we're going to build a context layer for a coding agent together — a real one, over a real codebase — and then I'm going to show you the thing nobody who sells these puts on a slide: even after you build it, the agent mostly ignores it. Getting it to actually use the thing is where the work is. That's the talk.

[Set expectations: this is a workshop, but the framework's pre-built and yours — what you'll *do* is stand up the whole pipeline end-to-end on real code and watch it resolve, live. We're setting up live in the room — the next slide has the repo; start cloning and running `uv sync` *now* while I talk, it's a few MB. If your Docker won't start, flag a volunteer — notebook 02 runs fully cached with no Docker and no key, so nobody is dead in the water.]
-->

---
layout: center
---

## Follow along

<div class="flex items-center justify-center gap-12 mt-2">

<QrCode />

<div class="text-left text-xl leading-relaxed">

`github.com/bcallender/agent-context-workshop`

**Clone it now** — it's a few MB. Then `uv sync && scripts/setup_data.sh`; we build in ~15 min.

**Notebook 02** runs with **no Docker, no key** — if setup fights you, you're still fine.

</div>

</div>

<!--
Before we dive in: the whole workshop is in this repo — scan the QR or grab the URL. Clone it and run `uv sync` and the setup script *now*, while I talk; it's tiny, a couple of megabytes, no big downloads, so it'll be done long before we touch a notebook. And if setup fights you — Docker won't start, whatever — don't sweat it: notebook 02, the eval, runs entirely from a committed cache with no Docker and no API key. Nobody's dead in the water. Flag a volunteer and follow along.
-->

---

## Ask your agent a simple question

"Where's `PostingList` defined?"

<v-clicks>

```bash
$ rg "struct PostingList"
posting_list/src/posting_list.rs:27    pub struct PostingList<V> { ... }
sparse/src/index/posting_list.rs:12    pub struct PostingList { ... }
# … + a dozen look-alikes: PostingListView, PostingListIterator, CompressedPostingList …
```

- **Two** are the same name — `PostingList` — in *different crates*. The rest just look alike.
- Your agent greps, picks one. **You don't know which.** Neither does it.

</v-clicks>

<!--
Let's start where every coding agent starts: text search. I ask about PostingList — a real type in qdrant, the vector database we're using all day today. I run ripgrep, and look what comes back: two structs named *exactly* PostingList — one in the posting_list crate, one in sparse — plus a whole pile of look-alikes: PostingListView, PostingListIterator, CompressedPostingList, a dozen of them.

Now — your agent does the same thing. It greps, gets this wall back, and picks one. Maybe the right one. Probably the one that showed up first. And here's the part that should bother you: it has no way to know which PostingList you meant, because text has no concept of identity. `PostingList` is a string. The thing you actually care about — which one, the one in the crate you're working in, with the methods you're about to call — that's not in the text. It's in the structure.

This is the whole workshop in one example. We're going to give the agent the structure. Hold onto this PostingList collision — we're coming back to it, live, in about twenty minutes, and it's going to resolve cleanly.

[Optional live: actually run rg in a terminal — it returns the two real PostingLists plus the look-alike family. The room feeling grep fail is worth more than the slide.]
-->

---

## The real problem isn't search

Every time the agent runs, it rebuilds its understanding of the codebase from scratch.

<v-clicks>

- **Expensive** — tokens burned re-deriving the same structure every session
- **Fragile** — "which PostingList?" gets re-guessed, and re-guessed differently
- **Shallow** — grep finds *strings*; it can't tell you what *depends on* what

</v-clicks>

<div v-click>

The agent has no persistent, trustworthy model of the code. It guesses, every time.

</div>

<!--
You just watched Yoni make exactly this case for data — agents that re-derive the whole system every run, no memory, confidently wrong. It's the same disease in code, so I'll be quick about it.

Grep is a string matcher: it finds where the letters P-o-s-t-i-n-g-L-i-s-t appear. It can't tell you what implements a trait, or what breaks if you change a return type, or which of the two PostingLists is yours. Those are questions about *relationships* — and relationships aren't in the text; they have to be reconstructed every run, and grep alone can't do that. That's the gap we're closing today.
-->

---

## A context layer for code

Yoni just showed you the data context layer. Here's the same recipe — **extract · persist · query** — one level down, on code you can run.

<v-clicks>

- **Symbols** — every type, trait, function, with its real identity (not a string)
- **Relationships** — implements, returns, takes, has-field, contains — as edges
- **Computed once, queried many times** — the agent stops re-deriving and starts *knowing*

</v-clicks>

<div v-click>

Same playbook as its bigger brother — smaller, concrete, and you **stand it up yourself**.

</div>

<!--
Yoni just walked you through the data context layer — the whole case for it, the four facts, the impact analysis. I'm not going to re-make that case; he made it. What we're doing now is the same three moves — extract the structure, persist it, query it — one level down, on code, small enough that you stand the whole thing up yourself in the next hour.

Every symbol gets a real identity, the relationships between them become first-class edges you can traverse, computed once and queried many times. Same playbook as tackling a sprawling data architecture, but concrete enough to run in this room. Let me show you the shape before we start playing with the notebooks.
-->

---

## Three levels of context

How an agent can "see" a codebase — each level strictly more structured than the last.

| | | |
|---|---|---|
| **L1** | grep / glob | strings, no structure |
| **L2** | index + semantic search | ranked, still flat |
| **L3** | a traversable **graph** | identity + relationships |

<div v-click>

We're climbing to L3. *(This framing isn't mine — it's in the water this week. The point is what L3 actually buys you, and where it doesn't.)*

</div>

<!--
Here's the scaffold for the day. Think about context for a coding agent as levels. L1 is what we just saw — grep and glob, raw strings, no structure. L2 is what most "code RAG" is today: you index the code and do semantic or lexical search, you get ranked results, but it's still a flat list — no relationships. L3 is a graph: symbols with real identity, and typed edges between them you can actually traverse.

I want to be honest about this framing up front, because you're going to hear "levels of context" from at least two other people at this conference this week — it's in the water. I'm not claiming I invented it. What I think is actually worth your 90 minutes isn't the ladder — it's the specific question of what climbing to L3 buys you, and the most important part -- whether the agent will even actually use it. Hold that thought.
-->

---

## Three rungs of *building* it

Levels are what the agent sees. Rungs are how you construct the graph.

<v-clicks>

- **Rung 0 — syntactic** — tree-sitter. Finds the names. Doesn't know what they mean.
- **Rung 1 — resolution** — the *deterministic* type system. What does `PostingList` actually refer to here?
- **Rung 2 — meaning** — LLM / semantic enrichment. What is this *for*?

</v-clicks>

<div v-click>

The leverage is **Rung 1**. Resolution is exactly what grep structurally lacks.

</div>

<!--
One more distinction and then we build. The levels are what the agent sees. The rungs are how *you* build the graph, and they're not the same thing.

Rung 0 is syntactic — tree-sitter parses the file and finds the names. Fast, language-agnostic, but it has no idea that this `PostingList` and that `PostingList` are different things. Rung 1 is resolution — this is where you figure out what each name actually *refers* to: the real type, across crate boundaries, through re-exports. Rung 2 is meaning — semantic enrichment, the LLM layer, "what is this code *for*," which we'll preview at the end.

The whole game is Rung 1. Resolution is the thing grep can't do — and it's the thing that turns two ambiguous PostingList strings — posting_list's and sparse's — into two distinct, identifiable types. Today we get Rung 1 for free, because Rust's compiler hands us resolved types in rustdoc JSON — and I'll be honest, I picked Rust *on purpose* because...well, making a workshop is a lot of work, something had to come for free. But seriously, there is a larger point here, I'll elaborate more at the end. The lesson is the same in any language; Rust just lets us build the clean version in a weekend. [light seed — full payoff at the Python coda.]
-->

---
layout: center
---

## 🛠️ Build it — `notebook 01`

**Extract → index → graph.** Open it now — we build for ~30 min, then come back for the payoff.

- **Rung 0 → Rung 1** — extract the symbols, watch them *resolve*
- **L2** — the flat index finds the collision but can't *relate* it
- **L3 → Neo4j** — load the graph, ask what `grep` couldn't

<!--
[HANDS-ON — ~30 min in notebook 01. Project the notebook tab and stay there; its own headers — `## Level 2`, `## Level 3`, `### The payoff` — are your regroup checkpoints. Come back to the deck at "The payoff."]

Everybody into notebook 01 — run the setup cell first: it checks Neo4j is up and your key's loaded. If it complains, flag a volunteer and follow along anyway; the cached path carries you. We're here about thirty minutes; I'll walk the room and we regroup at each section header.

EXTRACT (~10 min · Rung 0 vs Rung 1). Extract symbols from the qdrant posting_list crate two ways: tree-sitter (Rung 0) finds the names but can't resolve them; rustdoc JSON (Rung 1) brings the same symbols back *resolved* — real qualified names, real types, re-exports followed. The contrast is the lesson. Regroup when most people have both extractions printed.

THE WALL (~3 min · L2). Build the flat index across crates and go looking for PostingList: you get the two real PostingLists plus the look-alike family — exactly my ripgrep from the start. Feel the ceiling — the rows have a name and a location, but no field that says "this one's in sparse, unrelated to that one." L2 ranks; it doesn't relate. This is a thirty-second beat, not a segment — flow straight into the graph.

GRAPH (~15 min · L3 → Neo4j). The centerpiece. Load the resolved Rung-1 symbols and their edges into Neo4j — nodes for symbols, typed edges for relationships — then open the Neo4j browser and actually look at it; seeing your codebase as a graph for the first time tends to land. Then the two payoffs: the collision *resolved* (ask for PostingList, get each back by canonical path, distinctly), and blast radius — "what depends on this type" — one hop, file and line, no false positives. The question grep can't answer cleanly. Let people run it on a couple of types, then regroup for the payoff slide.
-->

---

## The payoff

You point at the `PostingList` you *mean* — by canonical path, not the ambiguous name — and ask what grep can't:

```cypher
// blast radius of the general posting_list::PostingList — NOT the sparse one
MATCH (t:Struct {qualified_name: "posting_list::posting_list::PostingList"})
      <-[:RETURNS|TAKES|HAS_FIELD]-(d)
RETURN d.qualified_name, d.filepath, d.line_start
```

<v-clicks>

- Matched on **canonical path** — so these are *this* type's dependents, not the sparse one's merged in.
- Blast radius: the real dependents, **one hop**, with `file:line`. No re-grepping.

</v-clicks>

<!--
Here's where we are. Twenty minutes ago grep gave us identical strings and a shrug — it can't tell these PostingLists apart. Now we point at exactly the one we mean, by its canonical path — posting_list's PostingList, not sparse's — and ask the question we actually had: what depends on this if I change it. One hop, real dependents, file and line, no false positives.

And notice the query: we match on the qualified_name, not the bare name. That's the whole resolution thesis in one line — if I'd matched `name: "PostingList"` I'd have silently merged in the sparse type's dependents and undone everything we just did. The canonical path is what makes the answer *this* type's, cleanly.

This is real. The graph does something grep cannot. If I stopped here, this would be a perfectly nice "graphs beat grep" demo, you'd nod, and you'd go to the Neo4j talk tomorrow and hear the same thing. But I'd be leaving out the most important part — the part I actually learned the hard way.
-->

---
layout: center
---

## So we gave it to an agent.

<!--
[Beat. Let it sit.] So. We built the beautiful thing. We loaded it into Neo4j. We wrote clean traversal tools on top — search, blast-radius, implementors. And we did the obvious thing: we handed all of it to a coding agent, gave it the question, and sat back to watch it glide through the graph.
-->

---

## It ran `grep` anyway.

<v-clicks>

- Graph tools, right there. The agent reached for the filesystem.
- `grep`, `glob`, `read_file` — over and over. The graph sat untouched.
- Built the whole thing. **The agent didn't use it.**

</v-clicks>

<!--
It ran grep. (Insert Gru presentation meme here)

We gave it a beautiful, precomputed, traversable model of the codebase — and it opened a terminal and started grepping like the graph wasn't even there. Glob, read_file, grep, read_file. It would occasionally poke the graph, get confused, and fall right back to wading through source files by hand. We built the entire L3 context layer, and the agent defaulted to L1 like nothing had changed.

This is the thing nobody puts on a slide. Everyone shows you the graph. Nobody shows you the agent refusing to use it. And once I saw it, I couldn't unsee it — it's been my single biggest day-to-day struggle building this stuff at typedef. Building the context is the easy part. Getting the agent to *reach* for it is the job.
-->

---

## Why? Posttraining.

The model was trained on millions of examples of one move: open a terminal, run `grep`, read the file.

<div v-click>

You built a better tool. It has **muscle memory**, and you're not in it.

</div>

<!--
Why does this happen? Because of how the model was made. These models are post-trained on an enormous amount of agentic coding data, and overwhelmingly that data is one motion: open a terminal, grep, read the file, repeat. That's the reflex. That's the muscle memory. It is the single most reinforced behavior a coding agent has.

So when you hand it a graph tool it's never seen before, you're not competing on the merits — your tool is better, that's not the question. You're competing against a reflex baked in by millions of training examples. And the reflex wins, by default, unless you do something about it. The graph doesn't lose because it's worse. It loses because it's unfamiliar.

So the real question stopped being "is the graph better" — we proved that — and became "how do I get the agent to actually reach for it."
-->

---

## Don't fight the prior. Lean into it.

Stop trying to talk the model out of grep. Make the graph *feel* like grep.

<v-clicks>

- **Name it `search`** — let the reflex fire, route it into the graph.
- **Return ripgrep-shaped results** — `path:line: snippet`. Familiar on the way in.
- **Make hop one pay** — empty result or a Cypher dump, and it bails to grep forever.

</v-clicks>

<!--
Here's what actually worked, and it's a little counterintuitive: stop fighting the prior. You will lose a prompt-engineering war against posttraining every time — "please use the graph tool" just makes it apologize and grep anyway. Instead, design *with* the reflex.

Name the tool `search`, not `query_graph` — let the model's "I'll search for it" instinct fire, and quietly route that into the graph. Return results that *look* like ripgrep — path, line, snippet — so the familiar shape greets it on the way in, and then you reveal the superpower, the traversal, on the follow-up. And make the very first call pay off, because if hop one returns an empty set or a wall of Cypher, the agent decides this tool is broken and falls back to grep and never comes back.

Notice what these have in common: not one of them is "convince the model." They're all "meet the reflex where it is."
-->

---
layout: center
---

## 🛠️ Make it reach for the graph

Same agent, same tools, same question — flip the system prompt, watch it switch.

`notebook 02` · the live before/after · ~5 min

<!--
[HANDS-ON — ~5 min · notebook 02, the "watch it switch" cell] This is the thesis, live. One question — the PostingList collision from the very start — run two ways with the SAME tools available to both. Naive: the graph's just sitting there, and the agent greps right past it into the collision and picks a PostingList, maybe the wrong crate. Then we flip the prompt — name the tools for what they do, prefer the graph — re-run, and it reaches for the graph and resolves the right one by canonical path in two hops. That switch, on your own screen, is the whole workshop. Walk the room; next slide we see what it does across all thirty questions.

[Build-your-own-tool is now optional in notebook 01's "your turn" — write your own Cypher tool and wire it to the agent (it'll even write the Cypher from a plain-English description). Run it here only if the room's ahead of schedule; otherwise take-home.]
-->


---

## Does it actually help? Run it ~~three~~ five times.

Per single run it's a wash — graph ~21/30, grep ~19/30, and the grep number bounces run to run. So I ran every question **5×** — each answer scored by a deterministic, gold-anchored checker, *no LLM judge*.

<div v-click>

**pass@5** — right *at least once*: grep edges it (graph 22 · grep 26). Retries flatter the dice.

</div>

<div v-click>

**pass^5** — right on *every* run. The graph holds; grep flips. *(type-dep alone: 12/15 vs 6/15)*

<BarCompare :rows="[
  { label: 'graph', value: 19, max: 30, display: '19 / 30', color: '#77f19a' },
  { label: 'grep',  value: 11, max: 30, display: '11 / 30', color: '#6b7689' },
]" />

</div>

<div v-click>

Same answers, **~3× fewer tokens**:

<BarCompare :rows="[
  { label: 'graph', value: 7,  max: 23, display: '7K',  color: '#77f19a' },
  { label: 'grep',  value: 23, max: 23, display: '23K', color: '#6b7689' },
]" />

</div>

<div v-click>

The win was never per-shot accuracy — it's **determinism**: *look it up once* vs *figure it out every time.* And it all rides on whether the agent reaches for the graph *at all*.

</div>

<!--
Does it help? Honestly — per single run it's basically a wash. Graph lands about twenty-one of thirty, grep about nineteen, and the grep number *bounces* from run to run. That bouncing is the tell. So I did the thing the noise was begging me to do: I ran every question five times. Two numbers fall out, and they point in opposite directions.

pass-at-five: did it get the answer right at least *once* in five tries. Twenty-two for the graph, twenty-six for grep — grep actually edges it. Grep loves this one, because if you give a noisy method five rolls of the dice, it usually hits one eventually. That's retries flattering grep.

pass-to-the-five: did it get it right on *every* run. And here it splits wide open: graph nineteen, grep eleven. The graph *holds* — it answers the same way run after run — while grep collapses by more than half. On the pure type-dependency questions it's even starker — twelve out of fifteen versus six. And watch *why*: the graph looked the connections up. It computed them once, deterministically, back in Rung one — so it answers the same way every run. Grep re-derives the relationships from raw text every single time, and re-derivation is a coin flip.

That's the actual win. The graph was never going to be *more correct* than a strong model with grep. What it is, is *deterministic* — it turns "figure out the connections again, every run" into "look them up." And in production, an agent doing this a hundred times a day, one shot each, no retries — determinism is the whole game. A tool that's right but only sometimes, and you can't tell which time, you can't ship. Determinism, plus it's about three times cheaper on tokens — seven thousand versus twenty-three. That's the honest win — and every bit of it still rides on whether the agent reaches for the graph at all, which is next.
-->

---

## The number that actually matters

You can build the most elegant tool in the world — right answer, every time, one call, zero false positives. **It's worth nothing if the agent only reaches for it a fraction of the time.**

<div v-click>

**Adoption** — of all code-lookups, the share that hit the graph vs fell back to grep:

<BarCompare :rows="[
  { label: 'naive',  value: 34, max: 100, display: '34%', color: '#6b7689' },
  { label: 'nudged', value: 72, max: 100, display: '72%', color: '#77f19a' },
]" />

*An elegant tool reached for a third of the time is a third of a tool* — and every capability win on the last slide is **gated** by this one number.

</div>

<div v-click>

**This is why you build the eval.** Not to prove the tool is good — to catch that it's going *unused*.

</div>

<!--
Yoni's last takeaway was evals, evals, evals — you can't build a reliable agent if you can't measure it. Here's the eval result that changed how I think about this, and the metric I almost never see anyone report. You can build the most elegant tool in the world: right answer, one call, no false positives. The eval on the last slide says ours basically is that. And none of it matters if the agent barely reaches for it. An elegant tool reached for a third of the time is a third of a tool — and that's exactly where ours started.

So we measure adoption directly: of all the times the agent went looking for code, what fraction used the graph versus fell back to grep? Naively, thirty-four percent — the grep reflex still wins most of the time. After we shape the prompt and the tools, seventy-two. It roughly doubles — and that last quarter still going to grep tells you how strong that reflex is.

And this is the real reason you build the eval — and it's the thread through everything I do. You don't build the eval to prove your tool is good; you'll convince yourself of that on your own. You build it to find the thing you would never see otherwise: that your beautiful, one-call-perfect tool is sitting there untouched while the agent greps around it. Every capability number on the last slide is downstream of this one. The graph's value was never "is it better." It's "did we get the agent to use the better thing."
-->

---

## The hard part was admitting grep works <span style="opacity:.45">· the nuance behind the title</span>

When the eval came back a tie, my first reaction was *frustration* — I wanted to keep tuning until the graph clearly won.

<v-clicks>

- That instinct — *"my approach has to be the better one"* — is the trap. Sunk cost, dressed up as rigor.
- The agent has its reflex (posttraining). I had mine (the graph I built). **Same bug, both sides of the keyboard.**
- If grep works this well, the honest move isn't to *fight* it — it's to lean into it.

</v-clicks>

<div v-click>

The agent will grep anyway. And so will *you* keep trying to out-engineer grep. **Design with the grain — both of yours.**

</div>

<!--
I want to be honest about something that happened when I got these results, because it's the actual point.

When the eval came back and grep tied my graph on accuracy, my first reaction wasn't "great, an honest result." It was frustration. I'd built this thing. I wanted a clean win. And my instinct was to go right back and keep tuning — better edges, a stricter scorer, more questions — until the graph clearly beat grep.

That instinct has a name: sunk cost. And it dresses itself up as rigor — "I just need to measure it better." But step back. The agent has a reflex it won't let go of — grepping, baked in by its posttraining. And here I was, with my own reflex I wouldn't let go of: my graph has to be the better tool. Same bug, both sides of the keyboard.

And here's what the data was actually trying to tell me: if grep works this well, the move is not to fight it. It's to lean into it. Meet the agent where it already is — grep-shaped tools — and use the graph for the one thing it's genuinely better at, which is efficiency, not replacement. That's what the title really means. The agent will grep anyway — and if you're honest, so will you keep trying to out-engineer grep. The work is to stop fighting both reflexes and design with the grain instead.
-->

---

## The eval was directionally right — and a little wrong <span style="opacity:.45">· both times</span>

Second talk in a row: the report pointed the *right way* and was quietly **off** — the dangerous kind. A wildly wrong eval you catch before lunch; a *plausible* one you put on a slide.

<v-clicks>

- The summary said *graph ≈ grep*. The **traces** said: the agent was **404-ing on every graph path** (a path mismatch no number would show), lobbing whole sentences at a *symbol* search, and an **earlier model looping 46 turns** for a 3-turn answer.
- The "decisive" determinism gap swung **±5 between runs** of the *same* eval — mostly noise at low *k*.
- None of it was in the scoreboard. **All of it was in the traces.**

</v-clicks>

<div v-click>

The fix is never a nicer number — it's a *harder eval*: read the traces → find the artifact → harden the harness → re-run. **Distrust your own scoreboard.**

</div>

<!--
One more, because it's the most useful thing I can hand you, and it's now happened to me twice. Both times I've built a talk like this, the eval came back directionally right — and a little bit wrong. "A little wrong" is the dangerous kind. Off by a mile, you catch it before lunch. Off by a hair — plausible, pointing the right direction — you put it on a slide and ship it.

Here's what "a little wrong" looked like this time, and I only know because I sat and read the traces. The summary said graph and grep basically tie — that's even the honest headline. But underneath: the agent was asking the graph for a file and getting a 404 every single time, because of a path mismatch I'd never have seen in a number, so it quietly gave up on the graph and grepped. It was throwing whole descriptive sentences at a tool that only matches symbol names, and getting nothing back. On the hard questions, the model I started on looped forty-plus turns to land a three-turn answer — part of why I switched models partway through. And my determinism gap — the headline — swung by five questions between two runs of the exact same eval. Decisive-looking, mostly noise.

Not one of those showed up in the scoreboard. Every one showed up the moment I opened the traces. So the real deliverable isn't the number on the last slide — it's the discipline behind it: distrust your own eval, go read what the agent actually did, find the artifact, harden the harness, run it again. That loop — not the graph — is the thing I'd most want you to take home.
-->

---

## You're only as good as the harness

The model keeps getting better. Your job is the environment around it.

<v-clicks>

- Building the graph was the easy part.
- The eval loop, the tool design, the adoption fight — *that* was the work.
- The code was never the slow part. **Neither is the model.**

</v-clicks>

<div v-click>

The whole harness — the deterministic scorer, the loop, *no LLM judge* — is available in the repo for your perusal.

</div>

<!--
So let me zoom all the way out, because this is the same lesson I keep landing on no matter which direction I come at it from. And here it's: building the graph took an afternoon; getting the agent to *use* it — the eval loop, the tool ergonomics, the adoption fight — that was the actual engineering.

The models keep getting better on their own. They are not getting better at using *your* context layer — that part is on you. The code was never the slow part. It turns out the model isn't either. The slow part is, and always was, the environment you build around it. Evals take time, tweaking knobs takes time, and is expensive -- but it's the only way to prove that your beautiful, amazing toolset can survive contact with the real world.

If you want the receipts — the whole eval harness, the deterministic scorer, the no-LLM-judge loop — it's all in notebook two, and it's yours to take home and point at your own codebase.
-->

---

## Rust was cheating — on purpose

Every resolved edge today — every `RETURNS`, every cross-crate `IMPLEMENTS` — came from `rustdoc`.

<v-clicks>

- The Rust **compiler already did Rung 1**. We read its homework.
- I picked the language where resolution is *free*. **Deliberately.**
- Build the well-engineered version on the *easy* instance — the lesson transposes.

</v-clicks>

<div v-click>

So: was the graph the point, or the compiler? Your Python codebase is about to answer.

</div>

<!--
Before we land the plane, an honest admission — and then I'm going to turn it into the most useful thing I say all day.

Every resolved edge you built today, you got for free. rustdoc is the Rust compiler's own output — it already resolved every type, followed every re-export, decided what every name refers to. We didn't do Rung 1. We read the compiler's homework and loaded it into Neo4j. A skeptic could call that an ETL job on the compiler's output, and for Rust — honestly — that's fair.

But I want to be clear this was a *choice*, not an accident. I had a workshop's worth of prep time, and I wanted you to walk out with a clean, well-engineered graph and a crisp lesson — not a half-finished resolver I ran out of time on. So I picked the language where resolution is free. And that's a real engineering move worth naming out loud: when you're learning something hard, you build the well-engineered version on the *easy* form of the problem first, so the lesson comes out clean — and then you transpose it to the hard form. Rust was the easy form. Watch what happens the moment we move to the one where you can't cheat.
-->

---

## Python: nothing resolves it for you

Same question — *what depends on this?* — where text search structurally can't answer it.

```python
# mypkg/api/__init__.py
from .client import Client          # a re-export — grep just sees a string

c = Client()
c.session.execute(query)            # what type is .session? what does this touch?
```

<v-clicks>

- `grep "Client"` → the re-export, the class def, 200 call sites. **No resolution.**
- Static analysis (Griffe — no runtime) rebuilds the types and follows the re-export.
- Load it, traverse it — the blast radius a compiler was never going to hand you.

</v-clicks>

<div v-click>

**This** is where a code graph earns its keep. Same recipe, any language: *extract → resolve → graph → traversal*.

</div>

<div v-click>

`notebook 03` · griffe on **pydantic**, live — the two `BaseModel`s resolved to distinct paths, the gaps named honestly, a 48-class blast radius.

</div>

<!--
Python. No compiler is waiting to hand you resolved types — and that is exactly where this gets good.

Look at this. A re-export in an __init__, and an attribute chain: c.session.execute. Grep for Client and you get the re-export line, the class definition, and two hundred call sites — and not one of them tells you what .session actually is or what .execute touches. Text doesn't know. ctags doesn't know. There is no homework to copy.

So you do Rung 1 yourself — statically, no runtime, with something like Griffe: rebuild the types, follow the re-export, resolve the names. And the second you've done that, you load it into the same graph, and you get the same blast radius — except now it's a capability that did not exist until you built it, because nothing else was going to give it to you.

In Rust the graph looked like a convenience. In Python it is the only road there. Same recipe in every language: extract, resolve, graph, traversal tools. Rust was the clean demo. Python is where you actually need it — and it's where I'd point you first tomorrow morning.

[notebook 03 IS this worked example — griffe on pydantic: the two BaseModels resolved to distinct canonical paths (the PostingList collision, in Python), 200 of 207 re-exports followed, the 7 it can't named honestly, and a 48-subclass blast radius on PydanticValueError. A 60-second live run of that cell beats this static slide — open notebook 03.]
-->

---

## Rung 2 — meaning <span style="opacity:.45">· optional, if time</span>

Structure tells you *what connects to what*. The **comments** tell you *why*. Rung 2 folds that intent in.

```python
df.with_column("intent", fc.semantic.map(
    "In one sentence, what is this for?\n\n{{doc}}", doc=fc.col("docstring")))
```

<v-clicks>

- A small, focused question reads the **prose humans wrote** — for *intent* the structure can't see.
- It lands on the same structural node, grounded on the same `file:line`.
- `search` now answers *what it's for*, not just *where it is*.

</v-clicks>

<!--
[OPTIONAL — FIRST TO CUT. Only if the build + eval + reversal all landed clean and we have ~10 min.]

Everything we built so far is deterministic — tree-sitter for structure, rustdoc for resolution. That gives you the skeleton: what connects to what. But there's a whole layer it can't touch — intent. WHY does this exist, what's it really for — and that lives in the prose humans already wrote: the comments, the docstrings. Structure can't read it; an LLM can.

That's Rung 2, and it's where fenic comes in. One small focused operator reads the docstring — the comment — and writes back a one-sentence intent, attached to the same node, grounded on the same file and line. Now a search returns structure AND intent on the same symbol. That's the meaning layer — and the next slide is the part that makes it trustworthy.
-->

---

## Many small questions, not one big one <span style="opacity:.45">· optional</span>

The lesson isn't a smarter prompt. It's **decomposition**.

<v-clicks>

- Ask the model ten things about a chunk of code at once → a blob you can't audit, and it hallucinates.
- Parse the structure deterministically, then ask **many small, focused questions** — one summary, one classification — each grounded on a row.
- Want it to weigh more? Give a focused question **more parsed input** — not more to answer.

</v-clicks>

<div v-click>

Small, grounded, auditable semantic ops over parsed structure. **That's what fenic is for.**

</div>

<!--
Yoni's first takeaway was "deterministic first, LLM where you must." This is the heart of how we think about it — and it isn't the prompt, it's the decomposition.

The naive move is to hand the model a big chunk of code and ask it ten things at once: what does this do, is it public, what's risky, who depends on it. You get back a blob — non-deterministic, it hallucinates, and you can't audit any single answer inside it.

The right move is the opposite. Parse the structure deterministically first — which we already did, that's Rungs zero and one — then ask the model many small, focused questions. One summary. One classification. Each grounded on a single row, each independently checkable. Small, bounded tasks are exactly what these models are good at.

So when you want the model to weigh one more factor, you're not piling more onto one prompt — you're giving a focused question more deterministically-extracted input to reason over, or adding one more small focused column. Either way it stays small and auditable. That — small, grounded semantic ops over parsed structure — is exactly what fenic is built to express. It's the whole reason the tool exists. [Then into where-this-goes.]
-->

---
layout: center
---

## Where this goes

The public-API floor was the start. The edges we didn't draw are the roadmap:

**Private internals** (where grep beat us) · **call graphs** (SCIP — true "who calls this") · **richer meaning** (comments today → issues, PRs, the discussions where intent really lives)

<!--
And past that, the edges we deliberately didn't draw today — because the honest losses ARE the roadmap.

The private-internals class grep beat us on? That's the next index. Call graphs through SCIP get you true "who calls this," not just "who references the type." And the meaning layer keeps going: today it reads the comments inside the code; next it folds in the prose OUTSIDE it — issues, PRs, design docs, the discussions where the real intent actually lives — all grounded back on the structure. Same idea, bigger corpus. But the recipe — extract, resolve, graph, traverse — you already have all of it.
-->

---
layout: center
class: end
---

## The agent will grep anyway —

## until you design for the reflex.

Brandon Callender · typedef

<sup>*Build it yourself:* `github.com/bcallender/agent-context-workshop`</sup>

<div class="flex flex-col items-center gap-2 mt-8">
  <QrLinkedIn />
  <span class="text-sm opacity-50">connect on LinkedIn — linkedin.com/in/bcallender</span>
</div>

<!--
So that's the workshop. You built a context layer for a coding agent — a real graph over a real codebase. You watched the agent ignore it. And you watched it switch the moment you stopped fighting the prior and started designing for it.

The one thing I want you to walk out with: the agent will grep anyway — until you build the environment that makes the better tool the path of least resistance. Building the context is the easy part. The handoff is the job.

The repo's up there, everything we did today is in it. Thank you — come find me, I'll be around all week.
-->
