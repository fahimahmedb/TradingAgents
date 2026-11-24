import unittest
from discovery_quality import (
    ROLES, SECTORS, SOURCES, benchmark, canonical_url, classify_requirements,
    duplicate_status, qualify, ranked, search_plan,
)


def offer(**overrides):
    base = dict(employer='Exemple SA', reference='JOB-01', url='https://jobs.example.org/post?utm_source=site&job=1',
        official_evidence={'url': 'https://jobs.example.org/post?job=1', 'status': 'open', 'observed_at': '2026-11-24T08:00+01:00'},
        decision_as_of='2026-11-24T10:00:00+01:00',
        contract='CDI', location='IDF', scope='project', project_missions=['recueillir les besoins', 'piloter évolutions'],
        requirements=[], experience_min_years=2, experience_level='mandatory', salary_eur=48000,
        role='analyste fonctionnel', location_detail='Paris')
    base.update(overrides)
    return base


class SearchPlanTests(unittest.TestCase):
    def test_01_budget_exact(self):
        self.assertEqual(len(search_plan(30)), 30)

    def test_02_sector_coverage(self):
        self.assertEqual(set(x['sector'] for x in search_plan(30)), set(SECTORS))

    def test_03_roles_not_ba_only(self):
        self.assertGreaterEqual(len(set(x['role'] for x in search_plan(30))), 8)
        self.assertIn('AMOA', ROLES)

    def test_04_source_diversity(self):
        self.assertEqual(set(x['source'] for x in search_plan(30)), set(SOURCES))

    def test_05_determinism(self):
        self.assertEqual(search_plan(15), search_plan(15))

    def test_06_budget_invalid(self):
        with self.assertRaises(ValueError): search_plan(0)


