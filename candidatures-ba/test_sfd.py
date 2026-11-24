import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from circuit import (
    R3_CHECKS, R3_RULES, allowed_supplements, cohorts, current_context, dispatch_gate, duplicate, form_plan,
    letter_route, measure, pending_work, preflight, qualify, qualified_runtime, recruiter_event, resume_packet,
    select_cv, sent_evidence, verify_route,
)
from pieces import compose_letter, file_hash, gate_letter, make_variant, qualify_variant


def sample():
    offer = {
        "employer": "Entreprise fictive", "reference": "TEST-21", "aliases": ["MIROIR-21"],
        "source": "https://emplois.example.test/offre21", "open": True, "opening_proof": "annonce directe",
        "contract": "CDI", "region": "IDF", "project_role": True,
        "scope_proof": "Lecture du mandat d'essai", "excluded_destinations": ["Organisme exclu"],
        "duties": ["Cadrer les besoins", "Suivre les évolutions"],
    }
    route = {
        "source": "https://emplois.example.test", "destination": "https://ats.example.test/apply21",
        "reference": offer["reference"], "verified_origins": ["https://ats.example.test"],
        "link_proof": "Lien employeur", "environment": "Work",
        "capability_proofs": {"read": "formulaire ouvert", "fill": "champ relu", "send": "bouton autorisé"},
        "letter": {"accepts_pdf": False, "accepts_text": False, "proof": "CV seul vérifié"},
    }
    return offer, route


