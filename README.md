# Interview Builder Offline v3

## Installation Windows
```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Bibliothèque
Ajoute autant de fichiers `.json` que souhaité dans `question_bank/`.

Les deux formats sont acceptés :
- `{ "questions": [...] }`
- `[...]`

L'application charge tous les `.json`, valide les champs, détecte les IDs dupliqués et affiche les erreurs JSON avec ligne/colonne au lieu de planter.

Aucune clé OpenAI et aucun appel API ne sont nécessaires.