class QualifyTests(unittest.TestCase):
    def test_07_open_project_offer(self): self.assertEqual(qualify(offer())['status'], 'PASS')
    def test_08_no_salary_not_blocking(self): self.assertEqual(qualify(offer(salary_eur=None))['status'], 'PASS')
    def test_09_bdf_end_client_excluded(self): self.assertEqual(qualify(offer(end_client='Banque de France'))['status'], 'EXCLUDE_EMPLOYER')
    def test_10_acpr_employer_excluded(self): self.assertEqual(qualify(offer(employer='ACPR'))['status'], 'EXCLUDE_EMPLOYER')
    def test_11_history_bdf_not_exclusion(self): self.assertEqual(qualify(offer(candidate_history='Banque de France'))['status'], 'PASS')
    def test_11b_embedded_end_client_bdf_excluded(self): self.assertEqual(qualify(offer(end_client='Direction projets — Banque de France'))['status'], 'EXCLUDE_EMPLOYER')
    def test_12_unknown_end_client_parks(self): self.assertEqual(qualify(offer(excluded_client_signal=True))['status'], 'PARK_CLIENT')
    def test_13_closed_official_excluded(self):
        e={'url':'https://example.org/job','status':'closed','observed_at':'date'}
        self.assertEqual(qualify(offer(official_evidence=e))['status'], 'EXCLUDE_CLOSED')
    def test_14_aggregator_not_opening_proof(self): self.assertEqual(qualify(offer(official_evidence={}))['status'], 'PARK_OPENING')
    def test_15_unknown_opening_parks(self):
        e={'url':'https://example.org/job','status':'unknown','observed_at':'date'}
        self.assertEqual(qualify(offer(official_evidence=e))['status'], 'PARK_OPENING')
    def test_16_no_operational_middle_office(self): self.assertEqual(qualify(offer(scope='operational'))['status'], 'EXCLUDE_ROLE')
    def test_17_pure_testing_out(self): self.assertEqual(qualify(offer(scope='pure_testing'))['status'], 'EXCLUDE_ROLE')
    def test_18_support_out(self): self.assertEqual(qualify(offer(scope='support'))['status'], 'EXCLUDE_ROLE')
    def test_19_project_duties_missing_parks(self): self.assertEqual(qualify(offer(project_missions=['tests']))['status'], 'PARK_SCOPE')
    def test_20_experience_over_three_mandatory_parks(self): self.assertEqual(qualify(offer(experience_min_years=5))['status'], 'PARK_SENIORITY')
    def test_21_experience_over_three_preferred_is_not_exclusion(self): self.assertEqual(qualify(offer(experience_min_years=5, experience_level='preferred'))['status'], 'PASS')
    def test_22_experience_ambiguous_parks(self): self.assertEqual(qualify(offer(experience_min_years=5, experience_level='unknown'))['status'], 'PARK_REQUIREMENT_WORDING')
    def test_23_required_master_cannot_infer_from_des(self):
        e=offer(requirements=[{'name':'master degree','level':'mandatory'}]); self.assertEqual(qualify(e, {'DES Quantitative Trading'})['status'], 'PARK_MANDATORY_GAP')
    def test_24_required_english_fluent_not_infer_from_b1(self):
        e=offer(requirements=[{'name':'english fluent','level':'mandatory'}]); self.assertEqual(qualify(e, {'english B1 TOEIC 735'})['status'], 'PARK_MANDATORY_GAP')
    def test_25_preferred_english_not_eliminatory(self):
        e=offer(requirements=[{'name':'english fluent','level':'preferred'}]); self.assertEqual(qualify(e, {'english B1 TOEIC 735'})['status'], 'PASS')
    def test_26_specialized_experience_not_infer_from_general_alternance(self):
        e=offer(requirements=[{'name':'3 years payments acquiring','level':'mandatory'}]); self.assertEqual(qualify(e, {'3 years banking apprenticeship'})['status'], 'PARK_MANDATORY_GAP')
    def test_27_unknown_requirement_wording(self):
        e=offer(requirements=[{'name':'bachelor or master','level':'unknown'}]); self.assertEqual(qualify(e)['status'], 'PARK_REQUIREMENT_WORDING')
    def test_28_cdi_and_idf(self):
        self.assertEqual(qualify(offer(contract='CDD'))['status'], 'EXCLUDE_CONTRACT')
        self.assertEqual(qualify(offer(location='Lyon'))['status'], 'EXCLUDE_LOCATION')
    def test_29_requirements_classification(self):
        r=[{'name':'SQL','level':'preferred'},{'name':'master','level':'mandatory'}]
        self.assertEqual(classify_requirements(r, set())[0], 'PARK_MANDATORY_GAP')
    def test_30_invalid_url_blocks(self): self.assertEqual(qualify(offer(url='http://example.com'))['status'], 'PARK_IDENTITY')

    def test_30b_stale_official_status_not_live(self):
        e={'url':'https://example.org/job','status':'open','observed_at':'2026-11-10T10:00:00+01:00'}
        self.assertEqual(qualify(offer(official_evidence=e))['status'], 'PARK_STALE_OPENING')
    def test_30c_future_observation_rejected(self):
        e={'url':'https://example.org/job','status':'open','observed_at':'2026-11-25T10:00:00+01:00'}
        self.assertEqual(qualify(offer(official_evidence=e))['status'], 'PARK_STALE_OPENING')
    def test_30d_mismatched_ats_reference_rejected(self):
        e={'url':'https://example.org/job','status':'open','observed_at':'2026-11-24T09:00:00+01:00','reference':'JOB-OTHER'}
        self.assertEqual(qualify(offer(official_evidence=e))['status'], 'PARK_IDENTITY')
    def test_30e_missing_as_of_rejected(self):
        e=offer(); e.pop('decision_as_of')
        self.assertEqual(qualify(e)['status'], 'PARK_OPENING')


class DedupRankingTests(unittest.TestCase):
    def test_31_strip_tracking_keep_job_id(self):
        self.assertEqual(canonical_url('https://www.EXAMPLE.org/post?utm_source=X&job=2#anchor'), 'https://example.org/post?job=2')
    def test_32_same_employer_reference_alternate_channel(self):
        row={'employer':'Exemple SA','reference':'JOB-01','status':'SUBMITTED'}
        self.assertEqual(duplicate_status(offer(),[row]),'BLOCK_DUPLICATE')
    def test_33_alias_requires_review(self):
        row={'employer':'Exemple SA','reference':'ANOTHER','role':'analyste fonctionnel','location_detail':'Paris','status':'NEW'}
        self.assertEqual(duplicate_status(offer(),[row]),'PARK_POSSIBLE_ALIAS')
    def test_34_not_mark_unrelated_employer_duplicate(self):
        row={'employer':'Autre SA','reference':'JOB-01','status':'SUBMITTED'}
        self.assertEqual(duplicate_status(offer(),[row]),'NEW')
    def test_35_pending_prevents_resend(self):
        row={'employer':'Exemple SA','reference':'JOB-01','status':'SUBMISSION_UNCERTAIN'}
        self.assertEqual(duplicate_status(offer(),[row]),'BLOCK_DUPLICATE')
    def test_36_same_ref_untreated_is_tracked(self):
        row={'employer':'Exemple SA','reference':'JOB-01','status':'PARK_QUALIFICATION'}
        self.assertEqual(duplicate_status(offer(),[row]),'ALREADY_TRACKED')
    def test_37_salary_only_after_eligibility(self):
        senior=offer(reference='JOB-2',salary_eur=70000,experience_min_years=8)
        junior=offer(reference='JOB-3',salary_eur=47000)
        self.assertEqual(ranked([senior,junior],set())[0][0]['reference'],'JOB-3')
    def test_38_no_salary_offer_kept(self):
        self.assertEqual(len(ranked([offer(salary_eur=None)],set())),1)


