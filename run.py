#!/usr/bin/env python3
import os
import sys
import logging
import dotenv
import requests
import json
import platform
import psutil
import uuid

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Charger les variables d'environnement avant d'importer les autres modules
dotenv.load_dotenv()

# Importer et exécuter les configurations depuis settings.py si disponible
logger.info("Chargement des configurations...")
try:
    from config import settings
    logger.info("Configurations chargées avec succès")
except ImportError:
    logger.warning("Module config.settings non trouvé, utilisation des variables d'environnement par défaut")
except Exception as e:
    logger.error(f"Erreur lors du chargement des configurations: {e}")

# Importer la fonction d'initialisation de la base de données
from db_init import init_database

# Fonction pour obtenir les informations système
def get_system_info():
    try:
        # Obtenir l'adresse MAC
        mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                               for elements in range(0, 48, 8)][::-1])
        
        # Obtenir l'adresse IP
        hostname = platform.node()
        ip_address = "127.0.0.1"  # Par défaut
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            logger.warning("Impossible de déterminer l'adresse IP, utilisation de 127.0.0.1")
        
        # Obtenir les informations sur le processeur
        processor = platform.processor() or "Unknown"
        if not processor or processor == "":
            processor = platform.machine()
        
        # Obtenir le nombre de cœurs
        num_cores = psutil.cpu_count(logical=False)
        if not num_cores:
            num_cores = psutil.cpu_count(logical=True)
        
        # Obtenir les informations sur la RAM
        ram_info = psutil.virtual_memory()
        ram_total_gb = round(ram_info.total / (1024**3))
        ram_available_gb = round(ram_info.available / (1024**3))
        
        # Obtenir les informations sur le disque
        disk_info = psutil.disk_usage('/')
        disk_total_gb = round(disk_info.total / (1024**3))
        disk_available_gb = round(disk_info.free / (1024**3))
        
        # Obtenir l'utilisation du CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        available_processor = 100 - cpu_usage
        
        return {
            "nom": hostname,
            "adresse_mac": mac_address,
            "ip": ip_address,
            "rom": disk_total_gb,
            "available_rom": disk_available_gb,
            "ram": ram_total_gb,
            "available_ram": ram_available_gb,
            "processeur": processor,
            "available_processor": available_processor,
            "number_of_core": num_cores
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations système: {e}")
        return None

# Fonction pour enregistrer le service auprès du service-cluster
def register_with_service_cluster():
    try:
        # Récupérer l'URL du service-cluster depuis les variables d'environnement
        service_cluster_host = os.getenv('SERVICE_CLUSTER_HOST')
        if not service_cluster_host:
            logger.error("La variable d'environnement SERVICE_CLUSTER_HOST n'est pas définie")
            return False
        
        # Construire l'URL complète
        register_url = f"{service_cluster_host}/api/service-clusters/"
        
        # Obtenir les informations système
        system_info = get_system_info()
        if not system_info:
            logger.error("Impossible d'obtenir les informations système")
            return False
        
        # Envoyer la requête POST au service-cluster
        logger.info(f"Tentative d'enregistrement auprès de {register_url} avec les données: {json.dumps(system_info)}")
        response = requests.post(
            register_url,
            json=system_info,
            headers={"Content-Type": "application/json"}
        )
        
        # Vérifier la réponse
        if response.status_code in [200, 201]:
            logger.info(f"Enregistrement réussi auprès du service-cluster: {response.json()}")
            return True
        else:
            logger.error(f"Erreur lors de l'enregistrement auprès du service-cluster: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement auprès du service-cluster: {e}")
        return False

# Point d'entrée principal
if __name__ == '__main__':
    # Récupérer le port de l'application depuis les variables d'environnement
    app_port = int(os.getenv('APP_PORT', 5003))
    logger.info(f"Port de l'application configuré: {app_port}")
    
    # Initialiser la base de données
    if not init_database():
        logger.error("Impossible de démarrer l'application en raison d'erreurs d'initialisation de la base de données.")
        sys.exit(1)
    
    # Enregistrer le service auprès du service-cluster
    if not register_with_service_cluster():
        logger.error("Impossible de démarrer l'application en raison d'erreurs d'enregistrement auprès du service-cluster.")
        sys.exit(1)
    
    # Démarrer l'application FastAPI avec uvicorn
    import uvicorn
    logger.info(f"Démarrage de l'application FastAPI sur le port {app_port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=app_port, reload=True)
