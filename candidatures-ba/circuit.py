"""Contrôles du dossier de candidature et transitions sans effet réseau."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit


R3_CHECKS = ("READ", "TARGET", "FACTS", "FIT", "STYLE", "RENDER", "CHANNEL")
R3_RULES = (
    "B7", "B16", "B17", "B18", "B19", "B20", "B26", "B27", "B28", "B29", "B30",
    "B43", "B50", "B60", "B71", "B72", "B73", "B74", "B75", "B76", "B77", "B78",
    "B79", "B80", "B81",
)
SENT_STATES = {"SUBMITTED", "SUBMISSION_CONFIRMED"}
PHASES = {"recherche", "preparation", "depot", "suivi"}


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str

    @property
    def ok(self):
        return self.status == "PASS"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return digest(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode())


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def origin(url):
    try:
        parts = urlsplit(url)
        if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password:
            port = f":{parts.port}" if parts.port not in (443, None) else ""
            return f"https://{parts.hostname.lower()}{port}"
    except (TypeError, ValueError):
        pass
    return ""


def qualify(offer):
    destination = [normalize(str(offer.get(key) or "")).casefold() for key in ("employer", "client")]
    if not offer.get("scope_proof") or "excluded_destinations" not in offer:
        return Decision("PARK_SCOPE", "Exclusions du mandat à relire")
    excluded = [re.escape(normalize(name).casefold()) for name in offer["excluded_destinations"] if normalize(name)]
    if any(re.search(r"\b" + term + r"\b", name) for name in destination for term in excluded):
        return Decision("PARK_EXCLUDED", "Employeur ou client final exclu")
    if offer.get("excluded_client_signal"):
        return Decision("PARK_CLIENT", "Client final à établir")
    spontaneous = offer.get("type") == "spontanee"
    if spontaneous and not offer.get("recruitment_signal"):
        return Decision("PARK_OPENING", "Une spontanée exige un signal de recrutement précis")
    if not spontaneous and offer.get("open") is False:
        return Decision("PARK_CLOSED", "Fermeture constatée")
    if not spontaneous and (offer.get("open") is not True or not offer.get("opening_proof")):
        return Decision("PARK_OPENING", "Ouverture à établir")
    if offer.get("contract") != "CDI" or offer.get("region") != "IDF":
        return Decision("PARK_SCOPE", "CDI et Île-de-France à établir")
    duties = {normalize(text) for text in offer.get("duties", ()) if normalize(text)}
    if offer.get("project_role") is not True or len(duties) < 2:
        return Decision("PARK_SCOPE", "Deux missions projet requises")
    if any(not x.get("proved") for x in offer.get("indispensable", ())):
        return Decision("PARK_REQUIREMENTS", "Exigence indispensable à établir")
    if not offer.get("reference") or not offer.get("employer") or not origin(offer.get("source", "")):
        return Decision("PARK_SOURCE", "Identité de l'offre incomplète")
    return Decision("PASS", "Offre qualifiée")


def duplicate(offer, rows):
    keys = {offer["reference"], *offer.get("aliases", ())}
    employer = normalize(offer["employer"]).casefold()
    for row in rows:
        same_id = bool(keys & {row.get("reference"), *row.get("aliases", ())})
        if same_id and normalize(row["employer"]).casefold() == employer:
            if row.get("status") in SENT_STATES | {"DISPATCH_PENDING", "UNKNOWN", "SUBMISSION_UNCERTAIN"}:
                return Decision("BLOCK_DUPLICATE", "Candidature ou tentative à réconcilier")
    return Decision("PASS", "Aucun envoi concurrent dans les lignes rapprochées")


def verify_route(offer, route, stage="inspect"):
    source = origin(offer.get("source", ""))
    destination = route.get("destination", "")
    if route.get("channel") == "email":
        valid = bool(re.fullmatch(r"[a-zA-Z0-9.!#$%&'*+/=?^_{}~-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", destination))
        allowed = valid and destination in route.get("verified_addresses", ())
    else:
        target = origin(destination)
        allowed = bool(target and target in route.get("verified_origins", ()))
    if not source or route.get("reference") != offer.get("reference") or route.get("source") != source:
        return Decision("BLOCK_DESTINATION", "Reprendre le lien issu de l'offre exacte")
    if not allowed or not route.get("link_proof"):
        return Decision("BLOCK_DESTINATION", "Destination non prouvée")
    stages = {"inspect": ("read",), "prepare": ("read", "fill"), "dispatch": ("read", "fill", "send")}
    proofs = route.get("capability_proofs", {})
    if not route.get("environment") or not all(proofs.get(action) for action in stages[stage]):
        return Decision("BLOCK_CHANNEL", "Capacité du run courant non établie")
    return Decision("PASS", "Canal et référence contrôlés")


def form_plan(fields, facts, approvals):
    plan, pending = {}, []
    for field in fields:
        key, kind = field["key"], field.get("kind", "fact")
        if kind in {"secret", "mfa", "captcha", "login", "binding"}:
            if field["required"]:
                pending.append((key, "USER_ACTION_REQUIRED"))
            continue
        if kind == "consent":
            if approvals.get(key):
                plan[key] = approvals[key]
            elif field["required"]:
                pending.append((key, "USER_ACTION_REQUIRED"))
            continue
        fact = facts.get(field.get("fact"))
        if fact and fact.get("source") and fact.get("value") not in (None, ""):
            plan[key] = fact["value"]
        elif field["required"]:
            pending.append((key, "UNKNOWN_REQUIRED"))
    return plan, pending


def resume_packet(offer, route, step):
    require(verify_route(offer, route).ok, "Vérifier la destination avant reprise")
    require(step in {"login", "mfa", "captcha", "binding", "consent", "required_field"}, "Étape inconnue")
    return {
        "reference": offer["reference"], "origin": origin(route["destination"]),
        "environment": route["environment"], "step": step, "revalidate": ["account", "reference", "attachments", "attempt"],
    }


def allowed_supplements(documents, destination):
    """Filtre les références et recommandations pour le destinataire exact."""
    result = []
    for doc in documents:
        kind = doc.get("kind")
        common = doc.get("evidence") and destination in doc.get("authorized_destinations", ())
        if kind == "reference" and common and doc.get("person") and doc.get("relationship"):
            result.append(doc)
        if kind == "recommendation" and common and doc.get("issuer") and doc.get("sha256") and doc.get("relevant"):
            result.append(doc)
    return result


def current_context(offer, route, directives, cv_sha):
    require(all(directives.get(key) for key in R3_RULES), "Directives R3 incomplètes")
    require(len(cv_sha) == 64 and all(ch in "0123456789abcdef" for ch in cv_sha), "Empreinte CV invalide")
    return {
        "mandate_sha256": fingerprint({key: directives[key] for key in R3_RULES}),
        "offer_sha256": fingerprint(offer),
        "reference": offer["reference"],
        "cv_sha256": cv_sha,
        "destination": route["destination"],
        "route_sha256": fingerprint({key: route.get(key) for key in (
            "source", "destination", "reference", "channel", "letter",
        )}),
    }


def read_receipt(context, receipt, facts):
    require(receipt.get("context") == context and receipt.get("read_id") and receipt.get("read_at"),
            "Lecture R3 et offre courante à attester")
    require(receipt.get("need") and receipt.get("avoid_claim") and "transfer" in receipt,
            "Appliquer la lecture au besoin et aux limites du parcours")
    fact = facts.get(receipt.get("fact"))
    require(fact and fact.get("source"), "Fait principal à sourcer")


def check_claims(paragraphs, claims, facts):
    joined = normalize(" ".join(paragraphs))
    require(bool(claims), "Lier les affirmations importantes à des faits sourcés")
    for claim in claims:
        fact = facts.get(claim.get("fact"))
        phrase = claim.get("phrase", "")
        require(fact and fact.get("source") and normalize(phrase) and normalize(phrase) in joined,
                "Affirmation ou source manquante")


def verify_letter(context, generated, evidence, observed_hashes):
    require(context == generated.get("context") == evidence.get("context"), "Contexte R3 périmé")
    require(observed_hashes == generated.get("hashes") == evidence.get("hashes"), "Pièce ou rendu modifié")
    for step in R3_CHECKS:
        review = evidence.get("reviews", {}).get(step, {})
        require(review.get("status") == "PASS" and review.get("observation"), f"Revue {step} manquante")
    require(bool(evidence.get("editorial_review_by")), "Relecture de fond non attestée")
    require(bool(evidence.get("weakest_argument") and evidence.get("least_proved_requirement")),
            "Critère indispensable et argument le plus faible à challenger")
    return {"status": "PASS", "context": context, "hashes": dict(observed_hashes)}


def letter_route(channel, lm_receipt):
    if not channel.get("proof") or any(type(channel.get(key)) is not bool for key in ("accepts_pdf", "accepts_text")):
        return Decision("BLOCK_LM_QA", "Observer les champs de motivation du canal exact")
    if not channel["accepts_pdf"] and not channel["accepts_text"]:
        return Decision("NO_LETTER_SUPPORTED", "Le parcours officiel ne prend pas de lettre")
    if not lm_receipt or lm_receipt.get("status") != "PASS":
        return Decision("BLOCK_LM_QA", "Contrôler la lettre et le champ de motivation si présent")
    if channel.get("accepts_text") is True and not lm_receipt.get("hashes", {}).get("portal_text"):
        return Decision("BLOCK_LM_QA", "Le texte du portail exige sa propre preuve")
    return Decision("PASS", "Pièce et texte du canal contrôlés")


def select_cv(canonical, variant, authorization, reference):
    if variant and authorization and variant.get("status") == "PASS":
        if (variant.get("reference") == reference and variant.get("source_sha256") == canonical["sha256"]
                and variant.get("sha256") and variant.get("render_sha256") and variant.get("render_observation")):
            return variant
    return canonical


def preflight(offer, route, rows, request, stage="prepare"):
    if request.get("kind") not in {"new", "retry_non_delivery"}:
        return Decision("BLOCK_AUTHORITY", "Seuls les nouveaux dépôts et reprises prouvées sont autorisés")
    if request.get("reserved_for_candidate") or not request.get("authorized"):
        return Decision("BLOCK_AUTHORITY", "Déposant ou autorisation à établir")
    relevant_rows = rows
    if request["kind"] == "retry_non_delivery":
        non_delivery = request.get("non_delivery_proof") or {}
        prior_id = non_delivery.get("previous_evidence_id")
        if sent_evidence(offer, non_delivery).status != "NON_DELIVERY_PROVED" or not prior_id:
            return Decision("SUBMISSION_UNCERTAIN", "Prouver la non-transmission avant une reprise")
        relevant_rows = [r for r in rows if r.get("evidence_id") != prior_id
                         or r.get("reference") != offer["reference"]]
    for decision in (qualify(offer), verify_route(offer, route, stage), duplicate(offer, relevant_rows)):
        if not decision.ok:
            return decision
    return Decision("PASS", "Dossier, canal et doublons contrôlés")


def dispatch_gate(offer, route, rows, request, letter):
    ready = preflight(offer, route, rows, request, "dispatch")
    if not ready.ok:
        return ready
    if not request.get("same_files_verified") or request.get("pending_fields"):
        return Decision("BLOCK_FIELDS", "Recontrôler les champs ou les pièces exactes")
    verdict = letter_route(route["letter"], letter)
    if verdict.status not in {"PASS", "NO_LETTER_SUPPORTED"}:
        return verdict
    if verdict.status == "PASS":
        context = request.get("context") or {}
        if (not context or context != letter.get("context") or request.get("letter_hashes") != letter.get("hashes")
                or context.get("reference") != offer["reference"] or context.get("destination") != route["destination"]):
            return Decision("BLOCK_LM_QA", "Contexte ou empreintes R3 à recontrôler")
    return Decision("PASS", "Résultat à enregistrer après réservation")


def sent_evidence(offer, event):
    if not event or event.get("reference") != offer["reference"] or not event.get("id") or not event.get("at"):
        return Decision("SUBMISSION_UNCERTAIN", "Preuve externe à réconcilier")
    if event.get("kind") == "received":
        return Decision("SUBMISSION_CONFIRMED", "Réception explicite")
    if event.get("kind") == "sent" and event.get("channel") == "email" and not event.get("attachments_verified"):
        return Decision("SUBMISSION_UNCERTAIN", "Relire les pièces du message envoyé")
    if event.get("kind") in {"sent", "registered_pending_email"}:
        return Decision("SUBMITTED", "Transmission établie")
    if event.get("kind") == "non_delivery":
        return Decision("NON_DELIVERY_PROVED", "Nouvelle tentative à requalifier")
    return Decision("SUBMISSION_UNCERTAIN", "Nature de la preuve insuffisante")


def pending_work(rows, limit=5):
    eligible = [row for row in rows if row.get("open") and row.get("qualified")
                and row.get("next_action") and row.get("status") not in SENT_STATES]
    return sorted(eligible, key=lambda r: (r.get("priority", 9), r.get("deadline") or "9999", r["reference"]))[:limit]


def measure(segments, confirmed_submissions):
    if {s.get("phase") for s in segments} != PHASES:
        return {"status": "UNKNOWN"}
    totals = {"autonome": 0, "manuel": 0, "commun": 0}
    for segment in segments:
        minutes = segment.get("minutes")
        who = segment.get("actor")
        if who not in totals or not isinstance(minutes, (int, float)) or not 0 <= minutes < float("inf"):
            return {"status": "UNKNOWN"}
        totals[who] += minutes
    observed = sum(totals.values())
    attributed = totals["autonome"] + totals["manuel"]
    return {
        "status": "PASS" if observed and attributed else "UNKNOWN", "minutes": totals,
        "hourly_submissions": confirmed_submissions * 60 / observed if observed else "UNKNOWN",
        "autonomous_share": totals["autonome"] / attributed if attributed else "UNKNOWN",
    }


def cohorts(rows, followup_days):
    require(isinstance(followup_days, int) and followup_days > 0, "Choisir un recul positif et commun")
    summary = {}
    for row in rows:
        age = row.get("age_days")
        if row.get("status") not in SENT_STATES or row.get("compliant") is not True:
            continue
        if not isinstance(age, int) or age < followup_days:
            continue
        key = (row.get("offer_type", "UNKNOWN"), row.get("channel", "UNKNOWN"), row.get("cv_kind", "UNKNOWN"))
        group = summary.setdefault(key, {"submissions": 0, "interviews": 0, "unknown_outcomes": 0})
        group["submissions"] += 1
        day = row.get("interview_day")
        if isinstance(day, int) and 0 <= day <= followup_days:
            group["interviews"] += 1
        elif not row.get("followup_checked"):
            group["unknown_outcomes"] += 1
    return summary


def recruiter_event(event, facts=()):
    require(event.get("id") and event.get("at") and event.get("reference"), "Retour à rattacher")
    entry = {key: event[key] for key in ("id", "at", "reference", "kind")}
    entry["next_actor"] = "candidate"
    if event["kind"] == "interview":
        entry["examples"] = [fact for fact in facts if fact.get("source") and fact.get("example")][:3]
    return entry


def qualified_runtime(run, reference):
    needed = ("environment", "runner", "open_proof", "send_proof", "reconciliation_proof")
    return bool(run.get("reference") == reference and all(run.get(key) for key in needed))
