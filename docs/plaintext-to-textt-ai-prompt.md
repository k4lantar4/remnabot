# AI Assistant Prompt for Plaintext to text.t Migration

Copy and paste this prompt into a new chat with an AI assistant to continue the migration work:

---

**You are helping to migrate a Python codebase from plaintext strings to translation keys using `text.t()`.**

## Context
- **Project**: remnabot (Telegram bot application)
- **Task**: Replace all plaintext strings with `text.t("key")` calls
- **Translation file**: `app/localization/locales/en.json`
- **File Tree**: Read `docs/plaintext-to-textt-file-tree.md` for complete file tree with line counts and status
- **Checklist**: Read `docs/plaintext-to-textt-checklist.md` for progress tracking
- **Verification**: Read `docs/plaintext-to-textt-verification.md` for automated verification methods

## Instructions

1. **Read the file tree** (`docs/plaintext-to-textt-file-tree.md`) to see:
   - Complete file tree with line counts
   - Current status of each file (⏳ Not Started | 🔄 In Progress | ✅ Completed)
   - For large files (>500 lines), check the "Last processed line" marker

2. **Read the checklist** (`docs/plaintext-to-textt-checklist.md`) to understand:
   - Overall progress
   - Which files are done, in progress, or remaining

3. **Find the next file to process**:
   - Look for files marked as "⏳ Not Started"
   - If all files are started, find files marked as "🔄 In Progress"
   - For large files, check the "Last processed line" and continue from there

4. **Process the file**:
   - For files ≤500 lines: Process the entire file
   - For files >500 lines: Process in chunks of 200-300 lines
   - Find all plaintext strings (strings in quotes that are user-facing messages)
   - Replace them with `texts.t("KEY")` where `KEY` is a descriptive translation key in **UPPER_SNAKE_CASE** format
   - Ensure the key follows existing patterns in `en.json` (e.g., `MAIN_MENU_ACTION_PROMPT`, `POLL_NOT_FOUND`, `ADMIN_*`, `SUBSCRIPTION_*`)

5. **Update translation file**:
   - Read `app/localization/locales/en.json`
   - For each new key you create, check if it exists
   - If it doesn't exist, add it to the END of the file with the original plaintext as the value
   - Maintain JSON structure and formatting

6. **Verify completion** (CRITICAL - before marking as ✅):
   - Run verification command to ensure no plaintext remains:
     ```bash
     FILE="app/path/to/file.py"
     grep -nE '(\.answer\(|\.reply\(|\.edit_text\(|\.edit_caption\(|\.send_message\(|callback\.message\.(answer|edit_text|edit_caption))\s*\(["'"'"'][^"'"'"']{3,}' "$FILE" | grep -vE '(texts\.t\(|get_texts|#|logger\.|print\(|f["'"'"']|"""|'"'"'""'"'"')' || echo "✅ Verified: No plaintext found"
     ```
   - Or use the verification script: `./docs/verify_file.sh app/path/to/file.py`
   - **DO NOT mark as ✅ Completed until verification passes**
   - If verification fails, fix remaining plaintext and re-verify

7. **Update documentation**:
   - After processing a file (or chunk for large files):
     - Update status: ⏳ → 🔄 (when starting) → ✅ (when complete - ONLY after verification passes)
     - For large files, update "Last processed line: X" after each chunk
   - Update the checklist file with progress

8. **Continue until complete**:
   - Process files one by one
   - For large files, work in chunks and update progress markers
   - Don't skip files - work systematically through the list

## Important Rules

- **Never use Persian/Farsi** in code, comments, or file names (English only)
- **Always check** if a translation key already exists before creating a new one
- **Maintain consistency** in key naming patterns
- **Test your changes** - ensure the code still works after replacements
- **Update status markers** after each file/chunk completion
- **For large files**: Process in manageable chunks (200-300 lines) and update progress

## Examples

**Example 1: Simple message**
**Before:**
```python
await message.answer("Welcome to the bot!")
```

**After:**
```python
await message.answer(texts.t("WELCOME_MESSAGE"))
```

**In en.json:**
```json
{
  "WELCOME_MESSAGE": "Welcome to the bot!"
}
```

**Example 2: Callback answer**
**Before:**
```python
await callback.answer("✅ Discount activated!", show_alert=True)
```

**After:**
```python
await callback.answer(texts.t("SUBSCRIPTION_PROMO_DISCOUNT_ACTIVATED"), show_alert=True)
```

**In en.json:**
```json
{
  "SUBSCRIPTION_PROMO_DISCOUNT_ACTIVATED": "✅ Discount activated!"
}
```

**Example 3: Error message**
**Before:**
```python
await callback.answer("❌ Invalid payment reference", show_alert=True)
```

**After:**
```python
await callback.answer(texts.t("PAYMENT_INVALID_REFERENCE"), show_alert=True)
```

**In en.json:**
```json
{
  "PAYMENT_INVALID_REFERENCE": "❌ Invalid payment reference"
}
```

**Note on Key Naming:**
- **Primary format**: Use **UPPER_SNAKE_CASE** format (e.g., `MAIN_MENU_ACTION_PROMPT`, `POLL_NOT_FOUND`, `WELCOME_MESSAGE`)
- **Secondary format**: Some keys use dot notation (e.g., `service.notifications.admin.*`) - check existing patterns in `en.json`
- Keys should be descriptive and follow existing patterns in `en.json`
- Group related keys with prefixes (e.g., `ADMIN_*`, `SUBSCRIPTION_*`, `PAYMENT_*`, `POLL_*`)
- **Most keys (97%) use UPPER_SNAKE_CASE** - prefer this format unless you see a clear dot notation pattern for similar functionality

**Note:** The `texts` object is typically obtained via `get_texts(language)` or passed as a parameter in handler functions.

## Current Status
Check the file tree (`docs/plaintext-to-textt-file-tree.md`) to see which files need processing. Start with the first "⏳ Not Started" file you find.

---

**Now begin by reading the documentation and checklist files, then start processing the next file in the queue.**
