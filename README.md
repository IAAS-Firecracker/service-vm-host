# Service VM Host

Service de gestion des machines virtuelles Firecracker dans un environnement microservices.

## Architecture

Le service-vm-host fait partie d'un système microservices qui comprend :
- Service VM Host (ce service)
- Service VM Offer
- Service System Image
- Service Cluster
- Service User

## Structure du Projet

```
service-vm-host/
├── app.py                # Point d'entrée de l'application
├── config/              # Configuration et enregistrement Eureka
├── database.py          # Configuration SQLAlchemy
├── dependencies.py      # Dépendances FastAPI
├── models/             # Modèles SQLAlchemy
│   ├── model_user.py      # Modèle User
│   ├── model_vm_offers.py # Modèle VM Offer
│   ├── model_system_images.py # Modèle System Image
│   └── model_virtual_machine.py # Modèle VM
├── RabbitMQ/           # Consommateurs RabbitMQ
│   ├── consumer_vm_offer.py
│   ├── cosumer_system_image.py
│   └── consumer_user.py
├── routes/             # Routes FastAPI
│   └── virtual_machine_routes.py
├── utils/             # Utilitaires
│   ├── utils_ssh.py
│   └── utils_mac_adress.py
├── logs/              # Logs de l'application
└── ssh_keys_vm/       # Clés SSH pour les VMs
```

## Installation

1. Cloner le dépôt :
```bash
git clone <repository-url>
cd service-vm-host
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

3. Configurer les variables d'environnement :
   - Copier `.env.example` vers `.env`
   - Configurer les variables suivantes dans `.env` :
     - Base de données MySQL
     - RabbitMQ
     - Eureka Server
     - Exchanges RabbitMQ (vm-offer-exchange, system-image-exchange, user-exchange)

4. Initialiser la base de données :
```bash
python db_init.py
```

## Utilisation

1. Démarrer le serveur :
```bash
python app.py
```

2. Accéder à l'API :
   - API : http://localhost:5003
   - Documentation Swagger : http://localhost:5003/swagger

## Endpoints API

### Gestion des machines virtuelles
- `POST /api/service-vm-host/vm/create` : Crée une nouvelle machine virtuelle
- `POST /api/service-vm-host/vm/start` : Démarre une machine virtuelle existante
- `POST /api/service-vm-host/vm/stop` : Arrête une machine virtuelle
- `POST /api/service-vm-host/vm/delete` : Supprime une machine virtuelle
- `POST /api/service-vm-host/vm/status` : Obtient le statut d'une machine virtuelle
- `GET /api/service-vm-host/vms` : Liste toutes les machines virtuelles
- `GET /api/service-vm-host/vm/{user_id}/{vm_name}/metrics` : Obtient les métriques d'une VM

### Health Check
- `GET /health` : Vérifie la santé de l'application
- `GET /info` : Informations sur l'application

### Exemple de requête pour créer une VM
```json
{
    "name": "test-vm",
    "user_id": "1",
    "vm_offer_id": "1",
    "system_image_id": "1",
    "tap_ip": "10.0.0.2",
    "vm_mac": "02:00:00:00:00:01"
}
```

## Communication Inter-Services

Le service communique avec d'autres services via :
1. RabbitMQ pour les événements :
   - VM Offer Events
   - System Image Events
   - User Events

2. Eureka pour la découverte de services

## Sécurité

- Utilisation de clés SSH pour l'authentification des VMs
- Communication sécurisée via RabbitMQ
- Validation des requêtes via FastAPI et Pydantic

## Monitoring

- Logs disponibles dans le dossier `logs/`
- Métriques disponibles via l'endpoint `/metrics`
- Health check via `/health` et `/info`

## Déploiement

Le service peut être déployé via Docker :
```bash
docker build -t service-vm-host .
docker-compose up
```

En Local


```bash
#Service VM Host
SECRET_KEY=4b4017b60ba6766fa68ac34cda732625aceb1248483b363507c62a76aeb0fb3d5df4fbec77ebb94c409294ff1597ac093cee490e1e842674ab3c989a2162b1104214f0c802fe1d3ca8cbc823b162fc6fd986c53147a0a5b23467238feb9ff9c0f92135dbee5710550466a1013b20abd96496f61c1b44d74e9b3438c8fefa89cd

#Database configuration
MYSQL_HOST=localhost
MYSQL_PORT=13319
MYSQL_USER=firecracker
MYSQL_PASSWORD=firecracker
MYSQL_DB=service_vm_host_db
APP_PORT=5003
APP_NAME=service-vm-host

#Rabbit configuration
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

#URL
EUREKA_SERVER=http://localhost:8761/eureka/
SERVICE_CLUSTER_HOST=http://localhost:5000
SERVICE_CONFIG_URI=http://localhost:8080

#All Exchange
SERVICE_VM_OFFER_EXCHANGE=vm-offer-exchange
SERVICE_SYSTEM_IMAGE_EXCHANGE=system-image-exchange
SERVICE_USER_EXCHANGE=user-exchange
```

## Configuration des Permissions Firecracker

Les permissions nécessaires pour Firecracker sont définies dans `firecracker-sudoers`.

## Dépendances

Les principales dépendances sont :
- FastAPI >= 0.104.1
- SQLAlchemy >= 2.0.23
- Pydantic >= 2.4.2
- RabbitMQ (via pika)
- Eureka Client
- MySQL (via PyMySQL)

## License

Ce service est sous licence MIT.
