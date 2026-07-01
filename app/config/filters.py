DISCOVERY_KEYWORDS = [
    'discover', 'recommend', 'shuffle', 'repeat', 'playlist', 
    'similar', 'new music', 'find', 'explore', 'algorithm'
]

def build_discovery_sql_condition(classifications_alias='c'):
    """
    Builds a SQL WHERE clause condition that mirrors the frontend's 
    logic for finding 'discovery-related' content.
    """
    fields = [
        f"COALESCE({classifications_alias}.topic, '')", 
        f"COALESCE({classifications_alias}.core_complaint, '')",
        f"COALESCE({classifications_alias}.behaviour_pattern, '')",
        f"COALESCE({classifications_alias}.unmet_need, '')"
    ]
    concatenated = " || ' ' || ".join(fields)
    
    conditions = []
    for keyword in DISCOVERY_KEYWORDS:
        # SQLite LOWER() and LIKE for case-insensitive matching
        conditions.append(f"LOWER({concatenated}) LIKE '%{keyword}%'")
        
    return " (" + " OR ".join(conditions) + ") "
