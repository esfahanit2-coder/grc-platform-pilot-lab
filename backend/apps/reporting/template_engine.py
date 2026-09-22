from io import BytesIO

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

DEFAULT_CSS = """
@page { size: A4; margin: 18mm; }
body { font-family: 'DejaVu Sans', sans-serif; color: #16243a; font-size: 10pt; line-height: 1.7; }
h1,h2,h3 { color: #10243b; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; }
th,td { border: 1px solid #d8e1eb; padding: 6px; vertical-align: top; }
th { background: #eef3f8; }
"""


def render_html(template_text, context):
    env=SandboxedEnvironment(undefined=StrictUndefined,autoescape=True)
    env.filters['yesno']=lambda value: 'Yes' if value else 'No'
    template=env.from_string(template_text)
    return template.render(**(context or {}))


def _report_url_fetcher():
    from weasyprint.urls import URLFetcher
    # WeasyPrint 70's public URL-fetching API. Only self-contained data URLs
    # are permitted; local files, HTTP(S), FTP and redirects are excluded.
    return URLFetcher(allowed_protocols={'data'},allow_redirects=False,fail_on_errors=True)


def safe_report_url_fetcher(url):
    """Fetch a report resource through the data-only WeasyPrint boundary."""
    return _report_url_fetcher().fetch(url)


def render_pdf(template_text, context, css_text=''):
    from weasyprint import CSS, HTML
    html=render_html(template_text,context)
    fetcher=_report_url_fetcher()
    output=BytesIO()
    HTML(string=html,url_fetcher=fetcher).write_pdf(
        output,
        stylesheets=[CSS(string=DEFAULT_CSS+'\n'+(css_text or ''),url_fetcher=fetcher)],
    )
    return output.getvalue(),html
