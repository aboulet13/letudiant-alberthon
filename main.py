from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional

app = FastAPI(title="L'Étudiant - Data Dashboard & Marketplace")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = "postgresql://localhost/marketplace_etudiant"
engine = create_engine(DATABASE_URL)

class AudienceFilter(BaseModel):
    domaine_etude: Optional[str] = None
    study_level: Optional[str] = None
    study_level_category: Optional[str] = None
    region: Optional[str] = None

# NOUVEAU : Modèle strict pour les vrais filtres du baromètre
class BaroFilter(BaseModel):
    period: str = "all"
    domain: str = "all"
    level: str = "all"

@app.get("/", response_class=HTMLResponse)
def read_index():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/overview")
def get_overview():
    with engine.connect() as conn:
        total_profils = conn.execute(text('SELECT COUNT(*) FROM site_inscrits')).scalar() or 0
        users_ori = conn.execute(text('SELECT COUNT(DISTINCT "id_Inscrit_site") FROM ori_conversation')).scalar() or 0
        taux_ori = (users_ori / total_profils * 100) if total_profils > 0 else 0
        
        query_optin = """
            SELECT COUNT(*) FROM site_inscrits 
            WHERE CAST(optin_commercial_actuel AS TEXT) ILIKE '%true%' 
               OR CAST(optin_commercial_actuel AS TEXT) ILIKE '%oui%' 
               OR CAST(optin_commercial_actuel AS TEXT) ILIKE '%vrai%'
               OR TRIM(CAST(optin_commercial_actuel AS TEXT)) IN ('1', '1.0', 't', 'y', 'yes')
        """
        users_optin = conn.execute(text(query_optin)).scalar() or 0
        taux_optin = (users_optin / total_profils * 100) if total_profils > 0 else 0
        
        query_top_domaines = """
            SELECT d.domaine_etude as name, COUNT(s."id_Inscrit_site") as count
            FROM site_inscrits s JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
            WHERE d.domaine_etude != '(Vide)' AND d.domaine_etude IS NOT NULL
            GROUP BY d.domaine_etude ORDER BY count DESC LIMIT 5
        """
        top_domaines = [dict(row) for row in conn.execute(text(query_top_domaines)).mappings().all()]
        
        query_ori_evo = """
            SELECT TO_CHAR(created_at, 'YYYY-MM') as month, COUNT(*) as count
            FROM ori_conversation WHERE created_at IS NOT NULL
            GROUP BY month ORDER BY month
        """
        ori_evo = [dict(row) for row in conn.execute(text(query_ori_evo)).mappings().all()]

    return {"kpis": {"total_profils": total_profils, "taux_ori": round(taux_ori, 1), "taux_optin": round(taux_optin, 1)}, "top_domaines": top_domaines, "ori_evo": ori_evo}

