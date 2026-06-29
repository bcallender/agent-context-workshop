---
theme: default
title: The Agent Will Grep Anyway
info: |
  Building a context layer for coding agents — and getting the agent to use it.
  Brandon Callender, Typedef · AI Engineer World's Fair 2026 (90-min workshop)
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
    cover · cold-open collision · the problem · context layer · levels · three rungs · setup
  Act 2 — Build it, then the reversal ................ ~45 min
    [HO] build extraction · [HO] L2 index + collision · [HO] L3 load + blast_radius
    the payoff · THE TURN · it grepped anyway · why: posttraining
  Act 3 — What actually works + zoom out ............. ~30 min
    lean into posttraining · [HO] make it use the graph · the honest eval ·
    adoption rate · reactance callback · the harness thesis · close

SUNDAY PRE-FLIGHT (deck depends on these — see docs/superpowers/specs + memories):
  [ ] ASSET FIX: data/raw_repos + data/cache are gitignored — a fresh clone can't run nb01.
      Ship a fetchable bundle + make setup fail loudly. (Blocker #1.)
  [ ] BUILD nb02: graph-agent vs grep-agent, commit the cache, ADD the adoption-rate metric.
      Every [FILL] in these notes comes from that cache. Until then the numbers are TODO.
  [ ] Add talk/public/typedef-logo.svg (cover references /typedef-logo.svg).
  [ ] Pre-workshop setup email (Docker + Neo4j + uv + API key) so setup isn't in the room.
  [ ] Decide: efficiency-first headline (recommended) · how far on the Python coda.
=====================================================================
-->

<style>
:root { --slidev-theme-primary: #829df3; --slidev-theme-background: #111111; }
.slidev-layout { background: #111111 !important; color: #e0e0e0; }
.slidev-page { background: #111111 !important; }
h1, h2, h3 { color: #829df3 !important; }
strong { color: #77f19a; }
em { color: #ffbf30; }
code:not(pre code) { background: #29394e; color: #77f19a; }
blockquote { border-left: 3px solid #ffbf30; color: #ffbf30; font-style: italic; }
blockquote p { color: #ffbf30; }
a { color: #829df3; }
li, p { color: #e0e0e0; }
.mermaid, .mermaid svg { background: transparent !important; }
</style>

# The Agent Will Grep Anyway

Building a context layer for coding agents — and the harder part: getting the agent to use it.

Brandon Callender

<img src="/typedef-logo.svg" alt="Typedef" style="height: 40px; margin-top: 1rem; opacity: 0.9;" />

<!--
Hi — I'm Brandon, I'm at Typedef. The last few talks I've given have all circled the same idea from different angles: a coding agent is only as good as the context you put around it, and building that context is the actual job. This one is the hands-on version. Over the next 90 minutes we're going to build a context layer for a coding agent together — a real one, over a real codebase — and then I'm going to show you the thing nobody who sells these puts on a slide: even after you build it, the agent mostly ignores it. Getting it to actually use the thing is where the work is. That's the talk.

[Set expectations: this is a workshop. You'll build. There's a setup desk / you got the email. If your Docker isn't up, flag a volunteer now — we have a fully-cached path so nobody is dead in the water.]
-->

---

## Ask your agent a simple question

"Where's `PostingList` defined?"

<v-clicks>

```bash
$ rg "struct PostingList"
posting_list/src/posting_list.rs:27      pub struct PostingList<T> { ... }
sparse/src/index/posting_list.rs:12      pub struct PostingList { ... }
quantization/.../posting_list_common.rs  // and more
```

- Three different types. Same name. Different crates.
- Your agent picks one. **You don't know which.** Neither does it.

</v-clicks>

<!--
Let's start where every coding agent starts: text search. I ask about PostingList — a real type in qdrant, the vector database we're using all day today. I run ripgrep. I get three hits. Three completely different structs, in three different crates, all named PostingList.

Now — your agent does the same thing. It greps, it gets three answers, and it picks one. Maybe the right one. Probably the one that showed up first. And here's the part that should bother you: it has no way to know which one you meant, because text has no concept of identity. `PostingList` is a string. The thing you actually care about — *which* PostingList, the one in the crate you're working in, the one with the methods you're about to call — that's not in the text. It's in the structure.

This is the whole workshop in one example. We're going to give the agent the structure. Hold onto this PostingList collision — we're coming back to it, live, in about twenty minutes, and it's going to resolve cleanly.

[Optional live: actually run rg in a terminal here. The room feeling grep fail is worth more than the slide.]
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
Step back from the one example. The deeper problem is that the agent has no memory of the codebase's shape. Every session it re-derives everything from raw text — re-reads files, re-greps, re-builds a mental model that evaporates the moment the context window closes. That's expensive, it's fragile, and it's shallow.

Shallow is the important one. Grep is a string matcher. It can tell you where the letters P-o-s-t-i-n-g-L-i-s-t appear. It cannot tell you "what implements this trait," or "what breaks if I change this return type," or "which of these three is the one in my crate." Those are questions about *relationships*, and relationships aren't in the text — you have to reconstruct them, and grep doesn't.

I've given a couple of talks about this for data warehouses — same disease there. The fix was the same shape too.
-->

---

## A context layer for code

A pre-analyzed, persistent model of the codebase the agent builds *on top of*.

<v-clicks>

- **Symbols** — every type, trait, function, with its real identity (not a string)
- **Relationships** — implements, returns, takes, has-field, contains — as edges
- **Computed once, queried many times** — the agent stops re-deriving and starts *knowing*

</v-clicks>

<div v-click>

Same idea I've shown for data warehouses — here it's for the codebase your agent lives in.

</div>

<!--
The answer — and this is the throughline of everything I work on at Typedef — is a context layer. A pre-analyzed, persistent model of the system that you compute once and the agent queries, instead of re-deriving from scratch every run.

For our data products this is a model of your warehouse — lineage, semantics, relationships. Today we're building the code version: a model of the codebase where every symbol has a real identity, and the relationships between symbols — implements, returns, takes, contains — are first-class edges you can traverse. The agent stops guessing about structure because the structure is just... there, precomputed, waiting to be asked.

That's what we're building in the next hour. Let me show you the shape of it before we start typing.
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

I want to be honest about this framing up front, because you're going to hear "levels of context" from at least two other people at this conference this week — it's in the water. I'm not claiming I invented it. What I think is actually worth your 90 minutes isn't the ladder — it's the specific question of what climbing to L3 buys you, measured honestly, and the part nobody talks about: whether the agent will even use it. Hold that thought.
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

The whole game is Rung 1. Resolution is the thing grep can't do — and it's the thing that turns three ambiguous PostingList strings into three distinct, identifiable types. Today we get Rung 1 for free, because Rust's compiler hands us resolved types in rustdoc JSON — and I'll be honest, I picked Rust *on purpose* for exactly that reason. I'll own that at the end. The lesson is the same in any language; Rust just lets us build the clean version in a weekend. [light seed — full payoff at the Python coda.]
-->

---
layout: center
---

## 🛠️ Build it — Part 1

Extract the symbols. **Rung 0 vs Rung 1.**

`notebook 01` · *open it now* · ~12 min

<!--
[HANDS-ON #1 — ~12 min] Okay. Everybody into notebook 01. Run the setup cell first — it checks your Neo4j is up and your key is loaded; if it complains, flag a volunteer, and meanwhile follow along, because the cached path will carry you.

What we're doing in this segment: extracting symbols from the qdrant `posting_list` crate two ways. First Rung 0 — tree-sitter — and you'll see it finds the names but can't resolve them. Then Rung 1 — rustdoc JSON — and you'll see the same symbols come back *resolved*: real qualified names, real types, re-exports followed. The contrast is the lesson. Walk the room. Regroup when most people have both extractions printed.
-->

---
layout: center
---

## 🛠️ Build it — Part 2

The flat index — and the collision returns.

`notebook 01` · L2 · ~8 min

<!--
[HANDS-ON #2 — ~8 min] Now we build L2 — the flat index over multiple crates — and we go looking for our friend PostingList. You'll get the three hits, just like my ripgrep at the start. And the point of this segment is to feel the ceiling: the index rows have a name and a location, but there is no field on them that says "this one is in the sparse crate and it's unrelated to that one." L2 ranks; it doesn't relate. That's the wall we climb over next.
-->

---
layout: center
---

## 🛠️ Build it — Part 3

Load the graph. Ask it what `grep` couldn't.

`notebook 01` · L3 → Neo4j · ~15 min

<!--
[HANDS-ON #3 — ~15 min] This is the centerpiece. We take the resolved Rung-1 symbols and their edges, and we load them into Neo4j — nodes for symbols, typed edges for the relationships. Then we open the Neo4j browser and actually look at it; seeing your codebase as a graph for the first time tends to land.

And then the two payoffs. One: the collision, resolved — we ask the graph for PostingList and we get each one back by its canonical path, in its crate, distinctly. Two: blast radius — "what depends on this type" — one hop, with file and line, no false positives. That's the question grep genuinely can't answer cleanly. Let people run it on a couple of types. Regroup for the payoff slide.
-->

---

## The payoff

The three `PostingList`s — resolved. And the question grep can't answer:

```cypher
// what depends on posting_list::PostingList?
MATCH (t:Struct {name:"PostingList"})<-[:RETURNS|TAKES|HAS_FIELD]-(d)
RETURN d.qualified_name, d.filepath, d.line
```

<v-clicks>

- Each `PostingList` comes back **distinct**, by canonical path + crate.
- Blast radius: the real dependents, **one hop**, with file:line. No re-grepping.

</v-clicks>

<!--
Here's where we are. Twenty minutes ago grep gave us three identical strings and a shrug. Now the graph gives us three distinct types, each tagged with the crate and the canonical path, and on top of that it answers the question we actually had — what depends on this thing if I change it — in a single hop, with evidence, no false positives.

This is real. The graph does something grep cannot. If I stopped here, this would be a perfectly nice "graphs beat grep" demo, and you'd nod, and you'd go to the Neo4j talk tomorrow and hear the same thing. But I'd be leaving out the most important part — the part I actually learned the hard way.
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
It ran grep.

We gave it a beautiful, precomputed, traversable model of the codebase — and it opened a terminal and started grepping like the graph wasn't even there. Glob, read_file, grep, read_file. It would occasionally poke the graph, get confused, and fall right back to wading through source files by hand. We built the entire L3 context layer, and the agent defaulted to L1 like nothing had changed.

This is the thing nobody puts on a slide. Everyone shows you the graph. Nobody shows you the agent refusing to use it. And once I saw it, I couldn't unsee it — it's been my single biggest day-to-day struggle building this stuff at Typedef. Building the context is the easy part. Getting the agent to *reach* for it is the job.
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
- **Don't coexist — dominate** — if grep's on the table, the prior wins. Make the graph a strict superset.
- **Make hop one pay** — empty result or a Cypher dump, and it bails to grep forever.

</v-clicks>

<!--
Here's what actually worked, and it's a little counterintuitive: stop fighting the prior. You will lose a prompt-engineering war against posttraining every time — "please use the graph tool" just makes it apologize and grep anyway. Instead, design *with* the reflex.

Name the tool `search`, not `query_graph` — let the model's "I'll search for it" instinct fire, and quietly route that into the graph. Return results that *look* like ripgrep — path, line, snippet — so the familiar shape greets it on the way in, and then you reveal the superpower, the traversal, on the follow-up. Don't put raw grep on the table next to the graph and hope it chooses well — it won't; make the graph a strict superset so there's no reason to reach past it. And make the very first call pay off, because if hop one returns an empty set or a wall of Cypher, the agent decides this tool is broken and falls back to grep and never comes back.

Notice what these have in common: not one of them is "convince the model." They're all "meet the reflex where it is."
-->

---
layout: center
---

## 🛠️ Make it reach for the graph

Your turn: shape the tool. Watch the agent switch.

`notebook 01` (build-your-own tool) → `notebook 02` · ~10 min

<!--
[HANDS-ON #4 — ~10 min] Your turn. In notebook 01 you'll write your own graph tool and wire it to the agent. Then in notebook 02 we do the before-and-after: run the agent with the graph presented badly, watch it grep; apply the nudges — the naming, the result shape — and re-run, and watch it actually reach for the graph and nail the answer in two hops. That switch, when you see it happen on your own screen, is the whole point of the workshop. Walk the room. Then we look at what it does to the numbers.
-->

---

## Does it actually help? Honestly.

30 questions across 5 crates. Graph agent vs grep agent. Same model, same budget.

<v-clicks>

- **Where the graph wins** — cross-crate "what depends on X," collisions: fewer tool calls, higher completeness. `[FILL: per-class numbers from nb02 cache]`
- **Where it ties** — "what implements trait T": grep can `rg "impl T for"`. Honest tie.
- **Where grep wins** — private internals, not in the public graph. *Grep wins. That's fine.*

</v-clicks>

<!--
So let's measure it, and let's measure it honestly — because the thing that makes me trust a result is someone telling me where it *loses*. Thirty questions, five crates, graph agent versus grep agent, same model, same turn budget.

[FILL from nb02 — the real numbers go here.] Where the graph genuinely wins is cross-crate dependency questions and collisions — fewer tool calls, higher completeness, the stuff grep has to wade through dozens of files to maybe get. Where it's an honest tie is "what implements this trait" — turns out `rg "impl Trait for"` is pretty good, so I'm not going to claim a win I don't have. And there's a whole class where grep *wins* — private internal symbols that aren't in our public-API graph at all. Grep wins those outright. That's not a defeat I'm hiding; it's a map of exactly what to put in the graph next.

This is a more useful result than "graphs win everything," which none of you would believe anyway.
-->

---

## The number that actually matters

The graph only helps if the agent *uses* it. So measure that.

<v-clicks>

- **Adoption rate** — % of code-lookups that hit the graph vs fell back to grep.
- Before the nudges: `[FILL]%`. After: `[FILL]%`.
- Every efficiency win upstream is **gated** by this one number.

</v-clicks>

<div v-click>

Nobody reports this. It's the whole ballgame.

</div>

<!--
But here's the metric I actually care about, and the one I haven't seen anybody else report. All those efficiency wins on the last slide? They're conditional. They only exist *if the agent reaches for the graph*. If it falls back to grep, you get nothing — you built infrastructure the agent ignores.

So we measure adoption rate directly: of all the times the agent went looking for code, what fraction actually used the graph versus fell back to the filesystem? [FILL: before/after.] Before the nudges it's low — the reflex wins. After we shape the tools, it jumps. That delta is the real result of this workshop. Every other number on the previous slide is downstream of this one. The graph's value isn't "is it better." It's "did we get the agent to use the better thing."
-->

---

## I've seen this before. In humans.

> Mandate a useful tool, and people's opinion of the tool goes *down*.

<v-clicks>

- Psychological **reactance** — forced adoption reads as lost autonomy; the judgment gets contaminated.
- "AI is useless" tracked *how the tool was handed to people* more than the tool.
- The agent has its own version. The handoff isn't a mandate — it's the **posttraining**.

</v-clicks>

<!--
And here's the thing that made all of this click for me. I wrote an essay recently about why smart engineers I respect call AI useless — and the punchline was that their opinion tracked *how the tool was handed to them* far more than the tool itself. Force a useful tool on someone and their assessment of it actually drops — there's a name for it, psychological reactance. Adoption mode is a confound sitting right on top of the signal.

I spent two thousand words on that about humans. And then I watched an agent refuse to use a graph I built, and realized it's the *same phenomenon, one layer down*. The agent isn't being mandated by a manager — it's being mandated by its own posttraining, which already decided how it likes to work. In both cases the tool's quality was never the deciding variable. The handoff was. Adoption is the hidden variable, for humans and for agents.
-->

---

## You're only as good as the harness

The model keeps getting better. Your job is the environment around it.

<v-clicks>

- Building the graph was the easy part.
- The eval loop, the tool design, the adoption fight — *that* was the work.
- The code was never the slow part. **Neither is the model.**

</v-clicks>

<!--
So let me zoom all the way out, because this is the same lesson I keep landing on no matter which direction I come at it from. With the data platform it was: the single agent with good tools and good context beat the elaborate eight-agent system. In the essay it was: you're only as good as your ability to build the harnesses and the loops around the agent. And here it's: building the graph took an afternoon; getting the agent to *use* it — the eval loop, the tool ergonomics, the adoption fight — that was the actual engineering.

The models keep getting better on their own. They are not getting better at using *your* context layer — that part is on you. The code was never the slow part. It turns out the model isn't either. The slow part is, and always was, the environment you build around it.
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

<!--
Python. No compiler is waiting to hand you resolved types — and that is exactly where this gets good.

Look at this. A re-export in an __init__, and an attribute chain: c.session.execute. Grep for Client and you get the re-export line, the class definition, and two hundred call sites — and not one of them tells you what .session actually is or what .execute touches. Text doesn't know. ctags doesn't know. There is no homework to copy.

So you do Rung 1 yourself — statically, no runtime, with something like Griffe: rebuild the types, follow the re-export, resolve the names. And the second you've done that, you load it into the same graph, and you get the same blast radius — except now it's a capability that did not exist until you built it, because nothing else was going to give it to you.

In Rust the graph looked like a convenience. In Python it is the only road there. Same recipe in every language: extract, resolve, graph, traversal tools. Rust was the clean demo. Python is where you actually need it — and it's where I'd point you first tomorrow morning.

[Sunday: point this at a REAL small package they can clone — fenic itself works. The Griffe parser already exists at src/context_workshop/parsers/python_griffe.py. Even a 60-second live `griffe`-resolved blast-radius beats a static slide here.]
-->

---

## Rung 2 — meaning <span style="opacity:.45">· optional, if time</span>

Everything so far is *deterministic* — structure + resolution, no LLM in the build. Rung 2 adds **meaning**, and it's where Fenic earns its keep.

```python
df.with_column("summary", fc.semantic.map(
    "In one sentence, what is this Rust item for?\n\n{{b}}", b=fc.col("blurb")))
```

<v-clicks>

- One operator → a purpose summary on **every node**, grounded on the same `file:line`.
- `search` now returns *what it's for*, not just *where it is*.

</v-clicks>

<!--
[OPTIONAL — FIRST TO CUT. Only if the build + eval + reversal all landed clean and we have ~10 min.]

Everything we built today is deterministic — tree-sitter for structure, rustdoc for resolution, no LLM anywhere in the build. Rung 2 is the third rung: meaning. And this is where Fenic, our transformation layer, comes in. One operator — semantic.map — runs an LLM over every symbol and writes a one-sentence "what is this for" summary as a new column. We attach that to the same graph nodes, grounded on the same file and line. So now when the agent searches, it gets back not just WHERE something is, but WHAT IT'S FOR — structure and meaning on the same node.
-->

---

## Add a factor? Edit the prompt. <span style="opacity:.45">· optional</span>

Want the model to *also* weigh stability, the signature, who depends on it? That's the entire change:

```python
"...Also flag whether it's a STABLE public API or an INTERNAL detail,
 judging from its signature.\n\n{{b}}\nsignature: {{sig}}",  b=..., sig=fc.col("signature")
```

<div v-click>

One line of prompt, one column binding. **A semantic layer is where "consider one more thing" costs a sentence — not a pipeline.**

</div>

<!--
And here's the part worth taking home if you take anything about Fenic. Say you want the model to weigh one more factor — whether something looks like a stable public API or an internal detail, judging from its signature. In a normal data pipeline that's a schema change, a new stage, plumbing. Here it's one more line in the prompt and one more column binding: sig equals the signature column. That's the whole edit. The point of a declarative semantic layer is that "have the LLM consider one more thing" costs you a sentence, not a sprint. [Then straight into where-this-goes.]
-->

---
layout: center
---

## Where this goes

The public-API floor was the start. The edges we didn't draw are the roadmap:

**Private internals** (where grep beat us) · **call graphs** (SCIP — true "who calls this") · **Rung 2** (meaning, the LLM in the *build* path)

<!--
And past that, the edges we deliberately didn't draw today — because the honest losses ARE the roadmap.

The private-internals class grep beat us on? That's the next index. Call graphs through SCIP get you true "who calls this," not just "who references the type." And Rung 2 — semantic meaning — is where the LLM finally earns a seat in the build pipeline, enriching the graph, never on the serving path. That's the v2. But the recipe — extract, resolve, graph, traverse — you already have all of it.
-->

---
layout: center
---

## The agent will grep anyway —

## until you design for the reflex.

Brandon Callender · Typedef

<sup>*Build it yourself:* `github.com/...` · *come find me*</sup>

<!--
So that's the workshop. You built a context layer for a coding agent — a real graph over a real codebase. You watched the agent ignore it. And you watched it switch the moment you stopped fighting the prior and started designing for it.

The one thing I want you to walk out with: the agent will grep anyway — until you build the environment that makes the better tool the path of least resistance. Building the context is the easy part. The handoff is the job.

The repo's up there, everything we did today is in it. Thank you — come find me, I'll be around all week.
-->
