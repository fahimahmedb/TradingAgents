"""Entrée B77 qui génère le PDF et le reçu, puis laisse la revue au rédacteur."""

from argparse import ArgumentParser

from pieces import compose_letter, load_json, save_json


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("dossier")
    parser.add_argument("cv")
    parser.add_argument("pdf")
    parser.add_argument("receipt")
    args = parser.parse_args()
    try:
        save_json(args.receipt, compose_letter(load_json(args.dossier), args.cv, args.pdf))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"BLOCK_LM_QA — {exc}\n")
    print("GENERATED_UNQUALIFIED")


if __name__ == "__main__":
    main()
