import re
from typing import Optional, Union, Tuple
from datetime import datetime
import html

ALLOWED_HTML_TAGS = {
    'b', 'strong',           
    'i', 'em',              
    'u', 'ins',             
    's', 'strike', 'del',  
    'code',                 
    'pre',                
    'a',                  
    'blockquote'
}

SELF_CLOSING_TAGS = {
    'br', 'hr', 'img'
}


def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    pattern = r'^\+?[1-9]\d{1,14}$'
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return re.match(pattern, cleaned_phone) is not None


def validate_telegram_username(username: str) -> bool:
    if not username:
        return False
    username = username.lstrip('@')
    pattern = r'^[a-zA-Z0-9_]{5,32}$'
    return re.match(pattern, username) is not None


def validate_promocode(code: str) -> bool:
    if not code or len(code) < 3 or len(code) > 20:
        return False
    return code.replace('_', '').replace('-', '').isalnum()


def validate_amount(amount_str: str, min_amount: float = 0, max_amount: float = float('inf')) -> Optional[float]:
    try:
        amount = float(amount_str.replace(',', '.'))
        if min_amount <= amount <= max_amount:
            return amount
        return None
    except (ValueError, TypeError):
        return None


def validate_positive_integer(value: Union[str, int], max_value: int = None) -> Optional[int]:
    try:
        num = int(value)
        if num > 0 and (max_value is None or num <= max_value):
            return num
        return None
    except (ValueError, TypeError):
        return None


def validate_date_string(date_str: str, date_format: str = "%Y-%m-%d") -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, date_format)
    except ValueError:
        return None


def validate_url(url: str) -> bool:
    pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    return re.match(pattern, url) is not None


def validate_uuid(uuid_str: str) -> bool:
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return re.match(pattern, uuid_str.lower()) is not None


def validate_traffic_amount(traffic_str: str) -> Optional[int]:
    traffic_str = traffic_str.upper().strip()
    
    if traffic_str in ['UNLIMITED', '∞']:
        return 0
    
    units = {
        'MB': 1,
        'GB': 1024,
        'TB': 1024 * 1024
    }
    
    for unit, multiplier in units.items():
        if traffic_str.endswith(unit):
            try:
                value = float(traffic_str[:-len(unit)].strip())
                return int(value * multiplier)
            except ValueError:
                break
    
    try:
        return int(float(traffic_str))
    except ValueError:
        return None


def validate_subscription_period(days: Union[str, int]) -> Optional[int]:
    try:
        days_int = int(days)
        if 1 <= days_int <= 3650:
            return days_int
        return None
    except (ValueError, TypeError):
        return None


def sanitize_html(text: str) -> str:
    """
    Safely sanitizes HTML text by replacing HTML entities with corresponding tags,
    while preventing XSS vulnerabilities through safe attribute handling.

    Args:
        text (str): Text with HTML entities (e.g., &lt;b&gt; bold &lt;/b&gt;)

    Returns:
        str: Sanitized HTML text (e.g., <b> bold </b>)
    """
    if not text:
        return text

    # For security, we need to process allowed tags by replacing their entities with tags
    # But safely handling attributes to avoid XSS

    allowed_tags = ALLOWED_HTML_TAGS.union(SELF_CLOSING_TAGS)

    # Process all allowed tags
    for tag in allowed_tags:
        # Pattern: capture &lt;tag&gt;, &lt;/tag&gt;, or &lt;tag attributes&gt;
        # Use a more complex pattern to capture attributes up to closing &gt;
        # (?s) - allows . to match newline
        # [^>]*? - lazy capture until >
        pattern = rf'(&lt;)(/?{tag}\b)([^>]*?)(&gt;)'

        def replace_tag(match):
            opening = match.group(1)  # &lt;
            full_tag_content = match.group(2)  # /?tagname
            attrs_part = match.group(3)  # attributes (without >)
            closing = match.group(4)  # &gt;

            # Remove leading space if present
            if attrs_part.startswith(' '):
                attrs_part = attrs_part[1:]

            # Build result
            if attrs_part:
                # Safely process attributes, replacing only safe entities
                # Don't expand &lt; and &gt; inside attributes to avoid XSS
                processed_attrs = attrs_part.replace('&quot;', '"').replace('&#x27;', "'")
                return f'<{full_tag_content} {processed_attrs}>'
            else:
                return f'<{full_tag_content}>'

        text = re.sub(pattern, replace_tag, text, flags=re.IGNORECASE)

    return text


