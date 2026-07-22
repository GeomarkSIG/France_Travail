# Carte des offres d'emploi — La Réunion (974)

Carte interactive (Leaflet) affichant les offres d'emploi publiées sur
[La Réunion](https://fr.wikipedia.org/wiki/La_R%C3%A9union), à partir de
l'[API France Travail](https://francetravail.io/) (offres d'emploi v2).

## Comment ça marche

- `scripts/fetch_offres.py` s'authentifie auprès de l'API France Travail
  (OAuth2 client_credentials) et récupère les offres géolocalisées des 24
  communes de La Réunion, puis écrit `data/offres.geojson`.
- `index.html` charge ce GeoJSON et affiche les offres sur une carte Leaflet
  avec regroupement (clustering), recherche par mot-clé et filtre par type
  de contrat.
- Un workflow GitHub Actions (`.github/workflows/update-data.yml`) relance
  le script chaque jour et commit les données mises à jour, afin que la
  carte reste à jour sans backend ni serveur.

Le `client_secret` de l'API n'est jamais exposé au navigateur : il n'est
utilisé que côté serveur (localement via `.env`, ou dans le job GitHub
Actions via les secrets du dépôt).

## Configuration locale

1. Créer une application sur [francetravail.io](https://francetravail.io/)
   avec accès à l'API **Offres d'emploi v2**, pour récupérer un
   `client_id` / `client_secret`.
2. Copier `.env.example` vers `.env` et renseigner les identifiants :
   ```
   FT_CLIENT_ID=...
   FT_CLIENT_SECRET=...
   ```
3. Installer les dépendances puis lancer le script :
   ```
   pip install -r requirements.txt
   python scripts/fetch_offres.py
   ```
4. Servir le dossier en local pour visualiser la carte (nécessaire car
   `fetch()` ne fonctionne pas sur `file://`) :
   ```
   python -m http.server 8974
   ```
   puis ouvrir http://localhost:8974/index.html

## Déploiement (GitHub Pages)

1. Dans les paramètres du dépôt GitHub : **Settings → Secrets and
   variables → Actions**, ajouter les secrets `FT_CLIENT_ID` et
   `FT_CLIENT_SECRET`.
2. **Settings → Pages** : déployer depuis la branche `main`, dossier `/root`.
3. Le workflow planifié met à jour `data/offres.geojson` chaque jour ; il
   peut aussi être lancé manuellement depuis l'onglet Actions
   (« Run workflow »).

## Fonds de plan

La carte propose trois fonds de plan (sélecteur en haut à droite) :
OpenStreetMap, Google Maps et Google Satellite. Les tuiles Google sont
chargées via les URL `mt.google.com` habituellement utilisées par les
projets Leaflet pour ce besoin ; il s'agit d'un usage non officiel (Google
ne fournit pas ces tuiles pour un usage hors de son propre produit Maps),
à garder en tête si le trafic devient important.

## Filtres et symbologie

- **Période** : "7 derniers jours" / "30 derniers jours" (glissants, basés
  sur `dateCreation`) ou toutes les dates.
- **Colorer / filtrer par** : bascule entre 3 légendes interactives (une
  seule à la fois pour rester lisible avec ~5 000 points) — cliquer une
  entrée de la légende isole/exclut cette catégorie.
  - *Type de contrat* : une couleur par code (CDI, CDD, Intérim…),
    assignation fixe (jamais recalculée selon la fréquence).
  - *Métier* : regroupement par grand domaine ROME (déduit de la 1ère
    lettre du code ROME). Seuls les 7 domaines les plus représentés à La
    Réunion ont une couleur dédiée ; les 7 autres domaines sont regroupés
    dans "Autres métiers" (gris) pour ne pas dépasser une palette de 8
    teintes lisibles. La liste des 7 domaines colorés est fixée dans
    `index.html` (`COLOR_MAPS.metier`) — à ajuster à la main si la
    répartition des offres change durablement.
  - *Expérience demandée* : variable ordinale (débutant → exigée), rendue
    avec une seule teinte du clair au foncé plutôt que des couleurs
    catégorielles.
- Au dézoom, les marqueurs proches sont regroupés en grappes neutres
  (couleur selon la taille du groupe, comme Leaflet.markercluster par
  défaut) — la coloration par catégorie n'est visible qu'en zoomant sur
  des marqueurs individuels.

## Licence

Ce projet est distribué sous licence [MIT](LICENSE).

## Notes sur l'API

- Le paramètre `commune` de l'API fait une recherche par rayon si
  `distance` n'est pas précisé : le script force `distance=0` pour un
  filtrage exact commune par commune (nécessaire aussi car l'API limite
  chaque requête à 3 150 résultats, et le département 974 compte à lui
  seul près de 5 000 offres).
- Seules les offres avec des coordonnées `lieuTravail.latitude` /
  `longitude` renseignées apparaissent sur la carte (quelques offres n'ont
  pas de géolocalisation précise et sont donc exclues).
