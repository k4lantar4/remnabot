# Plaintext to text.t Migration Checklist

## Overview
This checklist tracks the migration of all plaintext strings to use `text.t()` translation keys in the codebase.

## Rules
1. All plaintext strings must be replaced with `texts.t("KEY")` calls
2. All translation keys must exist in `app/localization/locales/en.json`
3. If a key doesn't exist, add it to the end of `en.json`
4. **Key naming format**: Use **UPPER_SNAKE_CASE** (e.g., `MAIN_MENU_ACTION_PROMPT`, `POLL_NOT_FOUND`)
   - Some keys use dot notation (e.g., `service.notifications.admin.*`) - check existing patterns
   - Group related keys with prefixes (e.g., `ADMIN_*`, `SUBSCRIPTION_*`, `PAYMENT_*`)

## Progress Tracking

### Files Status
- [x] Total files to process: 278
- [x] Files completed: 278 (all files verified and completed)
- [x] Files in progress: 0
- [x] Files remaining: 0

**✅ MIGRATION COMPLETE!** All 278 files have been verified and marked as completed.

### Large Files (>500 lines) - Process in Chunks
Large files should be processed in chunks of 200-300 lines at a time. Update the "Last processed line" marker after each chunk.

## File-by-File Status

*See `docs/plaintext-to-textt-file-tree.md` for detailed file tree with status markers*

## Verification

**CRITICAL: Before marking a file as ✅ Completed, verify it:**

1. Run verification script:
   ```bash
   ./docs/verify_file.sh app/path/to/file.py
   ```

2. Or use quick grep check:
   ```bash
   FILE="app/path/to/file.py"
   grep -nE '(\.answer\(|\.reply\(|\.edit_text\(|\.edit_caption\(|\.send_message\(|callback\.message\.(answer|edit_text|edit_caption))\s*\(["'"'"'][^"'"'"']{3,}' "$FILE" | grep -vE '(texts\.t\(|get_texts|#|logger\.|print\(|f["'"'"']|"""|'"'"'""'"'"')' || echo "✅ Verified"
   ```

3. **DO NOT mark as ✅ until verification passes**

See `docs/plaintext-to-textt-verification.md` for detailed verification methods.

## Notes
- Update status markers (⏳ → 🔄 → ✅) as you progress
- **Always verify before marking as ✅ Completed**
- For large files, update the "Last processed line" after each chunk
- Document any issues or questions encountered
