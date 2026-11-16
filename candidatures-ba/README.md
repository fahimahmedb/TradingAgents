# Candidatures BA

Le dépôt versionne les spécifications fonctionnelles et les tests reproductibles. Le registre Google Sheets reste la source opérationnelle. Les pièces de candidature, preuves individuelles et coordonnées restent accessibles depuis leurs emplacements existants.

## Rejouer la recette

Depuis le dépôt, avec Python 3 et sa bibliothèque standard.

```bash
python3 recette_hors_ligne.py
```

Les tests utilisent des données fictives. Ils exercent la collision entre deux acteurs, la perte de confirmation après l’envoi, la reprise après panne du suivi, les autorisations et la vérification d’identité des pièces.

## Qualifier une exécution réelle

1. Vérifier l’offre, les autorisations en vigueur, le canal et les pièces exactes dans le mandat.
2. Définir un seul déposant pour l’opportunité et vérifier l’absence de passage concurrent. Consigner l’intention dans le registre.
3. Après l’action, relier la preuve externe à la référence et relire l’écriture du registre. Après une erreur ambiguë, réconcilier la preuve avant toute nouvelle tentative.
4. Qualifier chaque portail et chaque environnement d’exécution séparément. Le test local couvre un modèle et le résultat d’un pilote couvre le parcours effectivement observé.

La recette R3 de la lettre dépend du paquet versionné désigné par le mandat lorsqu’il est accessible. Le répertoire contient les tests du parcours, dont la portée est décrite dans [les SFD](SFD_V0_4.md).
