# Candidatures BA

Ce répertoire versionne [les SFD](SFD_V0_4.md), la génération des pièces, les contrôles et la recette. Google Sheets porte le mandat actif, les intentions et les preuves individuelles. Les entrées JSON et les PDF réels sont privés.

## Rejouer la recette

Depuis ce répertoire, avec Python 3, `pypdf`, `reportlab`, Poppler et les polices Liberation Sans et Liberation Serif. Si nécessaire, pointer `CANDIDATURES_FONT_DIR` vers le dossier des quatre fichiers TTF Regular et Bold.

```bash
python3 recette_hors_ligne.py
python3 -m unittest -v test_sfd
```

## Préparer et contrôler un dossier

L’entrée JSON assemble `offer` (source et référence exactes, admissibilité et preuves), `route` (canal, destination et étapes observées), `registry` (lignes rapprochées entre canaux), `request` (autorité, type de dépôt et champs en suspens) et le chemin et l’empreinte du CV V3 revérifiés dans `canonical_cv` et `canonical_cv_sha256`. Les jeux fictifs de `test_sfd.py` montrent les champs attendus.

```bash
python3 controle_dossier.py dossier.json CV.pdf --prepare
python3 compose_letter_v5.py dossier.json CV.pdf lettre.pdf generation.json
python3 lm_gate.py dossier.json CV.pdf generation.json revue.json recu.json
python3 controle_dossier.py dossier.json CV.pdf --generated generation.json --review revue.json
```

Pour générer la lettre, le dossier inclut les directives actives, une trace de lecture, des faits sourcés et le projet propre à l’offre. Inspecter le PNG et le texte extraits avant de remplir `revue.json`. La revue atteste les sept contrôles `R3_CHECKS` avec observations, en reprenant le contexte et les empreintes de `generation.json`. Pour un canal CV seul vérifié, passer le contrôle de dossier sans les deux options de lettre. Une option de motivation bloque l’exception. Une modification des octets, de l’offre, des règles ou de la destination entraîne un nouveau contrôle.

Dans `pieces.py`, `make_variant` réordonne les blocs issus du V3 et vérifie leurs faits et leur extraction. `qualify_variant` lie le contrôle visuel aux empreintes du V3, de la variante et de son rendu. Enregistrer le reçu sur le dossier. Le choix de `select_cv` repose sur la référence exacte et l’autorisation active dans le mandat.

## Réserver, transmettre, réconcilier

- Appeler `sheets_guard.js` avec les outils Sheets, l’identifiant du suivi et le `sheetId` de Mandat. Initialiser `B83` à `LIBRE` une seule fois. Le script utilise `findReplace` sur la cellule seule et vérifie l’acquisition par relecture. Les index sont à base zéro.
- Après acquisition, relire le dossier et ses alias, consigner puis relire l’intention en J. Transmettre par le canal employeur vérifié uniquement si le contrôle est au vert. Le dépôt reste opéré par le connecteur Gmail ou le navigateur autorisé. Conserver le propriétaire et le résultat vérifié de la tentative.
- Écrire puis relire le résultat et libérer avec le jeton du propriétaire. Pour un effet externe incertain, joindre la preuve disponible et enregistrer l’incertitude avant de libérer. Si le suivi est indisponible, réconcilier avant toute reprise. Aucun déverrouillage automatique sur délai.

Qualifier séparément chaque portail et environnement. Le résultat des tests locaux décrit le code exercé. Une qualification de dépôt requiert une preuve externe reliée à la ligne et aux pièces. Pour la concurrence, tous les déposants du périmètre doivent appliquer la réservation.