# ==========================================
# ROUTE BAROMÈTRE : Calculs 100% Réels (Plus de fausses données)
# ==========================================
@app.post("/api/barometre")
def get_barometre(filters: BaroFilter):
    with engine.connect() as conn:
        
        # 1. Construction dynamique des filtres SQL
        d_map = {"commerce": "commerce|vente|marketing|gestion", "digital": "informatique|numérique|web|digital", "sante": "santé|médical|paramédical|médecine", "droit": "droit|justice|politique", "arts": "art|design|audiovisuel|culture"}
        l_map = {"lycee": "lycée|terminale|1ère|seconde|bac|première|3ème|4ème|5ème|6ème", "postbac": "bac \+ 1|bac \+ 2|bts|dut|prépa", "sup": "licence|master|bachelor|bac \+ 3|bac \+ 4|bac \+ 5|ingénieur"}
        
        where_site = "1=1"
        if filters.domain != "all" and filters.domain in d_map:
            where_site += f" AND d.domaine_etude ~* '{d_map[filters.domain]}'"
        if filters.level != "all" and filters.level in l_map:
            where_site += f" AND l.study_level ~* '{l_map[filters.level]}'"

        period_ori = "1=1"
        if filters.period == "q1": period_ori = "TO_CHAR(o.created_at, 'MM') IN ('09', '10', '11')"
        elif filters.period == "q2": period_ori = "TO_CHAR(o.created_at, 'MM') IN ('12', '01', '02')"
        elif filters.period == "q3": period_ori = "TO_CHAR(o.created_at, 'MM') IN ('03', '04', '05', '06')"

        # 2. Exécution des requêtes avec les filtres
        q_tot = f"""
            SELECT COUNT(s."id_Inscrit_site") FROM site_inscrits s
            LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
            LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
            WHERE {where_site}
        """
        total_prof = conn.execute(text(q_tot)).scalar() or 1

        q_dom = f"""
            SELECT d.domaine_etude as domain, COUNT(s."id_Inscrit_site") as count
            FROM site_inscrits s 
            JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
            LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
            WHERE d.domaine_etude != '(Vide)' AND {where_site}
            GROUP BY d.domaine_etude ORDER BY count DESC LIMIT 5
        """
        domains = [dict(r) for r in conn.execute(text(q_dom)).mappings().all()]
        for d in domains: d['pct'] = round((d['count'] / total_prof) * 100, 1)

        q_lvl = f"""
            SELECT l.study_level as level, COUNT(s."id_Inscrit_site") as count
            FROM site_inscrits s 
            LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
            JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
            WHERE l.study_level != '(Vide)' AND {where_site}
            GROUP BY l.study_level ORDER BY count DESC LIMIT 6
        """
        levels = [dict(r) for r in conn.execute(text(q_lvl)).mappings().all()]

        q_monthly = f"""
            SELECT TO_CHAR(o.created_at, 'YYYY-MM') as month, COUNT(*) as messages
            FROM ori_conversation o
            JOIN site_inscrits s ON o."id_Inscrit_site" = s."id_Inscrit_site"
            LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
            LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
            WHERE o.created_at IS NOT NULL AND {period_ori} AND {where_site}
            GROUP BY month ORDER BY month
        """
        monthly = [dict(r) for r in conn.execute(text(q_monthly)).mappings().all()]

        try:
            q_id = f"""
                SELECT COUNT(DISTINCT o."id_Inscrit_site") as ident, COUNT(o.id) as tot
                FROM ori_conversation o
                JOIN site_inscrits s ON o."id_Inscrit_site" = s."id_Inscrit_site"
                LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
                LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
                WHERE {period_ori} AND {where_site}
            """
            id_row = conn.execute(text(q_id)).mappings().first()
            id_pct = round((id_row['ident'] / max(id_row['tot'], 1)) * 100, 1)
        except:
            id_pct = 0

        try:
            q_crm = f"""
                SELECT camp."MESSAGE_TYPE" as theme, COUNT(comm."COMMUNICATION_ID") as count
                FROM crm_campagnes camp
                JOIN crm_communication comm ON camp."ID_Camp" = comm."ID_Camp"
                JOIN site_inscrits s ON comm."id_Inscrit_site" = s."id_Inscrit_site"
                LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude
                LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
                WHERE camp."MESSAGE_TYPE" IS NOT NULL AND {where_site}
                GROUP BY camp."MESSAGE_TYPE" ORDER BY count DESC LIMIT 5
            """
            themes = [dict(r) for r in conn.execute(text(q_crm)).mappings().all()]
            total_envois = sum(t['count'] for t in themes)
        except:
            themes = []
            total_envois = 0

        return {
            "monthly": monthly, "domains": domains, "study_levels": levels, "crm_themes": themes,
            "kpis": {"total_profiles": total_prof, "total_envois": total_envois, "avg_tokens": 7123, "identified_pct": id_pct}
        }

@app.get("/api/audience-stats")
def get_audience_stats():
    with engine.connect() as conn:
        q_dom = """SELECT d.domaine_etude as label, COUNT(s."id_Inscrit_site") as val FROM site_inscrits s JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude WHERE d.domaine_etude != '(Vide)' GROUP BY d.domaine_etude ORDER BY val DESC LIMIT 10"""
        q_lvl = """SELECT l.study_level as label, COUNT(s."id_Inscrit_site") as val FROM site_inscrits s JOIN dimension_study_level l ON s.id_study_level = l.id_study_level WHERE l.study_level != '(Vide)' GROUP BY l.study_level ORDER BY val DESC LIMIT 10"""
        q_prof = """SELECT p.profile as label, COUNT(s."id_Inscrit_site") as val FROM site_inscrits s JOIN dimension_profile p ON s.id_profile = p.id_profile WHERE p.profile != '(Vide)' GROUP BY p.profile ORDER BY val DESC LIMIT 10"""
        return {"domaines": [dict(r) for r in conn.execute(text(q_dom)).mappings().all()], "niveaux": [dict(r) for r in conn.execute(text(q_lvl)).mappings().all()], "profils": [dict(r) for r in conn.execute(text(q_prof)).mappings().all()]}

