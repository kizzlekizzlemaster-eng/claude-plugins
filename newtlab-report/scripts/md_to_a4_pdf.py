#!/usr/bin/env python3
"""보고서 MD → A4 인쇄용 PDF 변환기 (뉴트랩 보고서 공통 디자인)

사용법:
    python3 md_to_a4_pdf.py <파일.md> [파일2.md ...]

- 현재 폴더의 pdf/ 에 <파일명>.pdf 를 만든다 (MD 옆에는 아무것도 만들지 않는다)
- 디자인은 옆의 report.css 하나가 정본 — ERP 문서 화면 인쇄도 같은 파일을 쓴다
- 첫 번째 `# 제목` 이 문서 제목. 옵시디언 머리말(---)은 인쇄에서 뺀다
- 머리말 옵션: `인쇄: 조밀표` (표를 촘촘히), `인쇄: 원페이지` (2쪽 넘으면 경고)
- 쪽수를 출력한다. 원페이지 기획은 1쪽인지 여기서 확인한다
- 도식: ```mermaid 코드 블록을 그림으로 그린다 (vendor/mermaid.min.js, 네트워크 불필요). 못 그리면 경고를 찍는다
- 준비물: pip3 install markdown, 구글 크롬
"""
import re
import subprocess
import sys
from pathlib import Path

try:
    import markdown
except ImportError:  # pragma: no cover
    sys.exit("markdown 패키지가 없습니다. 터미널에서 `pip3 install markdown` 을 한 번 실행하세요.")

HERE = Path(__file__).resolve().parent
CSS_PATH = HERE / "report.css"
MERMAID_PATH = HERE / "vendor" / "mermaid.min.js"
MERMAID_INIT = (
    "mermaid.initialize({startOnLoad:false,theme:'base',securityLevel:'loose',"
    "fontFamily:'Pretendard, -apple-system, BlinkMacSystemFont, Apple SD Gothic Neo, sans-serif',"
    "flowchart:{htmlLabels:true,curve:'basis',padding:8},"
    "themeVariables:{primaryColor:'#e4ebc9',primaryTextColor:'#1f2a14',primaryBorderColor:'#4e6b2d',"
    "lineColor:'#4e6b2d',secondaryColor:'#f4f6ec',tertiaryColor:'#ffffff',fontSize:'12px',"
    "noteBkgColor:'#fff8d6',noteBorderColor:'#c9b45a'}});"
    # 문법이 틀린 블록은 빼고 그린다. 틀린 수를 body에 적어 두면 변환기가 읽어 경고한다
    "(async()=>{const els=[...document.querySelectorAll('pre.mermaid')];let bad=0;"
    "for(const el of els){let ok=false;try{ok=await mermaid.parse(el.textContent,{suppressErrors:true});}catch(e){ok=false;}"
    "if(!ok){bad++;el.setAttribute('data-bad','1');el.textContent='[도식 문법 오류 — 그리지 못함]\\n'+el.textContent;}}"
    "document.body.setAttribute('data-mermaid-bad',String(bad));"
    "try{await mermaid.run({nodes:els.filter(e=>!e.hasAttribute('data-bad'))});}catch(e){}"
    "document.body.setAttribute('data-mermaid-done','1');})();"
)

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def _chrome() -> str:
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    sys.exit("구글 크롬이 없습니다. 크롬을 설치한 뒤 다시 실행하세요.")


def _inline_images(body: str, base_dir: Path) -> str:
    """MD 안의 로컬 이미지를 base64로 심는다. HTML은 pdf/ 에 쓰이므로 상대경로가 깨지기 때문."""
    import base64
    import mimetypes

    def repl(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        path = (base_dir / src).resolve()
        if not path.is_file():
            print(f"  ⚠ 이미지 없음: {src}")
            return m.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode()
        return f'src="data:{mime};base64,{b64}"'

    return re.sub(r'src="([^"]+)"', repl, body)


def _mermaid_blocks(body: str) -> tuple[str, int]:
    """```mermaid 코드 블록을 mermaid가 그릴 수 있는 <pre class="mermaid">로 바꾼다. 블록 수를 함께 돌려준다."""
    import html as _html

    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f'<pre class="mermaid">{_html.unescape(m.group(1))}</pre>'

    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>', repl, body, flags=re.S)
    # 그림 바로 아래 `*그림 n. …*` 한 줄은 그림과 한 덩어리로 묶어 쪽이 갈리지 않게 한다
    body = re.sub(
        r'(<pre class="mermaid">.*?</pre>)\s*<p>(<em>.*?</em>)</p>',
        r'<figure class="diagram">\1<figcaption>\2</figcaption></figure>', body, flags=re.S,
    )
    return body, count


def _bad_diagrams(chrome: str, html_path: Path) -> int:
    """크롬으로 DOM을 떠서 문법이 틀려 못 그린 도식 수를 읽는다(-1이면 mermaid가 돌지 않았다)."""
    r = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--virtual-time-budget=15000", "--dump-dom", str(html_path)],
        capture_output=True, text=True,
    )
    m = re.search(r'data-mermaid-bad="(\d+)"', r.stdout)
    return int(m.group(1)) if m else -1


