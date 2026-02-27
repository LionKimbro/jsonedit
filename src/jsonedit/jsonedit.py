# jsonedit.py
# JSON Tree Editor
# v0.1-draft

import json
import sys
import copy
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.simpledialog import askstring
from pathlib import Path
import os
import tempfile


# ----------------------------
# globals
# ----------------------------

g_state = {
    "doc":             None,
    "file_path":       None,
    "selected_path":   None,
    "selected_kind":   None,
    "dirty":           0,
    "text_mode":       "json",
    "status_validity": "(no document)",
    "status_error":    "",
    "find_term":       None,
    "find_matches":    [],
    "find_index":      -1,
}

g_widget_state = {
    "path_to_iid":          {},
    "iid_to_path":          {},
    "iid_to_kind":          {},
    "expanded_paths":       set(),
    "suppress_tree_select": 0,
    "_iid_counter":         0,
}

widgets = {}

THEME_DARK = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "muted": "#808080",
    "accent": "#569cd6",
    "error": "#f44747",
    "button_bg": "#2d2d2d",
    "button_active_bg": "#3a3a3a",
    "button_fg": "#e6e6e6",
    "scroll_trough": "#2a2a2a",

    "text_bg": "#1e1e1e",
    "text_fg": "#d4d4d4",
    "text_insert": "#d4d4d4",
    "text_select_bg": "#264f78",
    "text_select_fg": "#ffffff",

    "tree_bg": "#1e1e1e",
    "tree_fg": "#d4d4d4",
    "tree_select_bg": "#264f78",
    "tree_select_fg": "#ffffff",
}


# ----------------------------
# tiny helpers
# ----------------------------

def is_leaf_string_path(doc, p):
    try:
        obj = get_at_path(doc, p)
    except Exception:
        return False
    return isinstance(obj, str)

def pretty(obj, indent=2):
    return json.dumps(obj, indent=indent, ensure_ascii=False, sort_keys=False)

