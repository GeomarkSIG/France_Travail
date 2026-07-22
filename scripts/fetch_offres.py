"""
Récupère les offres d'emploi de La Réunion (974) depuis l'API France Travail
et les écrit sous forme de GeoJSON pour affichage sur une carte Leaflet.

Identifiants requis (variables d'environnement) :
    FT_CLIENT_ID
    FT_CLIENT_SECRET
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"

PAGE_SIZE = 150
MAX_START_INDEX = 3000  # limite imposée par l'API
REQUEST_DELAY_S = 0.35  # marge sous la limite de débit du client_id (10 req/s en rafale)

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "offres.geojson"

# Les 24 communes de La Réunion (codes INSEE), utilisées pour contourner la
# limite de pagination de l'API (3150 résultats max par requête) : le
# département 974 compte à lui seul près de 5000 offres, on interroge donc
# commune par commune pour tout récupérer.
REUNION_COMMUNES = {
    "97401": "Les Avirons",
    "97402": "Bras-Panon",
    "97403": "Entre-Deux",
    "97404": "L'Étang-Salé",
    "97405": "Petite-Île",
    "97406": "La Plaine-des-Palmistes",
    "97407": "Le Port",
    "97408": "La Possession",
    "97409": "Saint-André",
    "97410": "Saint-Benoît",
    "97411": "Saint-Denis",
    "97412": "Saint-Joseph",
    "97413": "Saint-Leu",
    "97414": "Saint-Louis",
    "97415": "Saint-Paul",
    "97416": "Saint-Pierre",
    "97417": "Saint-Philippe",
    "97418": "Sainte-Marie",
    "97419": "Sainte-Rose",
    "97420": "Sainte-Suzanne",
    "97421": "Salazie",
    "97422": "Le Tampon",
    "97423": "Les Trois-Bassins",
    "97424": "Cilaos",
}


def get_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_commune_offres(session: requests.Session, token: str, commune_code: str) -> list[dict]:
    offres = []
    start = 0
    while start <= MAX_START_INDEX:
        end = start + PAGE_SIZE - 1
        # distance=0 : sans ce paramètre, "commune" fait une recherche par
        # rayon (défaut ~10-30 km) et non un filtre exact, ce qui génère un
        # fort recouvrement entre communes voisines.
        params = {"commune": commune_code, "distance": "0", "range": f"{start}-{end}"}
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        resp = session.get(SEARCH_URL, params=params, headers=headers, timeout=30)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "5"))
            time.sleep(wait)
            continue

        if resp.status_code == 204:
            break  # aucune offre pour cette commune

        resp.raise_for_status()
        payload = resp.json()
        offres.extend(payload.get("resultats", []))

        content_range = resp.headers.get("Content-Range", "")
        total = None
        if "/" in content_range:
            total = int(content_range.rsplit("/", 1)[-1])

        time.sleep(REQUEST_DELAY_S)

        if total is None or end + 1 >= total:
            break
        start += PAGE_SIZE

    return offres


# Les 14 grands domaines professionnels du référentiel ROME (France Travail),
# identifiés par la 1ère lettre du code ROME de l'offre (ex : "H2105" -> "H").
ROME_DOMAINES = {
    "A": "Agriculture et pêche, espaces naturels et espaces verts, soins aux animaux",
    "B": "Arts et façonnage d'ouvrages d'art",
    "C": "Banque, assurance, immobilier",
    "D": "Commerce, vente et grande distribution",
    "E": "Communication, média et multimédia",
    "F": "Construction, bâtiment et travaux publics",
    "G": "Hôtellerie-restauration, tourisme, loisirs et animation",
    "H": "Industrie",
    "I": "Installation et maintenance",
    "J": "Santé",
    "K": "Services à la personne et à la collectivité",
    "L": "Spectacle",
    "M": "Support à l'entreprise",
    "N": "Transport et logistique",
}


def to_feature(offre: dict) -> dict | None:
    lieu = offre.get("lieuTravail") or {}
    lat, lon = lieu.get("latitude"), lieu.get("longitude")
    if lat is None or lon is None:
        return None

    entreprise = offre.get("entreprise") or {}
    salaire = offre.get("salaire") or {}
    origine = offre.get("origineOffre") or {}
    romeCode = offre.get("romeCode") or ""

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "id": offre.get("id"),
            "intitule": offre.get("intitule"),
            "entreprise": entreprise.get("nom", "Entreprise non précisée"),
            "typeContrat": offre.get("typeContrat"),
            "typeContratLibelle": offre.get("typeContratLibelle"),
            "communeLibelle": lieu.get("libelle"),
            "codePostal": lieu.get("codePostal"),
            "dateCreation": offre.get("dateCreation"),
            "salaireLibelle": salaire.get("libelle"),
            "romeLibelle": offre.get("romeLibelle"),
            "romeDomaineCode": romeCode[:1] or None,
            "romeDomaine": ROME_DOMAINES.get(romeCode[:1]),
            "experienceExige": offre.get("experienceExige"),
            "experienceLibelle": offre.get("experienceLibelle"),
            "url": origine.get("urlOrigine"),
        },
    }


def main() -> None:
    client_id = os.environ.get("FT_CLIENT_ID")
    client_secret = os.environ.get("FT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Erreur : FT_CLIENT_ID et FT_CLIENT_SECRET doivent être définis.", file=sys.stderr)
        sys.exit(1)

    token = get_token(client_id, client_secret)

    session = requests.Session()
    seen_ids: set[str] = set()
    features = []

    for code, nom in REUNION_COMMUNES.items():
        offres = fetch_commune_offres(session, token, code)
        added = 0
        for offre in offres:
            oid = offre.get("id")
            if oid in seen_ids:
                continue
            seen_ids.add(oid)
            feature = to_feature(offre)
            if feature is not None:
                features.append(feature)
                added += 1
        print(f"{nom} ({code}) : {len(offres)} offre(s), {added} géolocalisée(s)")

    geojson = {
        "type": "FeatureCollection",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(features),
        "features": features,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(features)} offres géolocalisées écrites dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