def sanitize_telegram_name(name: Optional[str]) -> Optional[str]:
    """Sanitizes Telegram name for safe insertion into HTML and storage.
    Replaces angle brackets and ampersand with safe visual equivalents.
    """
    if not name:
        return name
    try:
        return (
            name.replace('<', '‹')
                .replace('>', '›')
                .replace('&', '＆')
                .strip()
        )
    except Exception:
        return name


def validate_device_count(count: Union[str, int]) -> Optional[int]:
    try:
        count_int = int(count)
        if 1 <= count_int <= 10:
            return count_int
        return None
    except (ValueError, TypeError):
        return None


def validate_referral_code(code: str) -> bool:
    if not code:
        return False
    
    if code.startswith('ref') and len(code) > 3:
        user_id_part = code[3:]
        return user_id_part.isdigit()
    
    return validate_promocode(code)


def validate_html_tags(text: str) -> Tuple[bool, str]:
    if not text:
        return True, ""
    
    tag_pattern = r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)[^>]*>'
    tags = re.findall(tag_pattern, text)
    
    for is_closing, tag_name in tags:
        tag_name_lower = tag_name.lower()
        
        if tag_name_lower not in ALLOWED_HTML_TAGS and tag_name_lower not in SELF_CLOSING_TAGS:
            return False, f"Unsupported tag: <{tag_name}>"
    
    return validate_html_structure(text)


def validate_html_structure(text: str) -> Tuple[bool, str]:
    tag_pattern = r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)[^>]*?/?>'
    
    matches = re.finditer(tag_pattern, text)
    tag_stack = []
    
    for match in matches:
        full_tag = match.group(0)
        is_closing = bool(match.group(1))
        tag_name = match.group(2).lower()
        
        if full_tag.endswith('/>') or tag_name in SELF_CLOSING_TAGS:
            continue
        
        if not is_closing:
            tag_stack.append(tag_name)
        else:
            if not tag_stack:
                return False, f"Closing tag without opening: </{tag_name}>"
            
            last_tag = tag_stack.pop()
            if last_tag != tag_name:
                return False, f"Improper tag nesting: expected </{last_tag}>, found </{tag_name}>"
    
    if tag_stack:
        return False, f"Unclosed tag: <{tag_stack[-1]}>"
    
    return True, ""


def fix_html_tags(text: str) -> str:
    if not text:
        return text
    
    fixes = [
        (r'<a href=([^"\s>]+)>', r'<a href="\1">'),
        (r'<(br|hr|img[^>]*?)>', r'<\1 />'),
        (r'<<([^>]+)>>', r'<\1>'),
        (r'<\s+([^>]+)\s+>', r'<\1>'),
    ]
    
    result = text
    for pattern, replacement in fixes:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def get_html_help_text() -> str:
    return """<b>Supported HTML tags:</b>

• <code>&lt;b&gt;bold&lt;/b&gt;</code> or <code>&lt;strong&gt;bold&lt;/strong&gt;</code>
• <code>&lt;i&gt;italic&lt;/i&gt;</code> or <code>&lt;em&gt;italic&lt;/em&gt;</code>  
• <code>&lt;u&gt;underlined&lt;/u&gt;</code>
• <code>&lt;s&gt;strikethrough&lt;/s&gt;</code>
• <code>&lt;code&gt;monospace&lt;/code&gt;</code>
• <code>&lt;pre&gt;code block&lt;/pre&gt;</code>
• <code>&lt;a href="url"&gt;link&lt;/a&gt;</code>
• <code>&lt;blockquote&gt;quote&lt;/blockquote&gt;</code>

<b>⚠️ Important rules:</b>
• Every opening tag must be closed
• Tags must be properly nested
• Link attributes must be in quotes

<b>❌ Incorrect:</b>
<code>&lt;b&gt;bold &lt;i&gt;italic&lt;/b&gt;&lt;/i&gt;</code>
<code>&lt;a href=google.com&gt;link&lt;/a&gt;</code>

<b>✅ Correct:</b>
<code>&lt;b&gt;bold &lt;i&gt;italic&lt;/i&gt;&lt;/b&gt;</code>
<code>&lt;a href="https://google.com"&gt;link&lt;/a&gt;</code>"""


def validate_rules_content(text: str) -> Tuple[bool, str, Optional[str]]:
    if not text or not text.strip():
        return False, "Rules text cannot be empty", None
    
    if len(text) > 4000:
        return False, f"Text too long: {len(text)} characters (maximum 4000)", None
    
    is_valid_html, html_error = validate_html_tags(text)
    if not is_valid_html:
        fixed_text = fix_html_tags(text)
        fixed_is_valid, _ = validate_html_tags(fixed_text)
        
        if fixed_is_valid and fixed_text != text:
            return False, html_error, fixed_text
        else:
            return False, html_error, None
    
    return True, "", None