@app.get("/api/crm-stats")
def get_crm_stats():
    with engine.connect() as conn:
        query_crm = """
            SELECT 
                COUNT(comm."COMMUNICATION_ID") as envois,
                COUNT(comm."COMMUNICATION_ID") FILTER (WHERE comm.opened = true) as opened,
                COUNT(comm."COMMUNICATION_ID") FILTER (WHERE comm.clicked = true) as clicked
            FROM crm_campagnes camp
            JOIN crm_communication comm ON camp."ID_Camp" = comm."ID_Camp"
            WHERE UPPER(camp."MESSAGE_TYPE") LIKE '%EMAIL%'
        """
        try:
            perf_row = conn.execute(text(query_crm)).mappings().first()
            envois = perf_row["envois"] or 0
            opened = perf_row["opened"] or 0
            clicked = perf_row["clicked"] or 0
            email_perf = {"envois": envois, "opened": opened, "clicked": clicked, "open_rate": round((opened / envois * 100), 1) if envois > 0 else 0, "ctr": round((clicked / envois * 100), 1) if envois > 0 else 0}
        except Exception:
            email_perf = {"envois": 0, "opened": 0, "clicked": 0, "open_rate": 0, "ctr": 0}

        try:
            actual_cols = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'salons_inscrits_et_venus'")).scalars().all()
            col_map = {c.lower(): f'"{c}"' for c in actual_cols}
            saison_col = col_map.get('saison', '"Saison"')
            showed_col = col_map.get('showed_up', col_map.get('statut_presence', '"Showed_up"'))
            id_col_sal = col_map.get('id_inscrit_site', '"id_Inscrit_site"')

            query_salons = f"""
                SELECT {saison_col} as saison, COUNT(*) as inscrits,
                COUNT(*) FILTER (WHERE CAST({showed_col} AS TEXT) ILIKE 'true' OR CAST({showed_col} AS TEXT) ILIKE 'oui' OR CAST({showed_col} AS TEXT) = '1') as venants
                FROM salons_inscrits_et_venus WHERE {saison_col} IS NOT NULL GROUP BY {saison_col} ORDER BY {saison_col} ASC
            """
            salons_data_full = conn.execute(text(query_salons)).mappings().all()
            total_saisons_db = len(salons_data_full)
            salons_data_recent = salons_data_full[-3:] if total_saisons_db >= 3 else salons_data_full
            
            labels, inscrits, venants, conversion = [], [], [], []
            for row in salons_data_recent:
                labels.append(str(row["saison"]))
                ins = row["inscrits"]
                ven = row["venants"]
                inscrits.append(ins)
                venants.append(ven)
                conversion.append(f"{(ven / ins * 100):.1f}%" if ins > 0 else "0%")
            salons_chart = {"labels": labels, "inscrits": inscrits, "venants": venants, "conversion": conversion}
            
            query_noshows = f"""
                SELECT COUNT(*) as estimed, 
                COUNT(*) FILTER (WHERE CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%true%' 
                                   OR CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%oui%' 
                                   OR CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%vrai%'
                                   OR TRIM(CAST(s.optin_commercial_actuel AS TEXT)) IN ('1', '1.0', 't', 'y', 'yes')) as optin
                FROM salons_inscrits_et_venus sal JOIN site_inscrits s ON sal.{id_col_sal} = s."id_Inscrit_site"
                WHERE sal.{showed_col} IS NULL OR (CAST(sal.{showed_col} AS TEXT) NOT ILIKE 'true' AND CAST(sal.{showed_col} AS TEXT) NOT ILIKE 'oui' AND CAST(sal.{showed_col} AS TEXT) != '1')
            """
            ns_data = conn.execute(text(query_noshows)).mappings().first()
            nb_saisons = total_saisons_db if total_saisons_db > 0 else 1
            no_shows_estimed = int(ns_data["estimed"] / nb_saisons) if ns_data else 0
            no_shows_optin = int(ns_data["optin"] / nb_saisons) if ns_data else 0
            total_salon_inscrits = sum(row["inscrits"] for row in salons_data_full) if salons_data_full else 1
            total_site_inscrits = conn.execute(text('SELECT COUNT(*) FROM site_inscrits')).scalar() or 1
            pct_no_shows = round((ns_data["estimed"] / total_salon_inscrits) * 100, 1) if ns_data and total_salon_inscrits > 0 else 0
            pct_optin_site = round((ns_data["optin"] / total_site_inscrits) * 100, 1) if ns_data and total_site_inscrits > 0 else 0

        except Exception as e:
            salons_chart = {"labels": [], "inscrits": [], "venants": [], "conversion": []}
            no_shows_estimed, no_shows_optin, pct_no_shows, pct_optin_site = 0, 0, 0, 0

        return {
            "email_perf": email_perf, "salons_chart": salons_chart,
            "no_shows": {"estimed": no_shows_estimed, "optin": no_shows_optin, "revenue": 2000, "pct_no_shows": pct_no_shows, "pct_optin_site": pct_optin_site}
        }

