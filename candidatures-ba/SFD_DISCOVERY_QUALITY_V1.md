# SFD — Qualité de découverte et de qualification des candidatures

**Version** : 1.0, 24 novembre 2026. **Statut** : spécification et recette déterministe locale, **pas activation de recherche ni preuve d'amélioration empirique**.

**Autorité** : `Mandat` du Google Sheets `1ND-b3FhP-1oTyYgzxFzC4_nbus6rgBpa8ODCZh94HIE`, version lue V6.9 ; SFD-01 à SFD-17 historiques dans `candidatures-ba/SFD_V0_4.md` au commit Git `3cee0b0bdd5efc0b5e76727cb01bda5dd32334c9`. Ce document numérote les nouveautés **SFD-DQ-01 à SFD-DQ-14**, sans renuméroter ni remplacer SFD-01 à SFD-17.

## Écart constaté et objectif

Le bilan opérationnel canonique du 23/11 à ~23:05 (Mandat!B42/B69) décrit des offres eXalt et Fortify non qualifiées du fait d'exigences formelles ou spécialisées et aucune transmission. La recherche Deep Research initiale et les échanges ont mis en évidence huit risques méthodologiques : concentration sectorielle et sur certains employeurs, vocabulaire trop étroit, seniors nombreux, confusion obligatoire/souhaité, sous-exploitation des compétences transférables, couverture non mesurée, occasions manquées non mesurées et absence de duel contrôlé entre méthodes. Ces constats constituent des **hypothèses de défaut de qualité**, non une mesure exhaustive d'erreurs sur le marché.

**Objet** : augmenter les offres **distinctes, ouvertes, réellement admissibles et non déjà transmises**, découvertes par heure observée, sans réduire les exigences du Mandat. Un classement ou un rapport de recherche n'est ni un dépôt, ni un reçu ATS. Les messages entrants restent en lecture seule, SFD-10/B83 reste obligatoire avant tout effet externe.

## Exigences et critères d'acceptation

| SFD | Problème | Règle vérifiable | Contrôle principal |
| --- | --- | --- | --- |
| DQ-01 | Répétition des mêmes grandes entreprises et banques | Répartir les requêtes par au moins dix familles sectorielles distinctes, dont assurances/mutuelles, fintechs, infrastructures, éditeurs, petites ESN, cabinets et employeurs directs ; garder une trace du secteur effectivement exploré. | T02, T39 ; répartition sectorielle observable, HHI publié |
| DQ-02 | Titre « BA Finance » trop exclusif | Générer des requêtes avec au moins huit familles d'intitulés sur un budget test de 30 requêtes : analyste fonctionnel, AMOA, chef de projet MOA, PMO SI, PO fonctionnel, etc. | T03 et couverture `ROLES` |
| DQ-03 | Dépendance à peu de jobboards | Alterner sites ATS employeur, Apec, France Travail et jobboards ; le moteur **ne confond pas source de découverte et preuve d'ouverture**. | T04, T14 |
| DQ-04 | Résultats trop seniors | Distinguer minimum d'expérience **obligatoire** (>3 ans = `PARK_SENIORITY`) d'expérience **souhaitée** ; ne pas afficher comme éligible un profil non établi. | T20, T21, T22 |
| DQ-05 | Confusion exigences formelles/souhaits | Classer chaque exigence `mandatory`, `preferred`, ou `unknown`. Une obligatoire non établie déclenche `PARK_MANDATORY_GAP`, une préférence non remplie est affichée sans élimination ; formulation inconnue = `PARK_REQUIREMENT_WORDING`. | T23–T27, T29 |
| DQ-06 | Compétences transférables mal utilisées | Utiliser les compétences réellement attestées : trois ans d'alternance comme expérience projet bancaire, pas comme 3 ans de monétique spécialisée ; DES sans équivalence Master ; anglais B1/TOEIC 735, pas fluent. Conserver les réalisations transposables plutôt que les seules correspondances exactes de titres. | T23, T24, T26 et revue humaine de l'annonce |
| DQ-07 | Offres périmées ou non vérifiées | Pour dire `open`, obtenir un statut ATS/officiel avec horodatage horodaté de moins de 72 h et identité cohérente. Annonce agrégateur, statut absent, incohérence ou preuve ancienne -> PARK, jamais ouverture inventée. | T13–T15, T30b–T30e |
| DQ-08 | Déduplication incomplète intercanaux | Dédupliquer par employeur + référence, URL canonique avec paramètres de tracking retirés et alias attestés ; même rôle/lieu sans identité = `PARK_POSSIBLE_ALIAS`. Une transmission incertaine reste bloquée. | T31–T36 |
| DQ-09 | Couverture marché non mesurée | Journaliser nombre et diversité de requêtes **exécutées**, source, date et preuve ; mesurer couverture **observée des secteurs et sources**, sans prétendre à un rappel du marché entier. | T01–T06, T45–T48 |
| DQ-10 | Opportunités manquées invisibles | Sur un jeu d'offres étiqueté **avant** la comparaison, compter vrais positifs, faux positifs et faux négatifs constatés par rapport à ce seul jeu, avec identité SHA du jeu gelé. | T39, T41–T44 |
| DQ-11 | Aucune comparaison reproductible ancienne/nouvelle recherche | Pour chaque méthode, budget de requêtes identique et journal d'exécution distinct ; refuser budget incomparable, requêtes en double et items hors jeu étiqueté. Un benchmark synthétique n'établit pas de supériorité sur le marché. | T39–T42, T45–T48 |
| DQ-12 | Classements favorisant salaire ou volume au détriment de l'admissibilité | Trier d'abord les offres qualifiées, ensuite le salaire fixe publié ; l'absence de salaire ne disqualifie pas. Mesurer *offres qualifiées uniques / minutes observées* séparément du nombre d'annonces et des dépôts. | T08, T37–T38 et mesure de campagne future |
| DQ-13 | Faux rejets et faux PASS dus aux inconnues | Statuts explicites `EXCLUDE`, `PARK`, `PASS`, sans transformer l'inconnu en rejet définitif ni en éligibilité. Distinguer BdF/ACPR **employeur/client final** d'une ligne d'expérience au CV. | T09–T12, T16–T19, T27–T30 |
| DQ-14 | Qualité de découverte confondue avec droit de candidater | Le module est **sans effet externe** : il ne transmet, n'ouvre pas de session ATS, n'envoie pas de courriel, ne réserve pas B83, ne modifie pas Mandat. `PASS` signifie **admissible pour le contrôle de dossier**, pas `SUBMITTED`. La passerelle SFD-05 à 17 et LM-QA R3 reste seule autorisée pour la transmission. | Absence de fonction réseau et de mutateur Sheets/Gmail ; intégration E2E = UNKNOWN |

