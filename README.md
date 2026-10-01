# Générateur d'entretien technique — application web

Cette version est une vraie petite application web Streamlit.

Elle fonctionne dans un navigateur et permet de générer :
- un questionnaire oral ;
- exactement 6 parties choisies dynamiquement par le modèle ;
- des questions adaptées au langage, domaine, rôle et technologies ;
- un mémo détaillé pour l'interviewer ;
- des relances et signaux ;
- un fichier Markdown ;
- un fichier Word.

## Option recommandée : Streamlit Community Cloud

1. Crée un dépôt GitHub.
2. Mets dedans :
   - `app.py`
   - `requirements.txt`
3. Va sur https://share.streamlit.io/
4. Connecte ton dépôt GitHub.
5. Sélectionne `app.py`.
6. Déploie.
7. L'application s'ouvre dans ton navigateur.

La clé API peut être saisie directement dans l'interface. Pour un usage personnel,
c'est simple. Pour une application partagée, il est préférable de mettre la clé
dans les Secrets de Streamlit plutôt que de demander aux utilisateurs de la saisir.

## Exécution locale

Si Python est installé :

```bash
pip install -r requirements.txt
streamlit run app.py
```

Puis ouvrir l'URL affichée par Streamlit.

## Paramètres

- Langages / frameworks
- Domaine
- Rôle
- Technologies
- Durée
- Nombre de questions
- Contexte complémentaire
- Modèle OpenAI

Le modèle décide lui-même des six parties. Il n'y a pas de liste de six parties
codée en dur dans l'application.
