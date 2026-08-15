# Réception de factures par courriel

Chaque client a une adresse de dépôt unique :

`factures+<ingest_token>@factureflow.evolutionb.ca`

Le sous-adressage (`+<token>`) permet de savoir à quel compte appartient une
facture sans exposer l'adresse personnelle du client. Le token est créé dans
`profiles.ingest_token` à l'inscription.

## Flux n8n

1. Une boîte dédiée reçoit les courriels, par exemple `factures@factureflow.evolutionb.ca`.
2. n8n lit le destinataire et garde le texte situé entre `+` et `@`.
3. Pour chaque pièce jointe PDF/JPG/JPEG/PNG, n8n envoie un `POST` multipart à
   `https://api.factureflow.evolutionb.ca/ingest/email` avec :
   - `file` : la pièce jointe;
   - `recipient_token` : le token extrait de l'adresse;
   - `portee` : `entreprise` par défaut;
   - header `X-Inbound-Secret` : la valeur privée de `INBOUND_EMAIL_SECRET`.
4. L'API valide le secret, trouve le client, puis traite la facture dans son
   propre espace. Les fichiers temporaires sont supprimés après l'extraction.

N8N ne doit jamais envoyer les pièces jointes à Notion. Notion peut suivre les
leads ou le projet, tandis que Supabase conserve les métadonnées de factures.
