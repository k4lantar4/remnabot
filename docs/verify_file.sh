#!/bin/bash

# Plaintext to texts.t() Verification Script
# Usage: ./docs/verify_file.sh <file_path>

FILE="$1"

if [ -z "$FILE" ]; then
    echo "Usage: $0 <file_path>"
    echo "Example: $0 app/handlers/start.py"
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
RESULT1=$(grep -nE '(await\s+)?(message|callback|event)\.(answer|reply|edit_text|edit_caption)\(["'"'"'][^"'"'"']+["'"'"']' "$FILE" 2>/dev/null | \
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
RESULT2=$(grep -nE '\.send_message\([^,)]+,\s*["'"'"'][^"'"'"']{3,}["'"'"']' "$FILE" 2>/dev/null | \
  grep -vE 'texts\.t\(|get_texts|#.*|logger\.|f["'"'"']|"""|'"'"'""'"'"'' || true)

if [ -z "$RESULT2" ]; then
    echo "   ✅ PASS: No plaintext in send_message"
else
    echo "   ❌ FAIL: Found plaintext in send_message:"
    echo "$RESULT2" | sed 's/^/      /'
fi

# Check 3: callback.answer with show_alert
echo ""
echo "3. Checking callback.answer..."
RESULT3=$(grep -nE 'callback\.answer\(["'"'"'][^"'"'"']+["'"'"']' "$FILE" 2>/dev/null | \
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