def _page_count(pdf: Path) -> int:
    """크롬이 만든 PDF는 페이지 객체가 평문이라 정규식으로 센다 (외부 패키지 불필요)."""
    data = pdf.read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def _front_matter_flags(text: str) -> tuple[str, set[str]]:
    """머리말을 떼고, `인쇄:` 옵션 집합을 돌려준다."""
    fm = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    flags: set[str] = set()
    if fm:
        for m in re.finditer(r"^인쇄:\s*(.+)$", fm.group(1), re.M):
            flags.update(p.strip() for p in re.split(r"[,·\s]+", m.group(1)) if p.strip())
        text = text[fm.end():]
    return text, flags


def convert(md_path: Path) -> None:
    text, flags = _front_matter_flags(md_path.read_text(encoding="utf-8"))
    m = re.search(r"^#\s+(.+)$", text, re.M)
    title = m.group(1).strip() if m else md_path.stem

    body = markdown.markdown(text, extensions=["tables", "sane_lists", "nl2br", "fenced_code"])
    body = _inline_images(body, md_path.resolve().parent)
    body, diagrams = _mermaid_blocks(body)
    script = ""
    if diagrams:
        if not MERMAID_PATH.is_file():
            print(f"  ⚠ 도식 {diagrams}개가 있는데 {MERMAID_PATH.name} 이 없어 그리지 못합니다.")
        else:
            script = f"<script>{MERMAID_PATH.read_text(encoding='utf-8')}</script><script>{MERMAID_INIT}</script>"
    cls = "report-doc compact" if "조밀표" in flags else "report-doc"
    css = CSS_PATH.read_text(encoding="utf-8")
    html = (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>{css}</style></head>"
        f'<body><div class="{cls}">{body}</div>{script}</body></html>'
    )

    # 산출물은 현재 폴더의 pdf/ — 옵시디언 볼트(docs·marketing)에 PDF를 두지 않는다 (2026-08-27 부대표님 지시)
    out_dir = Path.cwd() / "pdf"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / f"{md_path.stem}.html"
    pdf_path = out_dir / f"{md_path.stem}.pdf"
    html_path.write_text(html, encoding="utf-8")

    chrome = _chrome()
    if diagrams and script:
        bad = _bad_diagrams(chrome, html_path)
        if bad > 0:
            print(f"  ⚠ 도식 {diagrams}개 중 {bad}개가 문법이 틀려 그리지 못했습니다. PDF에 '[도식 문법 오류]'로 표시됩니다 — https://mermaid.live 에서 고치세요.")
        elif bad < 0:
            print("  ⚠ 도식을 그리는 mermaid가 돌지 않았습니다. 크롬 출력을 확인하세요.")
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
           f"--print-to-pdf={pdf_path}", str(html_path)]
    for attempt in range(3):
        pdf_path.unlink(missing_ok=True)
        r = subprocess.run(cmd, capture_output=True)
        if pdf_path.is_file() and pdf_path.stat().st_size > 0:
            break  # 크롬이 PDF를 쓰고도 종료 코드 2를 낼 때가 있어 파일 유무로 판정한다
        if attempt == 2:
            sys.exit(f"크롬이 PDF를 만들지 못했습니다 (종료 코드 {r.returncode}). 크롬을 닫고 다시 실행해 보세요.")
    html_path.unlink(missing_ok=True)
    pages = _page_count(pdf_path)
    size = pdf_path.stat().st_size // 1024
    extra = f", 도식 {diagrams}개" if diagrams else ""
    print(f"  ✓ {md_path.name} → {pdf_path} ({pages}쪽, {size} KB{extra})")
    if "원페이지" in flags and pages > 1:
        print(f"  ⚠ 원페이지 기획인데 {pages}쪽입니다. 근거·표를 줄여서 1쪽으로 맞추세요.")


if __name__ == "__main__":
    targets = [Path(a) for a in sys.argv[1:]]
    if not targets:
        sys.exit("사용법: python3 md_to_a4_pdf.py <파일.md> ...")
    for t in targets:
        convert(t)
