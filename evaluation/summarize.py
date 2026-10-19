"""results.csv를 읽어 조건별 정확도·환각 요약표(summary.md)를 만든다.

사용법:
    python evaluation/summarize.py
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
RESULTS = BASE / "results.csv"
SUMMARY = BASE / "summary.md"

CONDITION_NAMES = {
    "A": "A. 일반 AI",
    "B": "B. 도우미 (지침+MCP)",
    "C": "C. MCP만",
}
HALLUCINATION_NAMES = {
    "H1": "구법·개정안 적용",
    "H2": "수치 오류",
    "H3": "조문 오류",
    "H4": "링크 오류",
    "H5": "근거 없는 단정",
    "H6": "요건 누락",
}


def ratio(yes, total):
    return f"{yes / total * 100:.0f}% ({yes}/{total})" if total else "-"


def yn_ratio(rows, column):
    values = [r[column].strip().upper() for r in rows]
    yes = values.count("Y")
    return ratio(yes, yes + values.count("N"))


WARNING_LABELS = {"부분확인", "미확인"}


def label(r):
    return r.get("confidence_label", "").strip().replace(" ", "") or "없음"


def detectable_error_rate(rows):
    wrong = [r for r in rows if r["score"] in ("0", "1")]
    return ratio(sum(label(r) in WARNING_LABELS for r in wrong), len(wrong))


def dangerous_errors(rows):
    return str(sum(r["score"] == "0" and label(r) == "확인됨" for r in rows))


def over_warning_rate(rows):
    right = [r for r in rows if r["score"] == "2"]
    return ratio(sum(label(r) in WARNING_LABELS for r in right), len(right))


def load_rows():
    with RESULTS.open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("question_id", "").strip()]
    groups = defaultdict(list)
    for r in rows:
        groups[r["condition"].strip().upper()].append(r)
    return groups


def build_summary(groups):
    conditions = sorted(groups)
    names = [CONDITION_NAMES.get(c, c) for c in conditions]
    lines = ["## 조건별 결과", "", "| 지표 | " + " | ".join(names) + " |",
             "|---|" + "---|" * len(conditions)]

    def add_row(label, func):
        lines.append(f"| {label} | " + " | ".join(func(groups[c]) for c in conditions) + " |")

    add_row("문항 수", lambda rs: str(len(rs)))
    add_row("평균 점수 (2점 만점)",
            lambda rs: f"{sum(int(r['score']) for r in rs) / len(rs):.2f}")
    add_row("정답률 (2점)", lambda rs: ratio(sum(r["score"] == "2" for r in rs), len(rs)))
    add_row("오답률 (0점)", lambda rs: ratio(sum(r["score"] == "0" for r in rs), len(rs)))
    add_row("환각 발생 문항",
            lambda rs: ratio(sum(bool(r["hallucination_codes"].strip()) for r in rs), len(rs)))
    add_row("조문 인용 정확도", lambda rs: yn_ratio(rs, "citation_correct"))
    add_row("링크 유효율", lambda rs: yn_ratio(rs, "link_valid"))
    add_row("최근 개정 반영률 (★문항)", lambda rs: yn_ratio(rs, "amendment_reflected"))

    lines += ["", "## 오류 감지 가능성", "",
              "| 지표 | " + " | ".join(names) + " |", "|---|" + "---|" * len(conditions)]
    add_row("감지 가능 오류율 (높을수록 좋음)", detectable_error_rate)
    add_row("위험 오답 수 (확인됨인데 0점)", dangerous_errors)
    add_row("과잉 경고율 (낮을수록 좋음)", over_warning_rate)

    lines += ["", "## 환각 유형별 발생 건수", "",
              "| 유형 | " + " | ".join(names) + " |", "|---|" + "---|" * len(conditions)]
    counts = {}
    for c in conditions:
        counter = Counter()
        for r in groups[c]:
            for code in r["hallucination_codes"].replace(",", ";").split(";"):
                if code.strip():
                    counter[code.strip().upper()] += 1
        counts[c] = counter
    for code, label in HALLUCINATION_NAMES.items():
        lines.append(f"| {code} {label} | " +
                     " | ".join(str(counts[c][code]) for c in conditions) + " |")
    return "\n".join(lines) + "\n"


def main():
    groups = load_rows()
    if not groups:
        print("results.csv에 채점 결과가 없습니다. 결과를 기록한 뒤 다시 실행하세요.")
        return
    summary = build_summary(groups)
    SUMMARY.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"저장 완료: {SUMMARY}")


if __name__ == "__main__":
    main()