def compact(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

def path_to_str(p):
    if p is None:
        return ""
    return "[" + ", ".join(repr(x) for x in p) + "]"

def get_at_path(doc, p):
    obj = doc
    for k in p:
        obj = obj[k]
    return obj

def set_at_path(doc, p, value):
    if p is None or len(p) == 0:
        return value
    obj = doc
    for k in p[:-1]:
        obj = obj[k]
    obj[p[-1]] = value
    return doc

def delete_at_path(doc, p):
    obj = doc
    for k in p[:-1]:
        obj = obj[k]
    last = p[-1]
    if isinstance(obj, dict):
        del obj[last]
    else:
        del obj[last]
    return doc

def parent_path(p):
    if p is None or len(p) == 0:
        return None
    return p[:-1]

def last_key(p):
    if p is None or len(p) == 0:
        return None
    return p[-1]

def deep_copy(x):
    return copy.deepcopy(x)

def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def extract_embedded_editor_config(doc):
    # Returns a dict or None

    # Case 1: root is dict
    if isinstance(doc, dict):
        cfg = doc.get("jsonedit")
        if isinstance(cfg, dict):
            return cfg

    # Case 2: root is list, check element 0
    if isinstance(doc, list) and doc:
        first = doc[0]
        if isinstance(first, dict):
            cfg = first.get("jsonedit")
            if isinstance(cfg, dict):
                return cfg

    return None

def collect_key_paths(node, current_path, target_key, out_paths):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == target_key:
                out_paths.append(current_path + [key])
            collect_key_paths(value, current_path + [key], target_key, out_paths)

    elif isinstance(node, list):
        for i, value in enumerate(node):
            collect_key_paths(value, current_path + [i], target_key, out_paths)


# ----------------------------
# validation
# ----------------------------

def parse_json_text(s):
    try:
        obj = json.loads(s)
        return obj, None
    except json.JSONDecodeError as e:
        msg = f"{e.msg} (line {e.lineno}, col {e.colno})"
        return None, msg


# ----------------------------
# tree helpers
# ----------------------------

def first_bifurcation_path(doc):
    p = tuple()
    obj = doc
    while True:
        if isinstance(obj, list) and len(obj) == 1:
            p = p + (0,)
            obj = obj[0]
            continue
        if isinstance(obj, dict) and len(obj) == 1:
            k = next(iter(obj))
            p = p + (k,)
            obj = obj[k]
            continue
        return p

def label_for(p, kind, obj):
    # show keys/indices and type markers
    if kind == "root":
        if isinstance(obj, dict):
            return "root {}"
        if isinstance(obj, list):
            return "root []"
        return "root"
    k = last_key(p)
    if kind == "object-key":
        if isinstance(obj, dict):
            t = "{}" if isinstance(obj, dict) else "[]" if isinstance(obj, list) else "leaf"
            return f"{k!r}: {t}"
        return f"{k!r}"
    if kind == "array-element":
        t = "{}" if isinstance(obj, dict) else "[]" if isinstance(obj, list) else "leaf"
        return f"[{k}]: {t}"
    if kind == "object":
        return "{}"
    if kind == "array":
        return "[]"
    return "leaf"


# ----------------------------
# reducer helpers
# ----------------------------

def _derive_text_mode(doc, path):
    if doc is None or path is None:
        return "json"
    try:
        obj = get_at_path(doc, path)
        return "value" if isinstance(obj, str) else "json"
    except Exception:
        return "json"

def _kind_of(doc, path):
    if path is None:
        return None
    if path == tuple():
        return "root"
    pp = parent_path(path)
    parent = get_at_path(doc, pp)
    if isinstance(parent, dict):
        return "object-key"
    if isinstance(parent, list):
        return "array-element"
    return "value"


# ----------------------------
# reducer
# ----------------------------

def reducer(state, action):
    t = action["type"]
    if t in ("LOAD_DOC", "RELOAD_DOC"):
        return {**state,
            "doc": action["doc"], "file_path": action["file_path"],
            "selected_path": tuple(), "selected_kind": "root",
            "dirty": 0,
            "text_mode": _derive_text_mode(action["doc"], tuple()),
            "status_validity": "reloaded" if t == "RELOAD_DOC" else "loaded",
            "status_error": "",
            "find_term": None, "find_matches": [], "find_index": -1,
        }
    if t == "LOAD_FROM_CLIPBOARD":
        return {**state,
            "doc": action["doc"], "file_path": None,
            "selected_path": tuple(), "selected_kind": "root",
            "dirty": 0,
            "text_mode": _derive_text_mode(action["doc"], tuple()),
            "status_validity": "created", "status_error": "",
            "find_term": None, "find_matches": [], "find_index": -1,
        }
    if t == "SAVE_DONE":
        return {**state,
            "dirty": 0, "file_path": action["file_path"],
            "status_validity": "saved", "status_error": "",
        }
    if t == "SELECT_PATH":
        s = {**state, "selected_path": action["path"], "selected_kind": action["kind"]}
        s["text_mode"] = _derive_text_mode(s["doc"], s["selected_path"])
        return s
    if t == "COMMIT_TEXT":
        s = {**state, "doc": action["doc"], "dirty": 1,
             "status_validity": "valid", "status_error": ""}
        s["text_mode"] = _derive_text_mode(s["doc"], s["selected_path"])
        return s
    if t == "COMMIT_FAIL":
        return {**state, "status_validity": "INVALID", "status_error": action["error"]}
    if t in ("RAISE_ITEM", "LOWER_ITEM", "INSERT_AFTER", "DUPLICATE", "RENAME_KEY", "DELETE_ITEM"):
        s = {**state,
            "doc": action["doc"],
            "selected_path": action["selected_path"],
            "selected_kind": action.get("selected_kind", state["selected_kind"]),
            "dirty": 1,
        }
        s["text_mode"] = _derive_text_mode(s["doc"], s["selected_path"])
        if action.get("status_validity") is not None:
            s["status_validity"] = action["status_validity"]
        if action.get("status_error") is not None:
            s["status_error"] = action["status_error"]
        return s
    if t == "FIND_START":
        s = {**state,
            "find_term": action["term"], "find_matches": action["matches"],
            "find_index": action["index"],
            "selected_path": action["selected_path"], "selected_kind": action["selected_kind"],
            "status_error": action["status_error"],
        }
        s["text_mode"] = _derive_text_mode(s["doc"], s["selected_path"])
        return s
    if t == "FIND_ADVANCE":
        s = {**state,
            "find_index": action["index"],
            "selected_path": action["selected_path"], "selected_kind": action["selected_kind"],
            "status_error": action["status_error"],
        }
        s["text_mode"] = _derive_text_mode(s["doc"], s["selected_path"])
        return s
    if t == "FIND_CLEAR":
        return {**state, "find_term": None, "find_matches": [], "find_index": -1,
                "status_error": action["status_error"]}
    if t == "SET_STATUS":
        s = dict(state)
        if action.get("validity") is not None:
            s["status_validity"] = action["validity"]
        if action.get("error") is not None:
            s["status_error"] = action["error"]
        return s
    return state


# ----------------------------
# dispatch
# ----------------------------

def dispatch(action):
    global g_state
    old = g_state
    new = reducer(old, action)
    realize(old, new, action)
    g_state = new


# ----------------------------
# realize sub-functions
# ----------------------------

def _new_iid():
    c = g_widget_state["_iid_counter"] + 1
    g_widget_state["_iid_counter"] = c
    return f"n{c}"

def _insert_node(doc, parent_iid, p, kind):
    obj = get_at_path(doc, p) if p is not None else doc
    iid = _new_iid()
    txt = label_for(p, kind, obj)
    widgets["tree"].insert(parent_iid, "end", iid=iid, text=txt)
    g_widget_state["iid_to_path"][iid] = p
    g_widget_state["iid_to_kind"][iid] = kind
    g_widget_state["path_to_iid"][p] = iid
    return iid

def _remember_expanded_paths():
    g_widget_state["expanded_paths"].clear()

    def walk(iid):
        if widgets["tree"].item(iid, "open"):
            p = g_widget_state["iid_to_path"].get(iid)
            if p is not None:
                g_widget_state["expanded_paths"].add(p)
        for c in widgets["tree"].get_children(iid):
            walk(c)

    for iid in widgets["tree"].get_children(""):
        walk(iid)

def _restore_expanded_paths():
    for p in list(g_widget_state["expanded_paths"]):
        iid = g_widget_state["path_to_iid"].get(p)
        if iid:
            widgets["tree"].item(iid, open=True)

def _rebuild_tree(doc):
    """Replaces build_tree + refresh_tree; preserves expanded paths."""
    _remember_expanded_paths()

    widgets["tree"].delete(*widgets["tree"].get_children(""))
    g_widget_state["path_to_iid"].clear()
    g_widget_state["iid_to_path"].clear()
    g_widget_state["iid_to_kind"].clear()

    if doc is None:
        return

    root_path = tuple()
    root_iid = _insert_node(doc, "", root_path, "root")

    def rec(parent_iid, p):
        obj = get_at_path(doc, p)
        if isinstance(obj, dict):
            for k in obj.keys():
                cp = p + (k,)
                kid = _insert_node(doc, parent_iid, cp, "object-key")
                rec(kid, cp)
        elif isinstance(obj, list):
            for i in range(len(obj)):
                cp = p + (i,)
                kid = _insert_node(doc, parent_iid, cp, "array-element")
                rec(kid, cp)

    rec(root_iid, root_path)
    _restore_expanded_paths()

def _expand_tree_to_path(p):
    if p is None:
        return
    cur = tuple()
    while True:
        iid = g_widget_state["path_to_iid"].get(cur)
        if iid:
            widgets["tree"].item(iid, open=True)
        if cur == p:
            break
        cur = cur + (p[len(cur)],)

def _sync_tree_selection(path):
    """Replaces select_path widget part; uses suppress_tree_select guard."""
    iid = g_widget_state["path_to_iid"].get(path)
    if not iid:
        return
    g_widget_state["suppress_tree_select"] += 1
    try:
        widgets["tree"].selection_set(iid)
        widgets["tree"].focus(iid)
        widgets["tree"].see(iid)
    finally:
        g_widget_state["suppress_tree_select"] -= 1

def set_text(s, cursor="start"):
    t = widgets["text"]
    t.delete("1.0", "end")
    t.insert("1.0", s)

    if cursor == "start":
        t.mark_set("insert", "1.0")
        t.see("1.0")
    elif cursor == "select-entire-value":
        t.mark_set("insert", "1.0")
        t.tag_remove("sel", "1.0", "end")
        t.tag_add("sel", "1.0", "end-1c")
        t.see("1.0")

    t.tag_remove("sel", "1.0", "end") if cursor == "start" else None
    t.edit_modified(False)

def _refresh_text_pane(state, action=None):
    """Replaces refresh_text_for_path."""
    doc = state["doc"]
    path = state["selected_path"]

    # Determine cursor mode based on action type
    action_type = action["type"] if action else None
    if action_type in ("INSERT_AFTER", "DUPLICATE"):
        cursor = "select-entire-value"
    else:
        cursor = "start"

    if doc is None:
        set_text("", cursor="start")
        return

    obj = get_at_path(doc, path) if path is not None else doc

    if isinstance(obj, str):
        set_text(obj, cursor=cursor)
    else:
        set_text(pretty(obj, indent=2), cursor=cursor)

def _refresh_menu_enablement(state):
    """Replaces refresh_menu_enablement; takes state not globals."""
    if "edit_menu" not in widgets:
        return

    edit_menu = widgets["edit_menu"]

    doc = state["doc"]
    kind = state["selected_kind"]

    can_struct = (doc is not None) and (kind in ("object-key", "array-element"))
    can_rename = (doc is not None) and (kind == "object-key")

    # Edit menu indices:
    # 0 Search
    # 1 Repeat Search
    # 2 separator
    # 3 Raise
    # 4 Rename
    # 5 Delete
    # 6 Duplicate
    # 7 Insert
    # 8 Lower
    edit_menu.entryconfig(0, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(1, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(3, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(4, state=("normal" if can_rename else "disabled"))
    edit_menu.entryconfig(5, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(6, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(7, state=("normal" if can_struct else "disabled"))
    edit_menu.entryconfig(8, state=("normal" if can_struct else "disabled"))

def _update_title(state):
    """Replaces set_title."""
    base = "JSON Tree Editor"

    cfg = extract_embedded_editor_config(state["doc"]) or {}
    suffix = cfg.get("window-title")

    if isinstance(suffix, str) and suffix.strip():
        title = f"{base}: {suffix.strip()}"
    elif state["file_path"]:
        title = f"{base} — {state['file_path'].name}"
    else:
        title = base

    widgets["root"].title(title)

def _update_status_path(path):
    """Updates widgets['status_path'] label text."""
    widgets["status_path"].configure(text=path_to_str(path))

def _update_dirty_indicator(dirty):
    """Replaces update_dirty_indicator."""
    w = widgets.get("status_dirty")
    if w is None:
        return
    if dirty:
        w.configure(fg="#f44747")  # red
    else:
        w.configure(fg="#4ec94e")  # green


# ----------------------------
# realize
# ----------------------------

def realize(old, new, action=None):
    doc_changed = (new["doc"] is not old["doc"])

    _LOAD_ACTIONS = ("LOAD_DOC", "RELOAD_DOC", "LOAD_FROM_CLIPBOARD")

    if doc_changed:
        _rebuild_tree(new["doc"])
        if action and action["type"] in _LOAD_ACTIONS:
            _expand_tree_to_path(first_bifurcation_path(new["doc"]))
        _sync_tree_selection(new["selected_path"])
        _refresh_text_pane(new, action)
        _refresh_menu_enablement(new)
        _update_title(new)
        _update_status_path(new["selected_path"])
    else:
        if new["selected_path"] != old["selected_path"]:
            _sync_tree_selection(new["selected_path"])
            if not (action and action.get("suppress_text_refresh")):
                _refresh_text_pane(new, action)
            _update_status_path(new["selected_path"])
        if new["selected_kind"] != old["selected_kind"]:
            _refresh_menu_enablement(new)

    if new["dirty"] != old["dirty"]:
        _update_dirty_indicator(new["dirty"])
    if new["status_validity"] != old["status_validity"]:
        widgets["status_validity"].configure(text=new["status_validity"])
    if new["status_error"] != old["status_error"]:
        widgets["status_error"].configure(text=new["status_error"])
    if new["file_path"] != old["file_path"] and not doc_changed:
        _update_title(new)


# ----------------------------
# event handlers
# ----------------------------

def handle_tree_selection_changed(event=None):
    if g_widget_state["suppress_tree_select"]:
        return
    sel = widgets["tree"].selection()
    if not sel:
        return
    iid = sel[0]
    p = g_widget_state["iid_to_path"].get(iid)
    kind = g_widget_state["iid_to_kind"].get(iid)
    if p == g_state["selected_path"]:
        return
    dispatch({"type": "SELECT_PATH", "path": p, "kind": kind})

def handle_text_modified(event=None):
    if widgets["text"].edit_modified():
        dispatch({"type": "SET_STATUS", "validity": "(uncommitted edits)", "error": None})


# ----------------------------
# file i/o
# ----------------------------

def handle_open_file_command():
    p = filedialog.askopenfilename(
        title="Open JSON",
        filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
    )
    if not p:
        return
    open_file(Path(p))


def handle_reload_file_command():
    if not g_state["file_path"]:
        messagebox.showerror("Reload", "No file loaded previously.")
        return
    open_file(g_state["file_path"])


def open_file(p: Path):
    is_reloading = (p == g_state["file_path"])
    try:
        s = p.read_text(encoding="utf-8")
    except Exception as e:
        messagebox.showerror("Open", f"Could not read file:\n{e}")
        return

    obj, err = parse_json_text(s)
    if err:
        messagebox.showerror("Open", f"Invalid JSON:\n{err}")
        return
    if not isinstance(obj, (dict, list)):
        messagebox.showerror("Open", "Root must be an object {} or array [].")
        return

    action_type = "RELOAD_DOC" if is_reloading else "LOAD_DOC"
    dispatch({"type": action_type, "doc": obj, "file_path": p})


def save_file():
    if g_state["doc"] is None:
        return
    file_path = g_state["file_path"]
    if file_path is None:
        p = filedialog.asksaveasfilename(
            title="Save JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not p:
            return
        file_path = Path(p)

    try:
        s = pretty(g_state["doc"], indent=2) + "\n"
        atomic_write_text(file_path, s)
    except Exception as e:
        messagebox.showerror("Save", f"Could not write file:\n{e}")
        return

    dispatch({"type": "SAVE_DONE", "file_path": file_path})

def create_from_clipboard():
    try:
        s = widgets["root"].clipboard_get()
    except Exception:
        messagebox.showerror("Clipboard", "Clipboard is empty or unavailable.")
        return

    obj, err = parse_json_text(s)
    if err:
        messagebox.showerror("Clipboard", f"Invalid JSON:\n{err}")
        return
    if not isinstance(obj, (dict, list)):
        messagebox.showerror("Clipboard", "Root must be an object {} or array [].")
        return

    dispatch({"type": "LOAD_FROM_CLIPBOARD", "doc": obj})

def exit_application():
    widgets["root"].destroy()

def open_containing_folder():
    if g_state["file_path"] is None:
        return
    folder = g_state["file_path"].parent
    try:
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as e:
        messagebox.showerror("Open Folder", f"Could not open folder:\n{e}")

def spawn_new_instance():
    try:
        if shutil.which("jsonedit"):
            subprocess.Popen(["jsonedit"])
            return
        subprocess.Popen([sys.executable, "-m", "jsonedit"])
    except Exception as e:
        messagebox.showerror("New Instance", f"Could not launch new instance:\n{e}")


# ----------------------------
# clipboard ops
# ----------------------------

def write_clipboard(s):
    root = widgets["root"]
    root.clipboard_clear()
    root.clipboard_append(s)

def copy_entire_document(flags="P"):
    if g_state["doc"] is None:
        return
    s = pretty(g_state["doc"], indent=2) if flags != "C" else compact(g_state["doc"])
    write_clipboard(s)
    dispatch({"type": "SET_STATUS", "validity": "copied", "error": ""})

def copy_selected_subtree(flags="P"):
    if g_state["doc"] is None or g_state["selected_path"] is None:
        return
    obj = get_at_path(g_state["doc"], g_state["selected_path"])
    s = pretty(obj, indent=2) if flags != "C" else compact(obj)
    write_clipboard(s)
    dispatch({"type": "SET_STATUS", "validity": "copied node", "error": ""})


# ----------------------------
# commit: text -> tree
# ----------------------------

def apply_text_to_tree(event=None):
    if g_state["doc"] is None or g_state["selected_path"] is None:
        return "break"

    s = widgets["text"].get("1.0", "end-1c")
    p = g_state["selected_path"]
    if g_state["text_mode"] == "value":
        obj, err = s, None
    else:
        obj, err = parse_json_text(s)
    if err:
        dispatch({"type": "COMMIT_FAIL", "error": str(err)})
        return "break"

    if p == tuple():
        if not isinstance(obj, (dict, list)):
            dispatch({"type": "COMMIT_FAIL", "error": "Root must be {} or []."})
            return "break"

    # Build new_doc via deepcopy then mutate so doc identity always changes
    new_doc = copy.deepcopy(g_state["doc"])
    if p == tuple():
        new_doc = obj
    else:
        set_at_path(new_doc, p, obj)

    dispatch({"type": "COMMIT_TEXT", "doc": new_doc})
    return "break"


# ----------------------------
# prompts
# ----------------------------

def prompt_new_object_key(title="New JSON Key", message="Enter a name for the new key:"):
    while True:
        k = simpledialog.askstring(title, message, parent=widgets["root"])
        if k is None:
            return None
        k = k.strip()
        if not k:
            messagebox.showerror(title, "Key must be non-empty.")
            continue
        return k

def confirm_delete():
    return messagebox.askyesno("Delete Item", "Delete the selected item?")

def prompt_find_key(previous_term):
    return askstring(
        title="Search for:",
        prompt="",
        initialvalue=previous_term or ""
    )


# ----------------------------
# structural operations
# ----------------------------

def _move_structural_item(direction):
    """Shared implementation for raise (-1) and lower (+1)."""
    if g_state["doc"] is None:
        return
    kind = g_state["selected_kind"]
    if kind not in ("object-key", "array-element"):
        return
    p = g_state["selected_path"]
    pp = parent_path(p)
    if pp is None:
        return

    new_doc = copy.deepcopy(g_state["doc"])
    parent = get_at_path(new_doc, pp)
    action_type = "RAISE_ITEM" if direction == -1 else "LOWER_ITEM"

    if isinstance(parent, list):
        i = last_key(p)
        if len(parent) <= 1:
            return
        j = (i + direction) % len(parent)
        parent[i], parent[j] = parent[j], parent[i]
        np = pp + (j,)
        dispatch({"type": action_type, "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})
        return

    if isinstance(parent, dict):
        k = last_key(p)
        keys = list(parent.keys())
        if len(keys) <= 1:
            return
        i = keys.index(k)
        j = (i + direction) % len(keys)
        keys[i], keys[j] = keys[j], keys[i]
        new_parent = {kk: parent[kk] for kk in keys}
        new_doc = set_at_path(new_doc, pp, new_parent)
        np = pp + (k,)
        dispatch({"type": action_type, "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})

def raise_structural_item():
    _move_structural_item(-1)

def lower_structural_item():
    _move_structural_item(+1)

def insert_structural_item_after():
    if g_state["doc"] is None:
        return
    kind = g_state["selected_kind"]
    if kind not in ("object-key", "array-element"):
        return
    p = g_state["selected_path"]
    pp = parent_path(p)

    new_doc = copy.deepcopy(g_state["doc"])
    parent = get_at_path(new_doc, pp)

    if isinstance(parent, list):
        i = last_key(p)
        parent.insert(i + 1, None)
        np = pp + (i + 1,)
        dispatch({"type": "INSERT_AFTER", "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})
        widgets["text"].focus_set()
        return

    if isinstance(parent, dict):
        oldk = last_key(p)
        k = prompt_new_object_key()
        if k is None:
            return
        if k in parent:
            messagebox.showerror("New JSON Key", "Key already exists in this object.")
            return

        keys = list(parent.keys())
        i = keys.index(oldk)
        keys.insert(i + 1, k)

        new_parent = {}
        for kk in keys:
            if kk == k:
                new_parent[kk] = None
            else:
                new_parent[kk] = parent[kk]
        new_doc = set_at_path(new_doc, pp, new_parent)
        np = pp + (k,)
        dispatch({"type": "INSERT_AFTER", "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})
        widgets["text"].focus_set()
        return

def duplicate_structural_item():
    if g_state["doc"] is None:
        return
    kind = g_state["selected_kind"]
    if kind not in ("object-key", "array-element"):
        return
    p = g_state["selected_path"]
    pp = parent_path(p)

    new_doc = copy.deepcopy(g_state["doc"])
    parent = get_at_path(new_doc, pp)

    if isinstance(parent, list):
        i = last_key(p)
        parent.insert(i + 1, deep_copy(parent[i]))
        np = pp + (i + 1,)
        dispatch({"type": "DUPLICATE", "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})
        widgets["tree"].focus_set()
        return

    if isinstance(parent, dict):
        oldk = last_key(p)
        k = prompt_new_object_key(title="New JSON Key", message="Enter a name for the duplicated key:")
        if k is None:
            return
        if k in parent:
            messagebox.showerror("New JSON Key", "Key already exists in this object.")
            return

        keys = list(parent.keys())
        i = keys.index(oldk)
        keys.insert(i + 1, k)

        new_parent = {}
        for kk in keys:
            if kk == k:
                new_parent[kk] = deep_copy(parent[oldk])
            else:
                new_parent[kk] = parent[kk]
        new_doc = set_at_path(new_doc, pp, new_parent)
        np = pp + (k,)
        dispatch({"type": "DUPLICATE", "doc": new_doc,
                  "selected_path": np, "selected_kind": _kind_of(new_doc, np)})
        widgets["tree"].focus_set()
        return

def rename_structural_key():
    if g_state["doc"] is None:
        return
    if g_state["selected_kind"] != "object-key":
        return
    p = g_state["selected_path"]
    pp = parent_path(p)

    new_doc = copy.deepcopy(g_state["doc"])
    parent = get_at_path(new_doc, pp)

    if not isinstance(parent, dict):
        return

    oldk = last_key(p)
    k = prompt_new_object_key(title="Rename Key", message="Enter the new key name:")
    if k is None:
        return
    if k == oldk:
        return
    if k in parent:
        messagebox.showerror("Rename Key", "Key already exists in this object.")
        return

    keys = list(parent.keys())
    i = keys.index(oldk)
    keys[i] = k

    val = parent[oldk]
    new_parent = {}
    for kk in keys:
        if kk == k:
            new_parent[kk] = val
        else:
            new_parent[kk] = parent[kk]
    new_doc = set_at_path(new_doc, pp, new_parent)

    np = pp + (k,)
    dispatch({"type": "RENAME_KEY", "doc": new_doc,
              "selected_path": np, "selected_kind": _kind_of(new_doc, np),
              "suppress_text_refresh": True})

def pick_selection_after_delete(doc, pp, removed_key):
    parent = get_at_path(doc, pp)

    if isinstance(parent, list):
        n = len(parent)
        if n == 0:
            return pp, "parent"
        i = removed_key
        if i < n:
            return pp + (i,), "next-sibling"
        if i - 1 >= 0:
            return pp + (i - 1,), "previous-sibling"
        return pp, "parent"

    if isinstance(parent, dict):
        keys = list(parent.keys())
        if not keys:
            return pp, "parent"
        return pp + (keys[-1],), "previous-sibling"

    return pp, "parent"

def delete_structural_item():
    if g_state["doc"] is None:
        return
    kind = g_state["selected_kind"]
    if kind not in ("object-key", "array-element"):
        return
    if not confirm_delete():
        return

    p = g_state["selected_path"]
    pp = parent_path(p)
    if pp is None:
        return

    removed = last_key(p)

    # Check edit_modified BEFORE dispatch (invariant 4)
    text_has_uncommitted = widgets["text"].edit_modified()

    new_doc = copy.deepcopy(g_state["doc"])
    delete_at_path(new_doc, p)

    # Decide new selection
    np, classification = pick_selection_after_delete(new_doc, pp, removed)
    new_kind = _kind_of(new_doc, np)

    if text_has_uncommitted:
        dispatch({"type": "DELETE_ITEM", "doc": new_doc,
                  "selected_path": np, "selected_kind": new_kind,
                  "suppress_text_refresh": True,
                  "status_validity": "(uncommitted edits)",
                  "status_error": "Selection changed; text not refreshed (uncommitted edits)."})
    else:
        dispatch({"type": "DELETE_ITEM", "doc": new_doc,
                  "selected_path": np, "selected_kind": new_kind})


# ----------------------------
# finding
# ----------------------------

def action_find_key():
    previous_term = g_state["find_term"]

    term = prompt_find_key(previous_term)
    if term is None:
        return  # cancel → no-op

    if term == "" or term == previous_term:
        _do_find_advance()
        return

    # New term → new session
    matches = []
    collect_key_paths(g_state["doc"], [], term, matches)

    if not matches:
        dispatch({"type": "FIND_CLEAR",
                  "status_error": f'Find "{term}": no matches'})
        return

    match_tuples = [tuple(p) for p in matches]
    first_path = match_tuples[0]
    first_kind = _kind_of(g_state["doc"], first_path)

    dispatch({"type": "FIND_START",
              "term": term,
              "matches": match_tuples,
              "index": 0,
              "selected_path": first_path,
              "selected_kind": first_kind,
              "status_error": f'Find "{term}": 1 of {len(match_tuples)}'})

def action_repeat_find_key():
    if not g_state["find_matches"]:
        dispatch({"type": "SET_STATUS", "validity": None, "error": "No active search"})
        return
    _do_find_advance()

def _do_find_advance():
    matches = g_state["find_matches"]
    term = g_state["find_term"]

    if not matches:
        dispatch({"type": "SET_STATUS", "validity": None, "error": "No active search"})
        return

    new_index = g_state["find_index"] + 1
    wrapped = False

    if new_index >= len(matches):
        new_index = 0
        wrapped = True

    path = matches[new_index]
    kind = _kind_of(g_state["doc"], path)

    if wrapped:
        status_error = f'Find "{term}": wrapped (1 of {len(matches)})'
    else:
        status_error = f'Find "{term}": {new_index + 1} of {len(matches)}'

    dispatch({"type": "FIND_ADVANCE",
              "index": new_index,
              "selected_path": path,
              "selected_kind": kind,
              "status_error": status_error})


# ----------------------------
# help
# ----------------------------

def display_help():
    s = "\n".join([
        "JSON Tree Editor lets you explore and safely edit JSON documents using a tree view and a text editor side by side.",
        "",
        "BASIC WORKFLOW",
        "",
        "1. Load JSON into the program:",
        "   • Use File | Open to load a JSON file, or",
        "   • Use File | Create from Clipboard to paste JSON from the clipboard.",
        "",
        "2. Navigate the JSON structure:",
        "   • Click nodes in the tree on the left to select a portion of the JSON.",
        "   • The selected subtree will appear as editable text on the right.",
        "",
        "3. Edit JSON text:",
        "   • Modify the text in the editor pane on the right.",
        "   • You may freely edit, reformat, or replace the JSON subtree.",
        "",
        "4. Commit your changes:",
        "   • Press Ctrl+Enter, or",
        "   • Click the 'Update Tree' button.",
        "   • The tree view will refresh to reflect your changes.",
        "",
        "5. Export JSON:",
        "   • Use 'Copy Tree' to copy the entire document (pretty-printed).",
        "   • Use 'Copy Tree (compressed)' to copy compact JSON.",
        "   • Use 'Copy Node' to copy only the selected subtree.",
        "   • Use File | Save to write the document to disk.",
        "",
        "IMPORTANT WARNING",
        "",
        "Edits made in the text pane are NOT automatically committed.",
        "Your changes are only applied when you explicitly commit them",
        "using Ctrl+Enter or the 'Update Tree' button.",
        "",
        "If you navigate away from a node without committing,",
        "your edits will be lost.",
    ])

    w = tk.Toplevel(widgets["root"])
    w.title("JSON Tree Editor — Help")
    w.geometry("720x520")
    w.configure(background=THEME_DARK["bg"])
    t = tk.Text(w, wrap="word")
    t.insert("1.0", s)
    t.config(
        state="disabled",
        background=THEME_DARK["text_bg"],
        foreground=THEME_DARK["text_fg"],
        insertbackground=THEME_DARK["text_insert"],
        selectbackground=THEME_DARK["text_select_bg"],
        selectforeground=THEME_DARK["text_select_fg"],
    )
    t.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(w, command=t.yview)
    sb.grid(row=0, column=1, sticky="ns")
    t.config(yscrollcommand=sb.set)
    w.grid_rowconfigure(0, weight=1)
    w.grid_columnconfigure(0, weight=1)


# ----------------------------
# ui construction
# ----------------------------

def setup_gui():
    root = widgets["root"]

    root.option_add("*tearOff", 0)

    # main grid: editor row (weight 1), action row (0), status row (0)
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # ---- menubar
    menubar = tk.Menu(root)
    widgets["menubar"] = menubar

    file_menu = tk.Menu(menubar)
    widgets["file_menu"] = file_menu
    file_menu.add_command(label="Open", underline=0, accelerator="Ctrl+O", command=handle_open_file_command)
    file_menu.add_command(label="Open Folder", underline=5, command=open_containing_folder)
    file_menu.add_command(label="Reload", underline=0, accelerator="Ctrl+!", command=handle_reload_file_command)
    file_menu.add_command(label="Save", underline=0, accelerator="Ctrl+S", command=save_file)
    file_menu.add_separator()
    file_menu.add_command(label="Create from Clipboard", accelerator="Ctrl+N", underline=12, command=create_from_clipboard)
    file_menu.add_separator()
    file_menu.add_command(label="New Instance", accelerator="Ctrl+I", underline=0, command=spawn_new_instance)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", accelerator="Ctrl+Q", underline=1, command=exit_application)
    menubar.add_cascade(label="File", underline=0, menu=file_menu)

    edit_menu = tk.Menu(menubar)
    widgets["edit_menu"] = edit_menu
    edit_menu.add_command(label="Search…", accelerator="Ctrl+F", underline=0, command=action_find_key)
    edit_menu.add_command(label="Repeat Search", accelerator="Shift+Ctrl+F", command=action_repeat_find_key)
    edit_menu.add_separator()
    edit_menu.add_command(label="Raise Item", accelerator="Ctrl+Up", command=raise_structural_item)
    edit_menu.add_command(label="Rename Key", accelerator="Ctrl+R", command=rename_structural_key)
    edit_menu.add_command(label="Delete Item", accelerator="Del", command=delete_structural_item)
    edit_menu.add_command(label="Duplicate Item", accelerator="Ctrl+D", command=duplicate_structural_item)
    edit_menu.add_command(label="Insert Item After", accelerator="Ctrl+Right", command=insert_structural_item_after)
    edit_menu.add_command(label="Lower Item", accelerator="Ctrl+Down", command=lower_structural_item)
    menubar.add_cascade(label="Edit", underline=0, menu=edit_menu)

    help_menu = tk.Menu(menubar)
    widgets["help_menu"] = help_menu
    help_menu.add_command(label="Help", underline=0, command=display_help)
    menubar.add_cascade(label="Help", underline=0, menu=help_menu)

    root.config(menu=menubar)

    # ---- editor region: horizontal split (resizable)
    editor = ttk.PanedWindow(root, orient="horizontal")
    editor.grid(row=0, column=0, sticky="nsew")

    # tree pane
    tree_frame = ttk.Frame(editor)
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    tree = ttk.Treeview(tree_frame, show="tree")
    widgets["tree"] = tree
    tree.grid(row=0, column=0, sticky="nsew")

    tree_ys = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree_xs = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree_ys.grid(row=0, column=1, sticky="ns")
    tree_xs.grid(row=1, column=0, sticky="ew")
    tree.configure(yscrollcommand=tree_ys.set, xscrollcommand=tree_xs.set)

    # text pane
    text_frame = ttk.Frame(editor)
    text_frame.grid_rowconfigure(0, weight=1)
    text_frame.grid_columnconfigure(0, weight=1)

    text = tk.Text(text_frame, wrap="word", undo=False)
    widgets["text"] = text
    text.grid(row=0, column=0, sticky="nsew")

    text_ys = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
    text_xs = ttk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
    text_ys.grid(row=0, column=1, sticky="ns")
    text_xs.grid(row=1, column=0, sticky="ew")
    text.configure(yscrollcommand=text_ys.set, xscrollcommand=text_xs.set)

    # add panes to paned window (with initial sizes)
    editor.add(tree_frame, weight=1)
    editor.add(text_frame, weight=4)

    # ---- action row
    actions = ttk.Frame(root)
    actions.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
    actions.grid_columnconfigure(0, weight=0)

    b1 = ttk.Button(actions, text="Copy Tree", command=lambda: copy_entire_document("P"))
    b2 = ttk.Button(actions, text="Copy Tree (compressed)", command=lambda: copy_entire_document("C"))
    b3 = ttk.Button(actions, text="Copy Node", command=copy_selected_subtree)
    b4 = ttk.Button(actions, text="Copy Node (compressed)", command=lambda: copy_selected_subtree("C"))
    b5 = ttk.Button(actions, text="Update Tree", command=apply_text_to_tree)
    b6 = ttk.Button(actions, text="Emit", command=lambda: None)
    b6.state(["disabled"])  # placeholder

    b1.grid(row=0, column=0, padx=4)
    b2.grid(row=0, column=1, padx=4)
    b3.grid(row=0, column=2, padx=4)
    b4.grid(row=0, column=3, padx=4)
    b5.grid(row=0, column=4, padx=16)
    b6.grid(row=0, column=5, padx=4)

    # ---- status bar
    status = ttk.Frame(root)
    status.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))
    status.grid_columnconfigure(0, weight=0)
    status.grid_columnconfigure(1, weight=1)
    status.grid_columnconfigure(2, weight=0)
    status.grid_columnconfigure(3, weight=0)

    widgets["status_validity"] = ttk.Label(status, text="(no document)")
    widgets["status_error"] = ttk.Label(status, text="", anchor="w")
    widgets["status_path"] = ttk.Label(status, text="", anchor="e")
    widgets["status_dirty"] = tk.Label(
        status, text="●", font=("TkDefaultFont", 10),
        bg=THEME_DARK["bg"], fg="#4ec94e"
    )

    widgets["status_validity"].grid(row=0, column=0, sticky="w")
    widgets["status_error"].grid(row=0, column=1, sticky="ew", padx=12)
    widgets["status_path"].grid(row=0, column=2, sticky="e")
    widgets["status_dirty"].grid(row=0, column=3, sticky="e", padx=(4, 0))

    # ---- bindings
    tree.bind("<<TreeviewSelect>>", handle_tree_selection_changed)

    root.bind_all("<Control-o>", lambda e: handle_open_file_command())
    root.bind_all("<Control-!>", lambda e: handle_reload_file_command())
    root.bind_all("<Control-s>", lambda e: save_file())
    root.bind_all("<Control-n>", lambda e: create_from_clipboard())
    root.bind_all("<Control-i>", lambda e: spawn_new_instance())
    root.bind_all("<Control-q>", lambda e: exit_application())
    root.bind_all("<Control-h>", lambda e: display_help())
    root.bind_all("<Control-f>", lambda e: action_find_key())
    root.bind_all("<Control-F>", lambda e: action_repeat_find_key())

    tree.bind("<Control-Up>", on_ctrl_up)
    tree.bind("<Control-Down>", on_ctrl_down)
    tree.bind("<Control-Right>", on_ctrl_right)
    tree.bind("<Control-d>", on_ctrl_d)
    tree.bind("<Delete>", on_delete)
    tree.bind("<Control-r>", on_ctrl_r)

    # commit controls: Ctrl+Enter when focus is in text
    text.bind("<Control-Return>", apply_text_to_tree)
    text.bind("<<Modified>>", handle_text_modified)

    _refresh_menu_enablement(g_state)
    _update_title(g_state)
    apply_dark_mode()


def apply_dark_mode():
    t = widgets["text"]
    root = widgets["root"]

    t.configure(
        background=THEME_DARK["text_bg"],
        foreground=THEME_DARK["text_fg"],
        insertbackground=THEME_DARK["text_insert"],
        selectbackground=THEME_DARK["text_select_bg"],
        selectforeground=THEME_DARK["text_select_fg"],
    )

    style = ttk.Style()
    style.theme_use("clam")

    root.configure(background=THEME_DARK["bg"])

    style.configure(
        "Treeview",
        background=THEME_DARK["tree_bg"],
        foreground=THEME_DARK["tree_fg"],
        fieldbackground=THEME_DARK["tree_bg"],
    )

    style.map(
        "Treeview",
        background=[("selected", THEME_DARK["tree_select_bg"])],
        foreground=[("selected", THEME_DARK["tree_select_fg"])],
    )

    style.configure(
        "TLabel",
        background=THEME_DARK["bg"],
        foreground=THEME_DARK["fg"],
    )

    style.configure(
        "TFrame",
        background=THEME_DARK["bg"],
    )

    style.configure(
        "TPanedwindow",
        background=THEME_DARK["bg"],
    )

    style.configure(
        "TButton",
        background=THEME_DARK["button_bg"],
        foreground=THEME_DARK["button_fg"],
        bordercolor=THEME_DARK["bg"],
        focusthickness=0,
    )

    style.map(
        "TButton",
        background=[("active", THEME_DARK["button_active_bg"])],
        foreground=[("disabled", THEME_DARK["muted"])],
    )

    style.configure(
        "TScrollbar",
        background=THEME_DARK["bg"],
        troughcolor=THEME_DARK["bg"],
        bordercolor=THEME_DARK["bg"],
        lightcolor=THEME_DARK["bg"],
        darkcolor=THEME_DARK["bg"],
        arrowcolor=THEME_DARK["fg"],
    )

    style.map(
        "TScrollbar",
        background=[("active", THEME_DARK["bg"])],
        arrowcolor=[("active", THEME_DARK["fg"])],
    )

    widgets["status_error"].configure(foreground=THEME_DARK["error"])

    menu_bg = THEME_DARK["bg"]
    menu_fg = THEME_DARK["fg"]
    menu_active_bg = THEME_DARK["button_active_bg"]
    menu_active_fg = THEME_DARK["fg"]

    for key in ("menubar", "file_menu", "edit_menu", "help_menu"):
        m = widgets.get(key)
        if m:
            m.configure(
                background=menu_bg,
                foreground=menu_fg,
                activebackground=menu_active_bg,
                activeforeground=menu_active_fg,
            )


def on_ctrl_up(event):
    raise_structural_item()
    return "break"

def on_ctrl_down(event):
    lower_structural_item()
    return "break"

def on_ctrl_right(event):
    insert_structural_item_after()
    return "break"

def on_ctrl_d(event):
    duplicate_structural_item()
    return "break"

def on_delete(event):
    delete_structural_item()
    return "break"

def on_ctrl_r(event):
    rename_structural_key()
    return "break"


# ----------------------------
# main
# ----------------------------

def main():
    global g_state
    root = tk.Tk()
    widgets["root"] = root
    setup_gui()

    # Initialize status widgets from initial g_state
    widgets["status_validity"].configure(text=g_state["status_validity"])
    widgets["status_error"].configure(text=g_state["status_error"])
    _update_status_path(g_state["selected_path"])
    _update_dirty_indicator(g_state["dirty"])

    if len(sys.argv) > 1:
        try:
            open_file(Path(sys.argv[-1]))
        except Exception:
            pass

    root.mainloop()


if __name__ == "__main__":
    main()
