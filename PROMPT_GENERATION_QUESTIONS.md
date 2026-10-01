# Prompt ChatGPT — générer des questions pour Interview Builder Offline

Génère des objets JSON compatibles avec `question_bank.json`.

Paramètres à remplacer :
- Domaine : IoT
- Rôle : Tech Lead
- Langages : C++, Python
- Technologies : MQTT, gRPC, AWS
- Nombre : 20

Chaque objet doit contenir :
{
  "id": "identifiant_unique_snake_case",
  "tags": ["tags"],
  "topics": ["Sujet"],
  "title": "Titre",
  "question": "Question naturelle à poser oralement",
  "expected_answer": "Réponse attendue détaillée",
  "interviewer_memo": "Mémo technique détaillé pour l'interviewer",
  "follow_ups_and_signals": "Relances, bons signaux, signaux faibles et erreurs"
}

Contraintes :
- entretien oral ;
- éviter les questions de pure récitation ;
- mélanger théorie, scénarios, debugging, architecture, production et arbitrages ;
- adapter la difficulté au rôle ;
- Tech Lead = architecture + arbitrage + leadership technique ;
- le mémo doit être assez détaillé pour éviter une révision préalable ;
- tags précis pour permettre une sélection locale ;
- concepts durables plutôt que détails de version ;
- retourner uniquement un tableau JSON, sans Markdown ni texte autour.
