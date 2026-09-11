"""Language-independent edits of multi-line message templates."""


def strip_template_line(template: str, placeholder: str) -> str:
    """Remove every line of ``template`` that contains ``placeholder``, with its newline.

    Finding the line by its placeholder rather than by its text works in every locale: a
    literal replace of the Russian line never matched the fa/en templates (F-037).
    """
    lines = template.split('\n')
    kept = [line for line in lines if placeholder not in line]
    if len(kept) == len(lines):
        return template
    return '\n'.join(kept)
