"""Entrée B77 qui vérifie les preuves R3 et les fichiers à transmettre."""

from argparse import ArgumentParser

from pieces import gate_letter, load_json, save_json


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("dossier")
    parser.add_argument("cv")
    parser.add_argument("generated")
    parser.add_argument("review")
    parser.add_argument("receipt")
    args = parser.parse_args()
    try:
        result = gate_letter(load_json(args.dossier), args.cv, load_json(args.generated), load_json(args.review))
        save_json(args.receipt, result)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"BLOCK_LM_QA — {exc}\n")
    print("PASS")


if __name__ == "__main__":
    main()
