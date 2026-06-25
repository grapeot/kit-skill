from __future__ import annotations

import re


CSS_STYLES = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f6f8fa; color: #24292f; line-height: 1.6; }
h1 { color: #1f2328; font-size: 24px; border-bottom: 1px solid #d0d7de; padding-bottom: 12px; margin-top: 0; }
h2 { color: #1f2328; font-size: 20px; margin-top: 32px; padding-bottom: 8px; border-bottom: 1px solid #d0d7de; }
h3 { color: #1f2328; font-size: 16px; margin-top: 24px; }
p { margin: 12px 0; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }
th, td { border: 1px solid #d0d7de; padding: 10px 12px; text-align: left; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) { background: #f6f8fa; }
code { background: #f6f8fa; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; }
blockquote { border-left: 4px solid #0969da; margin: 16px 0; padding-left: 16px; color: #57606a; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 24px 0; }
ul, ol { padding-left: 24px; }
li { margin: 4px 0; }
strong { color: #1f2328; }
</style>
"""


def extract_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^# (.+)$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback


def build_preview(markdown: str, limit: int = 100) -> str:
    clean_content = re.sub(r"^#.*$", "", markdown, flags=re.MULTILINE)
    clean_content = re.sub(r"[\*\[\]()|]", "", clean_content)
    clean_content = " ".join(clean_content.split())
    return clean_content[:limit] + "..." if len(clean_content) > limit else clean_content


def md_to_html(markdown: str, title: str | None = None) -> str:
    html = markdown

    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)

    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>\n", html)
    html = re.sub(r"^\d+\. (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    def convert_table(match: re.Match[str]) -> str:
        table_content = match.group(0)
        lines = table_content.strip().split("\n")
        html_table = "<table>\n"
        for index, line in enumerate(lines):
            if re.match(r"^[\|\-\s]+$", line):
                continue
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            tag = "th" if index == 0 else "td"
            row = "".join(f"<{tag}>{cell}</{tag}>" for cell in cells)
            html_table += f"<tr>{row}</tr>\n"
        html_table += "</table>"
        return html_table

    html = re.sub(r"(\|.+\|\n)+", convert_table, html)
    html = re.sub(r"\n\n", "</p><p>", html)
    html = "<p>" + html + "</p>"
    html = re.sub(r"<p>(<h[123]>.*?</h[123]>)</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>(<ul>.*?</ul>)</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>(<table>.*?</table>)</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>(<hr>)</p>", r"\1", html)

    title_html = f"<title>{title}</title>" if title else ""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{title_html}
{CSS_STYLES}
</head>
<body>
{html}
</body>
</html>"""
