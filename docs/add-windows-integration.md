# JsonEdit Windows Integration Command

## Overview

This document describes how to add a **manual integration command** to JsonEdit that registers Windows file associations and shell integration.

Instead of modifying system configuration during `pip install`, JsonEdit provides an explicit command:

```

jsonedit install-integration

```

This approach is:

- explicit (no surprise system changes)
- robust across virtual environments and editable installs
- aligned with modern Python packaging practices
- easy to repair or update later

---

## Goal

Allow JsonEdit to:

- Register itself as a handler for `.json` files
- Add a native Windows file type
- Provide an optional right-click "Edit with JsonEdit" menu
- Use the pip-installed command entrypoint

---

## Design Philosophy

Separate responsibilities:

- `pip install` → installs files only
- `jsonedit install-integration` → modifies OS integration

This avoids packaging pitfalls and gives the user control.

---

## Command Structure

Add a CLI command:

```

jsonedit install-integration

```

Optional future commands:

```

jsonedit uninstall-integration
jsonedit repair-integration
jsonedit doctor

````

---

## Implementation Steps

### 1. Determine executable path

Inside the command:

```python
import sys

exe_path = sys.argv[0]
````

This resolves to the pip-generated launcher (`jsonedit.exe`).

---

### 2. Create registry keys (per-user)

Use:

```
HKEY_CURRENT_USER\Software\Classes
```

Avoid system-wide keys to prevent admin requirements.

---

### 3. Create file type class

Key:

```
Software\Classes\jsoneditfile
```

Default value:

```
JSON File (JsonEdit)
```

---

### 4. Register open command

Key:

```
jsoneditfile\shell\open\command
```

Value:

```
"<path_to_jsonedit.exe>" "%1"
```

`%1` represents the selected filename.

---

### 5. Associate extension (optional)

Key:

```
Software\Classes\.json
```

Default value:

```
jsoneditfile
```

NOTE:

* This makes JsonEdit the default editor.
* Alternatively, only add a context-menu entry if you do not want to override existing associations.

---

### 6. Optional: Add context menu entry

Key:

```
jsoneditfile\shell\edit
```

Default:

```
Edit with JsonEdit
```

Command:

```
jsoneditfile\shell\edit\command
```

Same executable string.

---

## Python Registry Example

```python
import winreg

def set_key(path, value):
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
    winreg.SetValue(key, "", winreg.REG_SZ, value)

exe = r"C:\path\to\jsonedit.exe"

set_key(r"Software\Classes\jsoneditfile",
        "JSON File (JsonEdit)")

set_key(r"Software\Classes\jsoneditfile\shell\open\command",
        f'"{exe}" "%1"')
```

---

## Testing

1. Run:

```
jsonedit install-integration
```

2. Restart Windows Explorer (Task Manager → Restart Explorer).

3. Double-click a `.json` file.

---

## Notes for Future Expansion

* Add icon via:

```
jsoneditfile\DefaultIcon
```

* Provide uninstall command.
* Provide detection logic to avoid duplicate registration.
* Consider "Open with JsonEdit" without overriding default association.

---

## Philosophy Reminder

Integration is an explicit user action.

JsonEdit installs cleanly, integrates deliberately.

