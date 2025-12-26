# Plaintext Verification Guide

This document describes how to verify that a file has been completely migrated from plaintext to `texts.t()` calls.

## Automated Verification Commands

### Method 1: Comprehensive Check (Recommended)

Run this command to check for remaining plaintext strings in user-facing contexts:

```bash
# Check a specific file
FILE="app/path/to/file.py"
grep -nE '(\.answer\(|\.reply\(|\.edit_text\(|\.edit_caption\(|\.send_message\(|\.message\.answer\(|callback\.message\.(answer|edit_text|edit_caption))\s*\(["'"'"'][^"'"'"']{3,}' "$FILE" | grep -vE '(texts\.t\(|get_texts|#|logger\.|print\(|f["'"'"']|"""|'"'"'""'"'"')' || echo "✅ No plaintext found in user-facing methods"
```

### Method 2: Pattern-Based Check

Check for common patterns that indicate plaintext:

```bash
FILE="app/path/to/file.py"

# Check for answer/reply/edit methods with string literals
grep -nE '(await\s+)?(message|callback|event)\.(answer|reply|edit_text|edit_caption)\(["'"'"'][^"'"'"']+["'"'"']' "$FILE" | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || \
  echo "✅ No plaintext in answer/reply/edit methods"

# Check for send_message with string literals
grep -nE '\.send_message\([^,)]+,\s*["'"'"'][^"'"'"']{3,}["'"'"']' "$FILE" | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || \
  echo "✅ No plaintext in send_message"
```

### Method 3: Simple String Literal Check (Less Reliable)

This checks for any string literals that might be user-facing (may have false positives):

```bash
FILE="app/path/to/file.py"

# Find string literals longer than 3 characters (likely user-facing)
grep -nE '["'"'"'][^"'"'"']{4,}["'"'"']' "$FILE" | \
  grep -vE '(texts\.t\(|get_texts|import|from|#|logger\.|print\(|f["'"'"']|"""|'"'"'""'"'"'|__|TODO|FIXME|NOTE|HACK)' | \
  grep -E '(answer|reply|edit|send|message|callback|text|caption)' || \
  echo "⚠️ Check manually - this method may have false positives"
```

### Method 4: Complete Verification Script

Save this as `verify_file.sh`:

```bash
#!/bin/bash

FILE="$1"

if [ -z "$FILE" ]; then
    echo "Usage: $0 <file_path>"
    exit 1
fi

if [ ! -f "$FILE" ]; then
    echo "Error: File not found: $FILE"
    exit 1
fi

echo "🔍 Verifying file: $FILE"
echo ""

# Check 1: answer/reply/edit methods
echo "1. Checking answer/reply/edit methods..."
RESULT1=$(grep -nE '(await\s+)?(message|callback|event)\.(answer|reply|edit_text|edit_caption)\(["'"'"'][^"'"'"']+["'"'"']' "$FILE" | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || true)

if [ -z "$RESULT1" ]; then
    echo "   ✅ PASS: No plaintext in answer/reply/edit methods"
else
    echo "   ❌ FAIL: Found plaintext in answer/reply/edit methods:"
    echo "$RESULT1" | sed 's/^/      /'
fi

# Check 2: send_message
echo ""
echo "2. Checking send_message..."
RESULT2=$(grep -nE '\.send_message\([^,)]+,\s*["'"'"'][^"'"'"']{3,}["'"'"']' "$FILE" | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || true)

if [ -z "$RESULT2" ]; then
    echo "   ✅ PASS: No plaintext in send_message"
else
    echo "   ❌ FAIL: Found plaintext in send_message:"
    echo "$RESULT2" | sed 's/^/      /'
fi

# Check 3: callback.answer with show_alert
echo ""
echo "3. Checking callback.answer with show_alert..."
RESULT3=$(grep -nE 'callback\.answer\(["'"'"'][^"'"'"']+["'"'"']' "$FILE" | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || true)

if [ -z "$RESULT3" ]; then
    echo "   ✅ PASS: No plaintext in callback.answer"
else
    echo "   ❌ FAIL: Found plaintext in callback.answer:"
    echo "$RESULT3" | sed 's/^/      /'
fi

# Summary
echo ""
if [ -z "$RESULT1" ] && [ -z "$RESULT2" ] && [ -z "$RESULT3" ]; then
    echo "✅ VERIFICATION PASSED: File appears to be fully migrated"
    exit 0
else
    echo "❌ VERIFICATION FAILED: File still contains plaintext strings"
    echo ""
    echo "Please review the results above and migrate remaining plaintext to texts.t()"
    exit 1
fi
```

Make it executable and run:
```bash
chmod +x verify_file.sh
./verify_file.sh app/path/to/file.py
```

## Manual Verification Checklist

Even after automated checks, manually verify:

- [ ] All `message.answer("...")` calls use `texts.t()`
- [ ] All `callback.answer("...")` calls use `texts.t()`
- [ ] All `callback.message.edit_text("...")` calls use `texts.t()`
- [ ] All `callback.message.edit_caption("...")` calls use `texts.t()`
- [ ] All `bot.send_message(..., "...")` calls use `texts.t()`
- [ ] All f-strings that contain user-facing text use `texts.t()` for the text parts
- [ ] All error messages shown to users use `texts.t()`
- [ ] All success/notification messages use `texts.t()`

## False Positives to Ignore

These patterns are OK and should be ignored:
- `texts.t("KEY")` - Already using translation
- `get_texts(...)` - Getting texts object
- Comments: `# ...`
- Logging: `logger.info("...")`, `logger.error("...")`
- Print statements: `print("...")`
- Docstrings: `"""..."""`
- F-strings for technical data: `f"Error code: {code}"`
- Technical strings: `__name__`, `__file__`, etc.

## Integration with Workflow

Before marking a file as ✅ Completed:

1. Run the verification script/command
2. If verification passes, mark file as ✅ Completed
3. If verification fails, fix remaining issues and re-verify
4. Update the file tree status marker

## Example Workflow

```bash
# 1. Process the file (migrate plaintext to texts.t())
# ... (manual or AI-assisted migration)

# 2. Verify the file
./verify_file.sh app/handlers/start.py

# 3. If verification passes, update status in file-tree.md
# Change: "start.py (1903 lines) - Status: 🔄 In Progress"
# To:     "start.py (1903 lines) - Status: ✅ Completed"
```
