from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Date
from sqlalchemy.orm import declarative_base

# --- CONFIGURATION ---
DATABASE_URL = "postgresql://localhost/marketplace_etudiant"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

# --- DIMENSIONS ---
class Profile(Base):
    __tablename__ = 'dimension_profile'
    id_profile = Column(Integer, primary_key=True)
    profile = Column(String)

class StudyLevel(Base):
    __tablename__ = 'dimension_study_level'
    id_study_level = Column(Integer, primary_key=True)
    study_level = Column(String)

class DomaineEtude(Base):
    __tablename__ = 'dimension_domaine_etude'
    id_domaine_etude = Column(Integer, primary_key=True)
    domaine_etude = Column(String)

# --- TABLE PRINCIPALE ---
class SiteInscrit(Base):
    __tablename__ = 'site_inscrits'
    id_Inscrit_site = Column(Integer, primary_key=True)
    Date_de_creation = Column(DateTime)
    Naissance_Date = Column(Date)
    genre = Column(String)
    email = Column(String)
    Code_Postal = Column(String)
    Commune = Column(String)
    Region = Column(String)
    id_profile = Column(Integer)
    id_study_level = Column(Integer)
    id_domaine_etude = Column(Integer)
    id_serie = Column(Integer)
    optin_commercial_actuel = Column(String)
    optin_letudiant_actuel = Column(String)

# --- TABLES ORI (Manquantes tout à l'heure) ---
class ORIConversation(Base):
    __tablename__ = 'ori_conversation'
    id = Column(String, primary_key=True)
    id_Inscrit_site = Column(Integer)
    created_at = Column(DateTime)
    nb_input_tokens = Column(Integer)
    feedback = Column(Integer)

# --- TABLES CRM (Manquantes tout à l'heure) ---
class CRMCampagne(Base):
    __tablename__ = 'crm_campagnes'
    ID_Camp = Column(String, primary_key=True)
    MESSAGE_TYPE = Column(String)
    thematique = Column(String)
    Nb_Envois = Column(Integer)

class CRMCommunication(Base):
    __tablename__ = 'crm_communication'
    COMMUNICATION_ID = Column(String, primary_key=True)
    ID_Camp = Column(String)
    id_Inscrit_site = Column(Integer)
    opened = Column(Boolean)
    clicked = Column(Boolean)

# --- CRÉATION DES TABLES MANQUANTES ---
if __name__ == "__main__":
    print("⏳ Création des tables manquantes (ORI et CRM)...")
    # create_all ne supprime rien, il crée juste ce qui n'existe pas encore
    Base.metadata.create_all(engine)
    print("✅ Structure de la Marketplace complète !")