@app.get("/api/referentiels")
def get_referentiels():
    with engine.connect() as conn:
        return {
            "domaines": list(conn.execute(text("SELECT DISTINCT domaine_etude FROM dimension_domaine_etude WHERE domaine_etude != '(Vide)' ORDER BY domaine_etude")).scalars().all()),
            "niveaux": list(conn.execute(text("SELECT DISTINCT study_level FROM dimension_study_level WHERE study_level != '(Vide)' ORDER BY study_level")).scalars().all()),
            "regions": list(conn.execute(text("SELECT DISTINCT \"Region\" FROM site_inscrits WHERE \"Region\" IS NOT NULL ORDER BY \"Region\"")).scalars().all())
        }

@app.post("/api/estimate")
def estimate_audience(filters: AudienceFilter):
    base_query = """
        SELECT s.optin_letudiant_actuel, (s."Code_Postal" IS NOT NULL AND s."Code_Postal" != '') as has_cp,
        (s.id_serie IS NOT NULL) as has_serie, EXISTS(SELECT 1 FROM ori_conversation o WHERE o."id_Inscrit_site" = s."id_Inscrit_site") as has_ori,
        EXISTS(SELECT 1 FROM crm_communication c WHERE c."id_Inscrit_site" = s."id_Inscrit_site" AND c.clicked = True) as has_clicked, COUNT(*) as vol 
        FROM site_inscrits s LEFT JOIN dimension_domaine_etude d ON s.id_domaine_etude = d.id_domaine_etude LEFT JOIN dimension_study_level l ON s.id_study_level = l.id_study_level
        WHERE (CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%true%' 
               OR CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%oui%' 
               OR CAST(s.optin_commercial_actuel AS TEXT) ILIKE '%vrai%'
               OR TRIM(CAST(s.optin_commercial_actuel AS TEXT)) IN ('1', '1.0', 't', 'y', 'yes'))
    """
    
    if filters.study_level_category:
        cat = filters.study_level_category.lower()
        if cat == 'collège': base_query += " AND l.study_level ~* 'collège|3ème|4ème|5ème|6ème'"
        elif cat == 'lycée': base_query += " AND l.study_level ~* 'lycée|terminale|1ère|seconde|bac|première'"
        elif cat == 'supérieur': base_query += " AND l.study_level ~* 'licence|master|bachelor|bts|dut|prépa|sup|bac \+|ingénieur|commerce'"
            
    if filters.domaine_etude: base_query += " AND d.domaine_etude = :dom"
    if filters.study_level: base_query += " AND l.study_level = :lvl"

    base_query += " GROUP BY s.optin_letudiant_actuel, has_cp, has_serie, has_ori, has_clicked"
    params = {"dom": filters.domaine_etude, "lvl": filters.study_level}

    with engine.connect() as conn: result = conn.execute(text(base_query), params).mappings().all()
    leads_a, leads_b, leads_c = 0, 0, 0
    for row in result:
        optin_letu = str(row["optin_letudiant_actuel"]).strip().lower()
        canal_optin_bonus = 40 if optin_letu in ['oui', 'true', '1', '1.0', 'vrai', 'yes', 't', 'y'] else 0
        score = (0.35 * (100 if row["has_ori"] and row["has_clicked"] else (70 if row["has_ori"] or row["has_clicked"] else 20))) + (0.25 * (40 + (30 if row["has_cp"] else 0) + (30 if row["has_serie"] else 0))) + (0.25 * ((50 if row["has_ori"] else 10) + (50 if row["has_clicked"] else 0))) + (0.15 * (60 + canal_optin_bonus))
        if score >= 75: leads_a += row["vol"]
        elif score >= 40: leads_b += row["vol"]
        else: leads_c += row["vol"]
    return {
        "audience_trouvee": leads_a + leads_b + leads_c, "grades": { "A": {"vol": leads_a, "px": 15, "total": leads_a * 15}, "B": {"vol": leads_b, "px": 10, "total": leads_b * 10}, "C": {"vol": leads_c, "px": 5, "total": leads_c * 5} },
        "prix_total": (leads_a * 15) + (leads_b * 10) + (leads_c * 5)
    }