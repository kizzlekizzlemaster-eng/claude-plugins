# newtlab-report — 뉴트랩 보고서 양식 플러그인

클로드 코드에서 보고서·기획안을 쓰면 회사 양식이 자동으로 적용됩니다.

## 설치 (직원 터미널, 한 번)

```
claude plugin marketplace add kizzlekizzlemaster-eng/claude-plugins
claude plugin install newtlab-report@newtlab
pip3 install markdown
mkdir -p ~/.claude && printf '\n# 뉴트랩 보고서 양식\n보고서·기획안·제안서·현황 정리를 쓰거나 고칠 때는 먼저 /newtlab-report:report 스킬을 부른다.\n' >> ~/.claude/CLAUDE.md
```

넷째 줄은 클로드가 보고서를 쓸 때 이 스킬을 먼저 부르도록 개인 CLAUDE.md에 규칙 한 줄을 넣는 것입니다. 플러그인 스킬은 목록에 이름만 떠서 이 줄이 없으면 `/newtlab-report:report`를 직접 쳐야 합니다.

## 갱신

```
claude plugin update newtlab-report
```

## 들어 있는 것

- `skills/report/SKILL.md` — 쓰는 순서 (종류 고르기 → 템플릿 → 규칙 → 검사 → PDF → 제출)
- `skills/report/rules.md` — 문체·구조 규칙 11개 (정본)
- `skills/report/templates/` — 원페이지 기획 · 보고서 템플릿
- `scripts/md_to_a4_pdf.py` + `report.css` — A4 PDF 변환기와 공통 디자인

정본 저장소는 뉴트랩 ERP `plugins/` 폴더입니다. 여기서 고치고 이 저장소로 내보냅니다.