def executed(budgets):
    return [{'method': method, 'query_id': f'{method}-{i}', 'query_text': f'query {i}',
             'observed_at': '2026-11-24T12:00:00+01:00',
             'evidence_url': f'https://jobs.example.org/result/{method}/{i}'}
            for method, size in budgets.items() for i in range(size)]


class BenchmarkTests(unittest.TestCase):
    def test_39_equal_budget_and_metrics(self):
        gold={'a':True,'b':True,'c':False}
        records=[{'method':'old','id':'a','decision':'PASS','sector':'banque'},
                 {'method':'old','id':'c','decision':'PASS','sector':'banque'},
                 {'method':'new','id':'a','decision':'PASS','sector':'banque'},
                 {'method':'new','id':'b','decision':'PASS','sector':'assurance'}]
        b=benchmark(records,gold,{'old':10,'new':10},executed({'old':10,'new':10}))
        self.assertEqual(b['old']['false_positives'],1)
        self.assertEqual(b['new']['observed_false_negatives'],0)
        self.assertEqual(b['scope'],'FROZEN_SAMPLE_ONLY_NOT_MARKET_RECALL')
        self.assertLess(b['new']['sector_hhi'], b['old']['sector_hhi'])
    def test_40_unequal_budget_rejected(self):
        with self.assertRaises(ValueError): benchmark([],{'a':True},{'old':10,'new':12},executed({'old':10,'new':12}))
    def test_41_unlabeled_item_rejected(self):
        with self.assertRaises(ValueError): benchmark([{'method':'old','id':'x','decision':'PASS'}],{'a':True},{'old':1,'new':1},executed({'old':1,'new':1}))
    def test_42_repeat_item_must_not_inflate(self):
        r=[{'method':'old','id':'a','decision':'PASS'}]*2
        with self.assertRaises(ValueError): benchmark(r,{'a':True},{'old':1,'new':1},executed({'old':1,'new':1}))
    def test_43_zero_denominator_explicit(self):
        b=benchmark([],{'a':False},{'old':1,'new':1},executed({'old':1,'new':1}))
        self.assertIsNone(b['old']['precision_on_sample'])
        self.assertIsNone(b['new']['recall_on_frozen_sample'])
    def test_44_frozen_reference_identity_deterministic(self):
        self.assertEqual(benchmark([],{'a':True},{'old':1,'new':1},executed({'old':1,'new':1}))['gold_sha256'],benchmark([],{'a':True},{'old':1,'new':1},executed({'old':1,'new':1}))['gold_sha256'])

    def test_45_missing_executions_rejected(self):
        with self.assertRaises(ValueError): benchmark([],{'a':True},{'old':1,'new':1},[])

    def test_46_mismatched_executed_query_counts_rejected(self):
        with self.assertRaises(ValueError): benchmark([],{'a':True},{'old':2,'new':2},executed({'old':1,'new':2}))

    def test_47_double_counted_search_rejected(self):
        logs = executed({'old':1,'new':1})
        with self.assertRaises(ValueError): benchmark([],{'a':True},{'old':1,'new':1},logs + [logs[0]])

    def test_48_missing_primary_search_evidence_rejected(self):
        logs = executed({'old':1,'new':1})
        logs[0]['evidence_url'] = ''
        with self.assertRaises(ValueError): benchmark([],{'a':True},{'old':1,'new':1},logs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
