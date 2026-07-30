# shared-contracts

Contrats partagés entre le backend, le web et le mobile.

- `openapi/` : le schéma OpenAPI est généré depuis le backend (`make backend-dev` puis `GET /openapi.json`), et versionné ici à chaque évolution majeure de l'API.
- `error-codes.md` : codes d'erreur stables de l'API.

Les clients (Angular, Flutter) doivent être générés ou vérifiés contre ces contrats.