## Contrat d'entrée, de sortie et de preuve

- Entrée découverte : recherche avec `method`, `query_id`, `query_text`, `sector`, `role`, `source`, `observed_at`, `evidence_url` ; ne qualifier « exécutée » que si preuve consultable. Source officielle pour l'ouverture distincte de la découverte sur agrégateur.
- Entrée offre : employeur, référence, lien exact, contrat, localisation, missions projet, exigences annotées (`mandatory/preferred/unknown`), preuve officielle (`url`, `status`, `observed_at`, `reference` si présente) et `decision_as_of` horodaté ; tout fait candidat attribué au CV V3 et aux confirmations écrites du mandat.
- Sortie : `PASS`, `PARK_*`, `EXCLUDE_*`, `ALREADY_TRACKED`, `BLOCK_DUPLICATE`, `NEW`, `PARK_POSSIBLE_ALIAS` ; motifs visibles ; aucune candidature soumise.
- Métriques : requêtes planifiées/réellement effectuées, annonces distinctes, entreprises et secteurs distincts, doublons, ouvertures officielles, admissibles, `PARK` par motif, faux positifs/faux négatifs sur jeu gelé, minutes observées et rendement. Temps manquant = `UNKNOWN`.
- Seuil de promotion : aucune promotion automatique sur 53 tests synthétiques. Exiger une campagne A/B sur sources **réellement consultées**, même budget mesuré, annotation des dossiers à l'aveugle et corroboration dans `Candidatures`, puis décision selon gain marginal et taux de faux positifs.

## Contre-exemples et frontières

1. Une offre « chef de projet MOA » destinée à 8 ans minimum n'est pas admissible, même très bien payée.
2. Une offre de « gestionnaire projet SI » ne doit pas être ratée au seul motif que « Business Analyst » manque de l'intitulé.
3. Une mention de régulation ACPR n'équivaut **pas** à un client final ACPR ; le champ `end_client` doit contenir l'identité du client final, pas une description réglementaire.
4. Une annonce publiquement visible il y a 15 jours ne prouve pas une ouverture actuelle ; la date de publication ne remplace pas le dernier contrôle officiel.
5. Une simulation de requêtes documente le comportement du code, **pas** une recherche de marché effectivement exécutée.
6. Une case `PASS` auto-déclarée pour une lettre ne remplace jamais la vérification de fond B72/B74 ; une chaîne d'affirmation correspondant à un bout de texte ne prouve pas sa véracité.

## Recette et cycle de correction

Exécution reproductible : `python3 -m unittest -v test_discovery_quality` dans ce dossier (stdlib uniquement) et `python3 -m compileall -q .`. Tous les cas doivent réussir. Chaque changement au moteur doit refaire la suite complète. Le module ne remplace pas `candidatures-ba/circuit.py`, les 22 tests historiques R3 ni le connecteur de transmission. **La qualification intégrée réelle (nouvelle méthode + données de marché réelles + Sheets + ATS) est distincte et reste UNKNOWN tant que non exécutée.**

**État au 24/11** : 53 tests unitaires déterministes exécutés avec succès en local sur l'implémentation associée ; 0 offre réelle recherchée par ce code, 0 dépôt et 0 preuve d'amélioration prospective. En cas de divergence GitHub/local, le test du SHA publié doit être rejoué avant PASS distant.
