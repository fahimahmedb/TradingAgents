"""Offline quality gate for discovering project-oriented CDI offers in Ile-de-France.

No network, job submission, applicant data or mutation of the canonical tracker.
A search plan is a plan, not proof that an actual search took place.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECTORS = (
    'banques hors employeurs exclus', 'assurance mutuelle', 'fintech paiement',
    'infrastructure de marche', 'editeurs logiciels', 'ESN petite et moyenne',
    'cabinets AMOA', 'industrie SI', 'services publics hors employeurs exclus',
    'transport energie telecom',
)
ROLES = (
    'business analyst fonctionnel', 'analyste fonctionnel', 'charge de projet SI',
    'chef de projet MOA', 'AMOA', 'PMO projet SI', 'product owner fonctionnel',
    'coordinateur projet SI', 'consultant MOA', 'gestionnaire de projets applicatifs',
    'analyste metier', 'chef de projet transformation digitale',
)
SOURCES = ('site employeur ATS', 'APEC', 'France Travail', 'Welcome to the Jungle', 'HelloWork')
EXCLUDED = ('banque de france', 'acpr', 'autorite de controle prudentiel et de resolution')
TRANSMITTED = {'SUBMITTED', 'SUBMISSION_CONFIRMED', 'DISPATCH_PENDING', 'SUBMISSION_UNCERTAIN', 'UNKNOWN'}


def norm(value: str) -> str:
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(x for x in value if not unicodedata.combining(x)).casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def canonical_url(value: str) -> str:
    if not value:
        return ''
    try:
        u = urlsplit(value.strip())
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            return ''
        host = u.hostname.lower().removeprefix('www.')
        filtered = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                    if not k.lower().startswith(('utm_', 'pk_', 'mtm_'))
                    and k.lower() not in {'fbclid', 'gclid', 'ref_source'}]
        filtered.sort()
        return urlunsplit(('https', host, u.path.rstrip('/'), urlencode(filtered), ''))
    except ValueError:
        return ''


def search_plan(budget: int = 30) -> list[dict]:
    """Balanced deterministic coverage, not a guarantee of market exhaustivity."""
    if not isinstance(budget, int) or budget < 1:
        raise ValueError('positive search budget required')
    return [{'sector': SECTORS[i % len(SECTORS)],
             'role': ROLES[(i * 7 + i // len(SECTORS)) % len(ROLES)],
             'source': SOURCES[(i * 3 + i // len(SECTORS)) % len(SOURCES)],
             'filters': 'CDI Île-de-France 0-3 ans projet',
             'id': f'Q{i + 1:03d}'} for i in range(budget)]


def classify_requirements(requirements: list[dict], proven: set[str]) -> tuple[str, list[str], list[str]]:
    """Only explicit hard requirements block. Unknown wording requires source verification."""
    hard, soft, unclear = [], [], []
    for r in requirements:
        label = norm(r.get('name', ''))
        level = r.get('level', 'unknown')
        if not label or level not in {'mandatory', 'preferred', 'unknown'}:
            unclear.append(label or 'unidentified')
        elif label not in proven:
            if level == 'mandatory':
                hard.append(label)
            elif level == 'preferred':
                soft.append(label)
            else:
                unclear.append(label)
    if unclear:
        return 'PARK_REQUIREMENT_WORDING', hard, soft + unclear
    if hard:
        return 'PARK_MANDATORY_GAP', hard, soft
    return 'PASS', [], soft


def _excluded_destination(offer: dict) -> bool:
    for field in ('employer', 'end_client'):
        value = norm(offer.get(field, ''))
        if any(re.search(r'\b' + re.escape(excluded) + r'\b', value) for excluded in EXCLUDED):
            return True
    return False


def qualify(offer: dict, proven: set[str] | None = None) -> dict:
    """Separate observed deal-breakers from unknowns and non-critical preferences."""
    proven = {norm(p) for p in (proven or set())}
    if _excluded_destination(offer):
        return {'status': 'EXCLUDE_EMPLOYER', 'reason': 'employer/end-client exclusion'}
    if offer.get('excluded_client_signal') and not offer.get('end_client'):
        return {'status': 'PARK_CLIENT', 'reason': 'unresolved end client'}
    if offer.get('contract') not in ('CDI',):
        return {'status': 'EXCLUDE_CONTRACT' if offer.get('contract') else 'PARK_CONTRACT', 'reason': 'CDI required'}
    if offer.get('location') not in ('IDF',):
        return {'status': 'EXCLUDE_LOCATION' if offer.get('location') else 'PARK_LOCATION', 'reason': 'IDF required'}
    if not offer.get('reference') or not offer.get('employer') or not canonical_url(offer.get('url', '')):
        return {'status': 'PARK_IDENTITY', 'reason': 'official offer identity missing'}
    official = offer.get('official_evidence', {})
    if not official.get('url') or not official.get('observed_at') or not canonical_url(official.get('url')):
        return {'status': 'PARK_OPENING', 'reason': 'no dated official opening proof'}
    if official.get('status') == 'closed':
        return {'status': 'EXCLUDE_CLOSED', 'reason': 'official listing closed'}
    if official.get('status') != 'open':
        return {'status': 'PARK_OPENING', 'reason': 'opening not confirmed'}
    # An ATS that was open months ago is not evidence of being open today.
    try:
        observed = datetime.fromisoformat(official['observed_at'])
        decision = datetime.fromisoformat(offer['decision_as_of'])
        if observed.tzinfo is None or decision.tzinfo is None:
            raise ValueError('timezone required')
        delta = decision - observed
        if delta < timedelta(0) or delta > timedelta(hours=72):
            return {'status': 'PARK_STALE_OPENING', 'reason': 'official opening proof outside 72h window'}
    except (KeyError, ValueError, TypeError):
        return {'status': 'PARK_OPENING', 'reason': 'invalid or missing dated opening proof'}
    if official.get('reference') and norm(official['reference']) != norm(offer['reference']):
        return {'status': 'PARK_IDENTITY', 'reason': 'official offer reference mismatch'}
    project = offer.get('project_missions', [])
    if offer.get('scope') == 'operational' or offer.get('scope') == 'pure_testing' or offer.get('scope') == 'support':
        return {'status': 'EXCLUDE_ROLE', 'reason': 'out-of-scope primary duties'}
    if len([m for m in project if norm(m)]) < 2 or offer.get('scope') != 'project':
        return {'status': 'PARK_SCOPE', 'reason': 'project scope not substantiated'}
    if offer.get('experience_min_years') is not None and offer['experience_min_years'] > 3:
        if offer.get('experience_level') == 'mandatory':
            return {'status': 'PARK_SENIORITY', 'reason': 'minimum experience beyond profile'}
        if offer.get('experience_level') != 'preferred':
            return {'status': 'PARK_REQUIREMENT_WORDING', 'reason': 'seniority wording unresolved'}
    status, hard, soft = classify_requirements(offer.get('requirements', []), proven)
    if status != 'PASS':
        return {'status': status, 'reason': 'unproved mandatory/unclear requirements', 'hard_gaps': hard, 'other_gaps': soft}
    return {'status': 'PASS', 'reason': 'eligible for further application workflow, not permission to send',
            'preferred_gaps': soft, 'salary_eur': offer.get('salary_eur')}


def duplicate_status(candidate: dict, registry: list[dict]) -> str:
    """Unknown alias is held for review, never silently marked as unique."""
    employer = norm(candidate.get('employer', ''))
    ref = norm(candidate.get('reference', ''))
    url = canonical_url(candidate.get('url', ''))
    for r in registry:
        if norm(r.get('employer', '')) != employer:
            continue
        rr = norm(r.get('reference', ''))
        ru = canonical_url(r.get('url', ''))
        aliases = {norm(a) for a in r.get('aliases', [])}
        same_ref = bool(ref and (ref == rr or ref in aliases))
        same_url = bool(url and ru and url == ru)
        if same_ref or same_url:
            return 'BLOCK_DUPLICATE' if r.get('status') in TRANSMITTED else 'ALREADY_TRACKED'
        if norm(r.get('role', '')) == norm(candidate.get('role', '')) and norm(r.get('location_detail', '')) == norm(candidate.get('location_detail', '')):
            if r.get('role') and r.get('location_detail'):
                return 'PARK_POSSIBLE_ALIAS'
    return 'NEW'


def ranked(offers: list[dict], proven: set[str]) -> list[tuple[dict, dict]]:
    """Eligibility first; high compensation is a tie breaker only, never an exemption."""
    outcomes = [(o, qualify(o, proven)) for o in offers]
    return sorted(outcomes, key=lambda t: (t[1]['status'] != 'PASS',
                                          -(t[0].get('salary_eur') or 0),
                                          norm(t[0].get('employer', ''))))


def benchmark(records: list[dict], gold: dict[str, bool], budgets: dict[str, int], executions: list[dict]) -> dict:
    """Fixed labeled sample benchmark; no inference about global-market recall."""
    if not gold or not budgets or any(n <= 0 for n in budgets.values()):
        raise ValueError('frozen labels and positive budgets required')
    methods = set(budgets)
    if len(methods) < 2 or len(set(budgets.values())) != 1:
        raise ValueError('comparable, equal query budgets required')
    # Evidence that the allocated query effort was actually spent. A list of planned
    # queries or a manually filled budget is not an executed search benchmark.
    completed = {m: set() for m in methods}
    if executions is None:
        raise ValueError('executed query log required')
    for log in executions:
        method = log.get('method')
        key = log.get('query_id')
        if (method not in methods or not key or key in completed[method]
                or not log.get('query_text') or not log.get('observed_at')
                or not canonical_url(log.get('evidence_url', ''))):
            raise ValueError('incomplete or duplicated execution evidence')
        completed[method].add(key)
    if any(len(completed[m]) != budgets[m] for m in methods):
        raise ValueError('planned query budget is not an executed query budget')
    grouped = {m: [] for m in methods}
    for record in records:
        if record['method'] not in methods or record['id'] not in gold:
            raise ValueError('out-of-sample item without frozen label')
        grouped[record['method']].append(record)
    result = {}
    relevant = {key for key, ok in gold.items() if ok}
    for method, items in grouped.items():
        ids = [r['id'] for r in items]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate item in one method must not inflate discovery')
        discovered = set(ids)
        qualified = {r['id'] for r in items if r['decision'] == 'PASS'}
        sectors = Counter(r.get('sector', 'unknown') for r in items)
        result[method] = {
            'query_budget': budgets[method], 'executed_queries': len(completed[method]),
            'observed_unique': len(discovered),
            'true_positives': len(qualified & relevant),
            'false_positives': len(qualified - relevant),
            'observed_false_negatives': len(relevant - qualified),
            'precision_on_sample': round(len(qualified & relevant) / len(qualified), 4) if qualified else None,
            'recall_on_frozen_sample': round(len(qualified & relevant) / len(relevant), 4) if relevant else None,
            'sector_coverage': len(sectors),
            'sector_hhi': round(sum((c / len(items)) ** 2 for c in sectors.values()), 4) if items else None,
        }
    result['scope'] = 'FROZEN_SAMPLE_ONLY_NOT_MARKET_RECALL'
    result['gold_sha256'] = hashlib.sha256(json.dumps(gold, sort_keys=True).encode()).hexdigest()
    return result
