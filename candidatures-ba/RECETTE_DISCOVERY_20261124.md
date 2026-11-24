# Recette vérifiable — qualité de découverte de candidatures (24 novembre 2026)

## Portée et identité
- **Sujet** : SFD-DQ-01 à DQ-14 et code de découverte/qualification déterministe en **lecture seule**, préparés dans une PR draft. Les 17 SFD historiques sont reprises à l'identique depuis le commit figé `3cee0b0bdd5efc0b5e76727cb01bda5dd32334c9`.
- **Archive historique contrôlée en octets** : fichier Drive B86, SHA-256 `dffe6bb6a052849f2eb878fb87bd58364edf38478fc7b871e54fd982c466926e` (MATCH le 24/11/2026).
- **Source de la qualification fonctionnelle** : Google Sheets canonique onglet `Mandat`, B16, B42, B69, B77 et B79–B86, consultés le 24/11 ; état B83 = `LIBRE`. Aucun changement à la feuille.
- **Version exacte des fichiers testés (blobs Git)** :
  - `candidatures-ba/SFD_DISCOVERY_QUALITY_V1.md` : `0bdd29723d04334c49d2d77161f4d7166cf0d0ae`
  - `candidatures-ba/discovery_quality.py` : `5875753c225c8523d10f82586ce04718d091b967`
  - `candidatures-ba/test_discovery_quality.py` : `b0cd4d28542b5f6e14c9acf5999da62574409c12`

## Tests réellement exécutés dans un environnement Python local

Dossier de recette : extraction de l'archive B86 et ajout des trois fichiers ci-dessus, avec `pypdf` et `reportlab` disponibles.

| Commande effectivement exécutée | Résultat constaté |
| --- | --- |
| `python3 recette_hors_ligne.py` | **PASS** : 7 tests fictifs de non-régression SFD |
| `python3 -m unittest -v test_sfd test_discovery_quality` | **PASS** : 72 tests, dont 15 historiques et 57 nouveaux, 0 échec |
| `python3 -m pytest -q test_sfd.py test_discovery_quality.py` | **PASS** : 72 tests, 0 échec |
| `python3 -m compileall -q .` | **PASS** : aucune erreur de compilation |

**Total de scénarios distincts du socle et de l'extension : 79/79 PASS** (7 + 15 + 57). L'exécution pytest rejoue les 72 scénarios, elle n'augmente pas ce décompte.

### Contre-exemples et corrections réellement testés

- Mutation *salaire avant admissibilité* : rejetée comme attendu par `test_37_salary_only_after_eligibility` (exit=1 du mutant).
- Mutation *ouverture officielle inconnue admise* : rejetée après correction d'un horodatage de fixture par `test_15_unknown_opening_parks` (exit=1 du mutant).
- Mutation *obligatoire confondu avec souhaité* : rejetée par 5 tests de la suite (exit=1 du mutant).
- **Échec découvert pendant l'extension** : `test_49_only_pure_imports_in_discovery_module` rejetait à tort `from __future__ import annotations`. Le jeu de modules autorisés a été corrigé en ajoutant `__future__`, sans élargir les effets de bord. Suite intégrale réexécutée : **72/72 PASS**.
- Quatre contrôles additionnels `test_49`–`test_52` couvrent liste blanche d'imports, appels dangereux directs et non-mutation des entrées.

## Limites explicites et décision
- **PASS** = qualification locale des règles DQ et non-régression du socle figé, sur données fictives.
- **UNKNOWN** = gain empirique d'offres réelles admissibles/heure, rappel du marché, faux négatifs réels, activation ATS ou expérience bout-en-bout. Aucun A/B live n'a été prétendu exécuté.
- **UNKNOWN** = statut des GitHub Actions pour ce sujet : la lecture des runs GitHub au moment du contrôle retournait 0 run ; aucun PASS CI distant n'est revendiqué.
- **AUCUNE TRANSMISSION** : aucun Gmail, LinkedIn, ATS ni modification de Mandat/Candidatures ; B83 non réservé.
- **Décision** : conserver la PR en **draft**, sans fusion ni activation de la campagne sur cette extension. La validation synthétique des 79 scénarios est close ; la prochaine décision éventuellement utile est de mesurer une comparaison A/B réelle, à budget de recherche identique et avec une vérité terrain gelée, puis décider d'une adoption.
