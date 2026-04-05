from pathlib import Path

from recalllayer.benchmark.proof_pack import build_proof_rows, render_proof_markdown


def main() -> None:
    rows = build_proof_rows()
    output_path = Path("reports") / "proof_pack.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_proof_markdown(rows) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
