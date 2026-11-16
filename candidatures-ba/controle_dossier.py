"""Vérifier un dossier et ses octets avant un dépôt via le canal autorisé."""

import json
from argparse import ArgumentParser
from dataclasses import asdict

from circuit import current_context, dispatch_gate, preflight, require, select_cv
from pieces import file_hash, gate_letter, load_json


def check(dossier, cv, generated=None, review=None):
    canonical = {"sha256": file_hash(dossier["canonical_cv"])}
    require(canonical["sha256"] == dossier["canonical_cv_sha256"], "CV différent du document vérifié dans le mandat")
    selected = select_cv(canonical, dossier.get("variant"), dossier.get("variant_authorized"),
                         dossier["offer"]["reference"])
    request = {**dossier["request"], "same_files_verified": file_hash(cv) == selected["sha256"]}
    receipt = None
    if generated and review:
        receipt = gate_letter(dossier, cv, generated, review)
        request["context"] = current_context(dossier["offer"], dossier["route"], dossier["directives"], file_hash(cv))
        request["letter_hashes"] = receipt["hashes"]
    return dispatch_gate(dossier["offer"], dossier["route"], dossier["registry"], request, receipt)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("dossier")
    parser.add_argument("cv")
    parser.add_argument("--generated")
    parser.add_argument("--review")
    parser.add_argument("--prepare", action="store_true", help="Vérifier l'autorité, le canal et les doublons avant la saisie")
    args = parser.parse_args()
    try:
        if bool(args.generated) != bool(args.review):
            raise ValueError("Le reçu de génération et la revue finale vont ensemble")
        generated, review = (load_json(args.generated), load_json(args.review)) if args.generated else (None, None)
        dossier = load_json(args.dossier)
        if args.prepare:
            result = preflight(dossier["offer"], dossier["route"], dossier["registry"], dossier["request"])
        else:
            result = check(dossier, args.cv, generated, review)
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"BLOCK — {exc}\n")
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
