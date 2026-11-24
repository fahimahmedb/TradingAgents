import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path


class SimulatedRecruiter:
    def __init__(self):
        self.transmissions = []

    def transmit(self, opportunity, channel, lose_confirmation=False):
        proof = f"simulation-{len(self.transmissions) + 1}"
        self.transmissions.append((opportunity, channel, proof))
        if lose_confirmation:
            raise TimeoutError("The portal accepted the request before the timeout")
        return proof

    def evidence(self, opportunity):
        return [entry for entry in self.transmissions if entry[0] == opportunity]


class DurableIntent:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS intents (opportunity TEXT PRIMARY KEY, owner TEXT)")
            db.commit()

    def reserve(self, opportunity, owner):
        with closing(sqlite3.connect(self.path, timeout=3)) as db:
            result = db.execute(
                "INSERT OR IGNORE INTO intents VALUES (?, ?)", (opportunity, owner),
            )
            db.commit()
            return result.rowcount == 1


def fingerprint(directives, opportunity, destination, pdf):
    relevant_rules = {cell: directives[cell] for cell in ("B16", "B20", "B79", "B81")}
    manifest = {
        "rules": relevant_rules,
        "opportunity": opportunity,
        "destination": destination,
        "document": hashlib.sha256(pdf).hexdigest(),
    }
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def may_dispatch(reserved_for_user, origin, action):
    return not reserved_for_user and origin == "new_qualified_application" and action == "submit"


def letter_exception(pdf_slot, motivation_slot):
    return not pdf_slot and not motivation_slot


class SpecReview(unittest.TestCase):
    opportunity = ("employeur-fictif", "ref-1234")

    def test_01_cellule_relue_ne_protege_pas_de_deux_emissions(self):
        registry = {}
        recruiter = SimulatedRecruiter()
        read_a = registry.get(self.opportunity)
        read_b = registry.get(self.opportunity)
        self.assertIsNone(read_a)
        self.assertIsNone(read_b)
        registry[self.opportunity] = "work"
        worker_a_passed_readback = registry[self.opportunity] == "work"
        registry[self.opportunity] = "hourly"
        worker_b_passed_readback = registry[self.opportunity] == "hourly"
        self.assertTrue(worker_a_passed_readback and worker_b_passed_readback)
        recruiter.transmit(self.opportunity, "ats")
        recruiter.transmit(self.opportunity, "email")
        self.assertEqual(len(recruiter.evidence(self.opportunity)), 2)

    def test_02_reprise_apres_echeance_rejoue_une_emission_acceptee(self):
        recruiter = SimulatedRecruiter()
        with self.assertRaises(TimeoutError):
            recruiter.transmit(self.opportunity, "ats", lose_confirmation=True)
        # B reprend un verrou expiré et ignore le résultat de A.
        recruiter.transmit(self.opportunity, "email")
        self.assertEqual(len(recruiter.evidence(self.opportunity)), 2)

    def test_03_reservation_atomique_puis_panne_sans_double_emission(self):
        recruiter = SimulatedRecruiter()
        overlap = threading.Barrier(2, timeout=4)
        opportunity_key = "|".join(self.opportunity)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "simulation.sqlite"
            intent = DurableIntent(path)

            def worker(channel):
                overlap.wait()
                if not intent.reserve(opportunity_key, channel):
                    return "refused"
                try:
                    recruiter.transmit(self.opportunity, channel, lose_confirmation=True)
                except TimeoutError:
                    return "uncertain"

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, ["ats", "email"]))
            self.assertCountEqual(results, ["uncertain", "refused"])
            reopened = DurableIntent(path)
            self.assertFalse(reopened.reserve(opportunity_key, "restart"))
            self.assertEqual(len(recruiter.evidence(self.opportunity)), 1)

    def test_04_reconcilier_preuve_externe_apres_ecriture_perdue(self):
        recruiter = SimulatedRecruiter()
        registry = {}
        proof = recruiter.transmit(self.opportunity, "ats")
        self.assertNotIn(self.opportunity, registry)
        observed = recruiter.evidence(self.opportunity)
        self.assertEqual(len(observed), 1)
        registry[self.opportunity] = observed[0][2]
        self.assertEqual(registry[self.opportunity], proof)
        self.assertEqual(len(recruiter.transmissions), 1)

    def test_05_reservation_au_candidat_et_reponse_recruteur(self):
        self.assertFalse(may_dispatch(True, "new_qualified_application", "submit"))
        self.assertFalse(may_dispatch(False, "reply_to_recruiter", "submit"))
        self.assertTrue(may_dispatch(False, "new_qualified_application", "submit"))

    def test_06_champ_motivation_empeche_exception_cv_seul(self):
        self.assertFalse(letter_exception(pdf_slot=False, motivation_slot=True))
        self.assertTrue(letter_exception(pdf_slot=False, motivation_slot=False))

    def test_07_recu_lie_au_document_a_la_destination_et_aux_regles(self):
        rules = {"B16": "V6.9", "B20": "CV V3", "B79": "exclusions", "B81": "lecture seule"}
        arguments = ("ref-1234", "https://example.test/apply", b"PDF-v1")
        baseline = fingerprint(rules, *arguments)
        self.assertEqual(baseline, fingerprint({**rules, "B42": "nouveau bilan"}, *arguments))
        self.assertNotEqual(baseline, fingerprint({**rules, "B79": "autre règle"}, *arguments))
        self.assertNotEqual(baseline, fingerprint(rules, arguments[0], arguments[1], b"PDF-v2"))
        self.assertNotEqual(baseline, fingerprint(rules, arguments[0], "https://example.test/new", arguments[2]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
