# Interview Builder

Application Streamlit permettant de sélectionner un questionnaire technique à partir
d'une banque JSON locale.

## Principes

- Python + Streamlit.
- Aucun appel à ChatGPT, aucune API LLM.
- Les questions sont stockées dans `question_bank.json`.
- L'utilisateur peut ajouter une ou plusieurs banques JSON à la banque intégrée.
- Un onglet fournit un prompt autonome à copier dans ChatGPT pour créer de nouvelles questions.
- L'application valide la structure du JSON avant utilisation.
- La sélection est locale et déterministe : filtres + heuristique de diversité/durée.
- Le questionnaire sélectionné peut être téléchargé en DOCX, Markdown ou JSON.

## Installation

```bash
python -m venv .venv
```

Windows :

```powershell
.venv\Scripts\activate
```

Puis :

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement Streamlit Cloud

Déposer le contenu du projet dans un dépôt GitHub puis sélectionner `app.py`
comme fichier principal.

## Format JSON

La racine doit contenir :

```json
{
  "schema_version": "1.0",
  "questions": []
}
```

Chaque question doit contenir :

```json
{
  "id": "unique-id",
  "question": "Question orale",
  "expected_answer": "Réponse attendue détaillée",
  "interviewer_memo": "Mémo détaillé pour l'interviewer",
  "follow_ups": [
    "Relance 1",
    "Relance 2"
  ],
  "themes": ["Architecture"],
  "scenario": "Contexte commun",
  "languages": ["C++"],
  "specialties": ["IoT"],
  "levels": ["Senior"],
  "technologies": ["MQTT", "gRPC"],
  "estimated_minutes": 5
}
```

### Règles pratiques

- `id` doit être unique.
- `follow_ups` doit être une liste.
- `estimated_minutes` doit être strictement positif.
- Les champs `languages`, `specialties`, `levels`, `technologies` et `themes`
  sont des listes.
- Une question peut appartenir à plusieurs thèmes/niveaux/technologies.
- Pour un questionnaire cohérent, utiliser le même `scenario` sur plusieurs questions.

## Exporter un questionnaire

Après génération, trois formats sont disponibles :
- **DOCX** : document Word prêt à transmettre ou modifier ;
- **Markdown** : format texte structuré ;
- **JSON** : format machine pour réutilisation/import.

## Ajouter des questions

1. Générer un ou plusieurs JSON dans ChatGPT avec le prompt fourni par l'application.
2. Sauvegarder chaque réponse dans un fichier `.json`.
3. Dans l'application, utiliser **Ajouter une ou plusieurs banques JSON**.
4. Sélectionner un ou plusieurs fichiers simultanément.
5. Chaque fichier valide est fusionné avec la banque intégrée et ses questions deviennent immédiatement disponibles.

Les fichiers sont ajoutés à la banque intégrée : il n'est donc pas nécessaire de fusionner
manuellement les questions dans un seul fichier. Les `id` doivent être uniques entre la banque
intégrée et tous les fichiers importés. Les fichiers invalides sont signalés sans empêcher les
autres fichiers valides d'être ajoutés.

## Architecture

```text
                +----------------------+
                | question_bank.json   |
                +----------+-----------+
                           |
                           v
+----------------+   +-----+------+   +---------------------+
| Filtres Streamlit +-> Validator |---> Sélection locale   |
+----------------+   +------------+    durée / diversité   |
                                               |
                                               v
                                      Questionnaire final
                                               |
                                               +--> Export JSON

ChatGPT (externe, manuel)
        |
        | prompt fourni par l'app
        v
   nouveau JSON
        |
        +--> upload dans l'app
```

L'application ne communique pas avec ChatGPT.
