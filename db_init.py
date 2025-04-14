#!/usr/bin/env python3
import os
import sys
import dotenv
import pymysql
import logging
from sqlalchemy import create_engine

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Charger les variables d'environnement avant d'importer les autres modules
dotenv.load_dotenv()


# Fonction pour initialiser la base de données
def init_database():
    try:
        logger.info("Initialisation de la base de données...")
        # Récupérer les informations de connexion depuis les variables d'environnement
        mysql_host = os.getenv('MYSQL_HOST')
        mysql_port = int(os.getenv('MYSQL_PORT'))
        mysql_user = os.getenv('MYSQL_USER')
        mysql_password = os.getenv('MYSQL_PASSWORD')
        mysql_db = os.getenv('MYSQL_DB')
        
        logger.info(f"Connexion à MySQL: {mysql_host}:{mysql_port} avec l'utilisateur {mysql_user}")
        
        # Créer la base de données si elle n'existe pas
        conn = pymysql.connect(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password
        )
        
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db}")
        conn.commit()
        
        logger.info(f"Base de données '{mysql_db}' créée ou déjà existante.")
        
        cursor.close()
        conn.close()
        
        # Maintenant importer les modèles et créer les tables
        from models import Base
        
        # Créer l'URL de connexion à la base de données
        database_url = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}"
        
        # Créer le moteur SQLAlchemy
        engine = create_engine(database_url)
        
        # Créer toutes les tables définies dans les modèles
        Base.metadata.create_all(engine)
        
        logger.info("Tables créées avec succès.")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        return False

if __name__ == "__main__":
    # Initialiser la base de données
    if init_database():
        logger.info("Base de données initialisée avec succès.")
        sys.exit(0)
    else:
        logger.error("Échec de l'initialisation de la base de données.")
        sys.exit(1)