class CircuitTests(unittest.TestCase):
    def setUp(self):
        self.offer, self.route = sample()
        self.request = {"kind": "new", "authorized": True, "same_files_verified": True}

    def test_exclusion_et_qualification(self):
        self.assertTrue(qualify(self.offer).ok)
        self.assertEqual(qualify({**self.offer, "client": "Organisme exclu"}).status, "PARK_EXCLUDED")
        self.assertEqual(qualify({**self.offer, "duties": ["a", " "]}).status, "PARK_SCOPE")
        needed = {**self.offer, "indispensable": [{"name": "Critère non établi"}]}
        self.assertEqual(qualify(needed).status, "PARK_REQUIREMENTS")

    def test_divulgation_autorisee_pour_la_bonne_destination(self):
        documents = [
            {"kind": "reference", "person": "Tuteur fictif", "relationship": "alternance", "evidence": "accord-1"},
            {"kind": "recommendation", "issuer": "Organisme fictif", "evidence": "original-1",
             "sha256": "a" * 64, "relevant": True, "authorized_destinations": ["employeur-1"]},
        ]
        self.assertEqual(allowed_supplements(documents, "employeur-1"), documents[1:])
        self.assertEqual(allowed_supplements(documents, "employeur-2"), [])

    def test_destination_et_capacite(self):
        self.assertTrue(verify_route(self.offer, self.route, "dispatch").ok)
        changed = {**self.route, "destination": "https://autre.example.test/form"}
        self.assertEqual(verify_route(self.offer, changed).status, "BLOCK_DESTINATION")
        readonly = {**self.route, "capability_proofs": {"read": "vu"}}
        self.assertEqual(verify_route(self.offer, readonly, "prepare").status, "BLOCK_CHANNEL")

    def test_spontanee_et_canal_email_autorise(self):
        candidate = {**self.offer, "type": "spontanee", "open": None, "opening_proof": None}
        self.assertEqual(qualify(candidate).status, "PARK_OPENING")
        candidate["recruitment_signal"] = "Besoin publié, daté et ciblé"
        self.assertTrue(qualify(candidate).ok)
        address = "recrutement@" + "emplois.example.test"
        channel = {**self.route, "channel": "email", "destination": address, "verified_addresses": [address]}
        self.assertTrue(verify_route(candidate, channel, "dispatch").ok)
        proof = {"reference": "TEST-21", "id": "sent-1", "at": "date", "kind": "sent", "channel": "email"}
        self.assertEqual(sent_evidence(candidate, proof).status, "SUBMISSION_UNCERTAIN")
        self.assertEqual(sent_evidence(candidate, {**proof, "attachments_verified": True}).status, "SUBMITTED")

    def test_champs_et_reprise_sans_secret(self):
        fields = [
            {"key": "qualification", "fact": "degree", "required": True},
            {"key": "otp", "kind": "mfa", "required": True},
            {"key": "prospection", "kind": "consent", "required": False},
        ]
        self.assertEqual(form_plan(fields, {}, {}), ({}, [
            ("qualification", "UNKNOWN_REQUIRED"), ("otp", "USER_ACTION_REQUIRED"),
        ]))
        handoff = resume_packet(self.offer, self.route, "mfa")
        self.assertEqual(handoff["step"], "mfa")
        self.assertNotIn("?", handoff["origin"])

    def test_parcours_sans_lettre_et_texte_seul(self):
        self.assertEqual(letter_route(self.route["letter"], None).status, "NO_LETTER_SUPPORTED")
        text_channel = {**self.route["letter"], "accepts_text": True}
        self.assertEqual(letter_route(text_channel, {"status": "PASS"}).status, "BLOCK_LM_QA")
        self.assertEqual(letter_route({**text_channel, "accepts_text": None}, {"status": "PASS"}).status, "BLOCK_LM_QA")

    def test_preflight_avant_donnees(self):
        self.assertTrue(preflight(self.offer, self.route, [], self.request).ok)
        pending = {**self.offer, "status": "DISPATCH_PENDING"}
        self.assertEqual(preflight(self.offer, self.route, [pending], self.request).status, "BLOCK_DUPLICATE")
        self.assertEqual(preflight(self.offer, self.route, [], {**self.request, "authorized": False}).status,
                         "BLOCK_AUTHORITY")

    def test_doublon_intercanal_et_confirmation_en_attente(self):
        emailed = {**self.offer, "reference": "MIROIR-21", "status": "SUBMITTED", "channel": "email"}
        self.assertEqual(duplicate(self.offer, [emailed]).status, "BLOCK_DUPLICATE")
        self.assertEqual(duplicate(self.offer, [{**emailed, "status": "DISPATCH_PENDING"}]).status, "BLOCK_DUPLICATE")

    def test_autorisation_recruteur_et_pdf_change(self):
        self.assertTrue(dispatch_gate(self.offer, self.route, [], self.request, None).ok)
        for request in ({"kind": "reply"}, {"reserved_for_candidate": True}):
            self.assertEqual(dispatch_gate(self.offer, self.route, [], {**self.request, **request}, None).status,
                             "BLOCK_AUTHORITY")
        stale = {"status": "PASS", "context": {"reference": "AUTRE"}, "hashes": {"pdf": "a"}}
        letter_route_config = {**self.route, "letter": {"accepts_pdf": True, "accepts_text": False}}
        self.assertEqual(dispatch_gate(self.offer, letter_route_config, [], self.request, stale).status, "BLOCK_LM_QA")

    def test_reconcilier_avant_reprise(self):
        event = {"reference": "TEST-21", "id": "receipt", "at": "observation"}
        self.assertEqual(sent_evidence(self.offer, {**event, "kind": "click"}).status, "SUBMISSION_UNCERTAIN")
        state = sent_evidence(self.offer, {**event, "kind": "registered_pending_email"})
        self.assertEqual(state.status, "SUBMITTED")
        self.assertEqual(sent_evidence(self.offer, {**event, "kind": "received"}).status, "SUBMISSION_CONFIRMED")
        retry = {**self.request, "kind": "retry_non_delivery",
                 "non_delivery_proof": {**event, "kind": "non_delivery", "previous_evidence_id": "initial"}}
        previous = {**self.offer, "status": "SUBMITTED", "evidence_id": "initial"}
        self.assertTrue(dispatch_gate(self.offer, self.route, [previous], retry, None).ok)
        self.assertEqual(dispatch_gate(self.offer, self.route, [previous], {**retry, "non_delivery_proof": {}}, None).status,
                         "SUBMISSION_UNCERTAIN")

    def test_triage_et_durees_inconnues(self):
        ready = {"reference": "2", "priority": 2, "open": True, "qualified": True, "next_action": "vérifier canal"}
        self.assertEqual(pending_work([ready, {**ready, "reference": "1", "open": False}]), [ready])
        self.assertEqual(measure([], 1)["status"], "UNKNOWN")
        segments = [{"phase": stage, "minutes": 5, "actor": "autonome"}
                    for stage in ("recherche", "preparation", "depot", "suivi")]
        self.assertEqual(measure(segments, 1)["hourly_submissions"], 3)

    def test_cohortes_a_recul_egal(self):
        data = {"status": "SUBMITTED", "compliant": True, "age_days": 21,
                "offer_type": "annonce", "channel": "ats", "cv_kind": "v3", "interview_day": 8}
        self.assertEqual(cohorts([data, {**data, "age_days": 5}], 14)[("annonce", "ats", "v3")],
                         {"submissions": 1, "interviews": 1, "unknown_outcomes": 0})

    def test_entretien_et_portee_du_pilote(self):
        event = {"reference": "TEST-21", "id": "avis", "at": "jour 1", "kind": "interview"}
        examples = recruiter_event(event, [{"example": "Cas fictif", "source": "CV"}, {"example": "sans preuve"}])
        self.assertEqual(examples["next_actor"], "candidate")
        self.assertEqual(len(examples["examples"]), 1)
        self.assertFalse(qualified_runtime({"reference": "TEST-21", "environment": "Work"}, "TEST-21"))


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        from reportlab.pdfgen.canvas import Canvas
        self.cv = self.folder / "source.pdf"
        output = Canvas(str(self.cv))
        output.drawString(60, 760, "Candidat fictif")
        output.drawString(60, 730, "DES Quantitative Trading")
        output.drawString(60, 710, "Alternance 2024-2026")
        output.drawString(60, 690, "TOEIC 735")
        output.save()
        self.offer, self.route = sample()
        self.rules = {rule: f"Règle de test {rule}" for rule in R3_RULES}
        self.context = current_context(self.offer, self.route, self.rules, file_hash(self.cv))

    def test_generation_et_gate_lient_les_octets_aux_preuves(self):
        facts = {"need": {"source": "CV", "value": "J’ai analysé des besoins métier."}}
        dossier = {
            "offer": self.offer, "route": self.route, "directives": self.rules, "facts": facts,
            "read": {"context": self.context, "read_id": "contrôle", "read_at": "date", "need": "besoins",
                     "avoid_claim": "budget", "transfer": "", "fact": "need"},
            "letter": {"sender": ["Candidat fictif"], "recipient": ["Recrutement", "Société fictive"],
                       "subject": "Objet — Candidature en AMOA", "salutation": "Madame, Monsieur,",
                       "paragraphs": ["J’ai analysé des besoins métier."],
                       "closing": "Veuillez agréer mes salutations distinguées.", "signature": "Candidat fictif",
                       "claims": [{"fact": "need", "phrase": "analysé des besoins métier"}]},
        }
        generated = compose_letter(dossier, self.cv, self.folder / "test.pdf")
        self.assertEqual(generated["status"], "GENERATED_UNQUALIFIED")
        review = {**generated, "editorial_review_by": "lecteur de test", "weakest_argument": "cas bref",
                  "least_proved_requirement": "aucune exigence dans le cas de test",
                  "reviews": {step: {"status": "PASS", "observation": "preuve de test"} for step in R3_CHECKS}}
        self.assertEqual(gate_letter(dossier, self.cv, generated, review)["status"], "PASS")
        self.assertEqual(current_context(self.offer, self.route, {**self.rules, "B42": "note"}, file_hash(self.cv)),
                         self.context)
        with self.assertRaisesRegex(ValueError, "Revue RENDER"):
            gate_letter(dossier, self.cv, generated, {**review, "reviews": {
                key: value for key, value in review["reviews"].items() if key != "RENDER"}})
        Path(generated["files"]["text"]).write_text("nouvelle version", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "modifié"):
            gate_letter(dossier, self.cv, generated, review)

    def test_cv_reorganise_avec_repli_canonique(self):
        profile = {"header": ["Candidat fictif"], "fixed_facts": ["DES Quantitative Trading", "TOEIC 735"],
                   "blocks": [{"id": "parcours", "label": "Parcours", "lines": ["Alternance 2024-2026"]},
                              {"id": "formation", "label": "Formation", "lines": ["DES Quantitative Trading", "TOEIC 735"]}]}
        reordered = self.folder / "CV.pdf"
        draft = make_variant(self.cv, profile, ["formation", "parcours"], self.offer["reference"], reordered)
        self.assertEqual(draft["status"], "GENERATED_UNQUALIFIED")
        approved = qualify_variant(self.cv, reordered, draft, "Rendu inspecté dans le cas de test")
        canonical = {"sha256": file_hash(self.cv)}
        self.assertEqual(select_cv(canonical, approved, False, self.offer["reference"]), canonical)
        self.assertEqual(select_cv(canonical, approved, True, self.offer["reference"]), approved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
