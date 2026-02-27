
# jsonedit

**A structured document editor for composing meaning in JSON.**

jsonedit is a tree-based editor designed for working with **hierarchical ideas**, not just JSON text.
It treats JSON as a *living document* — something you assemble, reshape, and extract from — rather than a file you manually type.

It is especially well suited for **LLM prompt construction, context curation, and structured knowledge editing**.

---

## Screenshot

![jsonedit screenshot](docs/img/screenshot-1.png)

---

## What jsonedit is (and is not)

jsonedit is **not** a traditional programmer’s JSON editor.

It is a **document compositor** built around one core idea:

> Edit meaning locally. Commit structure deliberately.

Instead of editing lines of text, you work directly with the document’s tree structure — selecting nodes, reshaping hierarchies, and exporting semantic fragments when needed.

---

## Why it exists

Modern workflows — especially those involving LLMs — often look like this:

* assemble structured prompts
* rearrange examples or schemas
* experiment safely
* extract only the relevant subtree
* paste into an AI context window
* iterate

Traditional editors treat JSON as text.

jsonedit treats JSON as **thought structure**.

---

## Core Concepts

### 🌲 Structure First

The primary editing unit is a **node**, not a line.

Common operations include:

* raise / lower items in hierarchy
* duplicate subtrees
* insert siblings
* rename keys
* delete with intelligent reselection

Navigation uses structural paths instead of line numbers.

---

### ✍️ Split-Brain Editing

Two coordinated views:

* **Tree view** → orientation and structure
* **Text pane** → focused semantic rewriting

You always know *where* you are structurally while editing *what* something means.

---

### 🧪 Safe Editing via Explicit Commit

Text edits remain sandboxed until you explicitly commit them.

This allows:

* experimentation without breaking structure
* temporary invalid JSON while thinking
* deliberate structural mutation

No accidental global edits.

---

### 📦 Export is a First-Class Action

jsonedit assumes you frequently want pieces of documents.

You can quickly copy:

* entire documents
* selected subtrees
* pretty or compact JSON

Ideal for moving structured context into LLM prompts.

---

### 🧠 JSON as a Living Document

Documents may include metadata and workspace information, encouraging long-lived structured artifacts rather than disposable config files.

---

## Ideal Use Cases

jsonedit works best when JSON represents **ideas**, not just data.

### ✅ Excellent for

* LLM prompt composition
* Context packaging for AI systems
* Agent or tool configuration
* Structured writing and outlining
* Dataset annotation
* Knowledge assembly in hierarchical form

Typical workflow:

1. Select subtree
2. Rewrite locally
3. Commit structure
4. Copy compressed node
5. Paste into LLM context

---

### ❌ Not Designed For

* General programming JSON editing
* Schema validation or linting
* Large machine-generated JSON files
* Collaborative merge workflows
* High-speed code typing environments

If you want VS Code for JSON — use VS Code.

jsonedit optimizes for **clarity of structure**, not typing speed.

---

## Install

```bash
pip install jsonedit
```

---

## Run

```bash
jsonedit
```

Open a file directly:

```bash
jsonedit <filepath>
```

---

## Requirements

* Python
* Tkinter available in your Python installation

(jsonedit is a desktop GUI application.)

---

## Philosophy

jsonedit is built on a few assumptions:

* JSON encodes ideas, not just data.
* Structure matters more than formatting.
* Users think in subtrees rather than lines.
* Editing should be deliberate and reversible.
* Exporting fragments is a primary activity.

---

## License

CC0 1.0 Universal — public domain.
See `LICENSE`.

