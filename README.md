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
