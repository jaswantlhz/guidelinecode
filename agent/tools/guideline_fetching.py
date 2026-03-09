import requests
import logging

logger = logging.getLogger(__name__)

CPIC_API_BASE = "https://api.cpicpgx.org/v1"

def get_guideline_pdf(gene: str, drug: str) -> str:
    """
    Find the CPIC guideline URL for a given gene and drug using the CPIC API.
    """
    try:
        # 1. Resolve Drug Name to Drug ID (roughly) or just search Pairs
        # Since /pair only has ID, we might need to search /drug first?
        # Let's try filtering guidelines directly first, it might be easier.
        # Check /guideline endpoint:
        # https://api.cpicpgx.org/v1/guideline?name=ilike.*{gene}*&name=ilike.*{drug}*
        
        # Heuristic: CPIC guideline names are usually "CPIC Guideline for [Drug] and [Gene]"
        # But searching by name is fuzzy.
        
        # Better: Get all pairs for the gene, then check drug names.
        # We need a way to map Drug Name -> Drug ID or vice versa.
        
        # Let's try fetching the specific Pair via a join with Drug? 
        # PostgREST syntax allow embedded resources?
        # try: /pair?select=*,drug(*)&genesymbol=eq.{gene}&drug.name=ilike.{drug}
        
        params = {
            "genesymbol": f"eq.{gene}",
            "select": "*,drug(*)",
            "drug.name": f"ilike.{drug}"
        }
        resp = requests.get(f"{CPIC_API_BASE}/pair", params=params, timeout=30)
        resp.raise_for_status()
        pairs = resp.json()
        
        # Filter purely in python if API filter flaky
        candidates = []
        for p in pairs:
            # Check if drug name matches (handling case/partial)
            d_data = p.get("drug") or {}
            d_name = d_data.get("name", "")
            
            # If drug name matches OR if drug data is missing but API returned it
            if (d_name and (drug.lower() in d_name.lower() or d_name.lower() in drug.lower())):
                 candidates.append(p)
            elif not d_name:
                 # Fallback: if drug info missing in join, assume it's one of the matches
                 candidates.append(p)

        if not candidates:
             raise ValueError(f"No CPIC gene-drug pair found for {gene}/{drug}")

        # Prioritize by CPIC Level AND Name Match
        LEVEL_PRIORITY = {
            "A": 5, "B": 4, "B/C": 3, "C": 2, "D": 1
        }
        
        def get_priority(pair):
            score = 0
            # Level Priority
            lvl = pair.get("cpiclevel", "")
            score += LEVEL_PRIORITY.get(lvl, 0)
            
            # Name Match Priority (Bonus for explicit match over implicit/null)
            d_data = pair.get("drug") or {}
            d_name = d_data.get("name", "")
            if d_name and (drug.lower() in d_name.lower() or d_name.lower() in drug.lower()):
                score += 10
                
            return score
            
        # Sort descending by priority
        candidates.sort(key=get_priority, reverse=True)
        
        valid_pair = candidates[0]
        logger.info(f"Selected pair {valid_pair.get('pairid')} (Level {valid_pair.get('cpiclevel')}) for {gene}/{drug}. Guideline: {valid_pair.get('guidelineid')}")


             
        url = valid_pair.get("url", "") # Wait, does pair have URL? 
        # Earlier output: "guidelineid": 100416.
        # We need to fetch the guideline URL using guidelineid.
        
        gid = valid_pair.get("guidelineid")
        if not gid:
             # Check if it has a provisional URL or something?
             # If no guideline ID, maybe no guideline exists (Level C/D).
             raise ValueError(f"Pair {gene}/{drug} has no active CPIC guideline ID.")

        # Fetch Guideline
        g_resp = requests.get(f"{CPIC_API_BASE}/guideline?id=eq.{gid}", timeout=30)
        g_resp.raise_for_status()
        g_data = g_resp.json()
        
        if not g_data:
             raise ValueError(f"Guideline ID {gid} not found via API.")
             
        # The URL to the CPIC page
        return g_data[0].get("url", "")

    except Exception as e:
        logger.error(f"Error fetching guideline for {gene}/{drug}: {e}")
        raise ValueError(f"Failed to find guideline URL: {e}")