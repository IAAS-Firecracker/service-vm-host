from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
import subprocess
import json
import os
import time
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv
import uuid
from fastapi.middleware.cors import CORSMiddleware
from config.eureka_client import register_with_eureka, shutdown_eureka
from config.settings import load_config
import sys
from database import init_database, create_tables
import uvicorn
from RabbitMQ.consumer_vm_offer import rabbitmq_consumer
from RabbitMQ.cosumer_system_image import system_image_consumer
from RabbitMQ.consumer_user import user_consumer
from routes.virtual_machine_routes import router as virtual_machine_router
from routes.virtual_machine_routes import register_with_service_cluster
# Charger les variables d'environnement
load_dotenv()


# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'firecracker.log')),
        logging.StreamHandler()  # Pour afficher aussi dans la console
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Firecracker VM Manager API",
    description="API pour gérer les machines virtuelles avec Firecracker",
    version="1.0.0",
    docs_url="/swagger"
)

# Importer et exécuter les configurations depuis settings.py si disponible
logger.info("Chargement des configurations...")
try:
    load_config()
    logger.info("Configurations chargées avec succès")
except ImportError:
    logger.warning("Module config.settings non trouvé, utilisation des variables d'environnement par défaut")
except Exception as e:
    logger.error(f"Erreur lors du chargement des configurations: {e}")

# Ajouter le middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to RabbitMQ and start consuming on startup
@app.on_event("startup")
async def startup_event():
    # Enregistrer le service auprès du service-cluster
    await register_with_eureka()


    # Initialiser la base de données
    init_database()
        # Ajouter des données de test
        #seed_database()

    # Enregistrer le service auprès du service-cluster
    if not register_with_service_cluster():
        logger.error("Impossible de démarrer l'application en raison d'erreurs d'enregistrement auprès du service-cluster.")
        sys.exit(1)
    
    # Start the RabbitMQ consumers in background threads
    rabbitmq_consumer.start_consuming()
    logger.info("Started RabbitMQ consumer for VM offer events")
    
    system_image_consumer.start_consuming()
    logger.info("Started RabbitMQ consumer for System Image events")
    
    user_consumer.start_consuming()
    logger.info("Started RabbitMQ consumer for User events")

# Stop RabbitMQ consumers on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    #deregister Eureka
    await shutdown_eureka()
    rabbitmq_consumer.stop_consuming()
    logger.info("Stopped VM offer RabbitMQ consumer")
    
    system_image_consumer.stop_consuming()
    logger.info("Stopped System Image RabbitMQ consumer")
    
    user_consumer.stop_consuming()
    logger.info("Stopped User RabbitMQ consumer")

@app.get("/health", tags=["health"])
async def health_check():
    """Vérifie la santé de l'application"""
    return {"status": "UP", "service": "SERVICE-VM-HOST"}

@app.get("/info", tags=["info"])
async def info():
    """Retourne des informations sur l'application"""
    return {"status": "UP", "service": "SERVICE-VM-HOST"}

app.include_router(virtual_machine_router)


# Point d'entrée principal
if __name__ == '__main__':
    # Récupérer le port de l'application depuis les variables d'environnement
    app_port = int(os.getenv('APP_PORT', 5003))
    logger.info(f"Port de l'application configuré: {app_port}")
    # Initialiser la base de données
    if init_database():
        #creation de la base de donnee
        create_tables()
        #seed_test_data()
        # Démarrer l'application FastAPI avec uvicorn
        logger.info(f"Démarrage de l'application FastAPI sur le port {app_port}...")
        uvicorn.run("app:app", host="0.0.0.0", port=app_port, reload=True)
    else:
        logger.error("Impossible de démarrer l'application en raison d'erreurs d'initialisation.")
        sys.exit(1)
