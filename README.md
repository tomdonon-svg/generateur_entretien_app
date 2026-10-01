# Interview Builder Offline

Application Streamlit 100 % locale, sans API OpenAI.

## Installation Windows

Installe Python depuis https://www.python.org/downloads/

Dans PowerShell, dans le dossier :

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Le navigateur s'ouvre ensuite sur l'application.

## Fonctionnement

L'application sélectionne localement les questions de `question_bank.json`
selon les langages, domaine, rôle et technologies.

Elle affiche les quatre blocs :
- question ;
- réponse attendue ;
- mémo interviewer ;
- relances / signaux.

Elle permet l'export Word et Markdown.

## Ajouter des questions

Utilise `PROMPT_GENERATION_QUESTIONS.md` dans ChatGPT pour générer de nouvelles
questions. Ajoute ensuite les objets JSON dans `question_bank.json`.

Aucune requête Internet ou OpenAI n'est effectuée par l'application.
