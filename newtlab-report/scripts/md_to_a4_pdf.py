#!/usr/bin/env python3
"""보고서 MD → A4 인쇄용 PDF 변환기 (뉴트랩 보고서 공통 디자인)

사용법:
    python3 md_to_a4_pdf.py <파일.md> [파일2.md ...]

- 현재 폴더의 pdf/ 에 <파일명>.pdf 를 만든다 (MD 옆에는 아무것도 만들지 않는다)
- 디자인은 옆의 report.css 하나가 정본 — ERP 문서 화면 인쇄도 같은 파일을 쓴다
- 첫 번째 `# 제목` 이 문서 제목. 옵시디언 머리말(---)은 인쇄에서 뺀다
- 머리말 옵션: `인쇄: 조밀표` (표를 촘촘히), `인쇄: 원페이지` (2쪽 넘으면 경고)
- 쪽수를 출력한다. 원페이지 기획은 1쪽인지 여기서 확인한다
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

    body = markdown.markdown(text, extensions=["tables", "sane_lists", "nl2br"])
    body = _inline_images(body, md_path.resolve().parent)
    cls = "report-doc compact" if "조밀표" in flags else "report-doc"
    css = CSS_PATH.read_text(encoding="utf-8")
    html = (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>{css}</style></head>"
        f'<body><div class="{cls}">{body}</div></body></html>'
    )

    # 산출물은 현재 폴더의 pdf/ — 옵시디언 볼트(docs·marketing)에 PDF를 두지 않는다 (2026-08-27 부대표님 지시)
    out_dir = Path.cwd() / "pdf"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / f"{md_path.stem}.html"
    pdf_path = out_dir / f"{md_path.stem}.pdf"
    html_path.write_text(html, encoding="utf-8")

    subprocess.run(
        [_chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", str(html_path)],
        capture_output=True, check=True,
    )
    html_path.unlink(missing_ok=True)
    pages = _page_count(pdf_path)
    size = pdf_path.stat().st_size // 1024
    print(f"  ✓ {md_path.name} → {pdf_path} ({pages}쪽, {size} KB)")
    if "원페이지" in flags and pages > 1:
        print(f"  ⚠ 원페이지 기획인데 {pages}쪽입니다. 근거·표를 줄여서 1쪽으로 맞추세요.")


if __name__ == "__main__":
    targets = [Path(a) for a in sys.argv[1:]]
    if not targets:
        sys.exit("사용법: python3 md_to_a4_pdf.py <파일.md> ...")
    for t in targets:
        convert(t)
