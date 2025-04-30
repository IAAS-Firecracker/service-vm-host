# Service VM Host API

Une API Python pour gérer les machines virtuelles Firecracker dans le cadre du projet Tsore-Iaas-Firecracker.

## Fonctionnalités

- API RESTful complète pour gérer les machines virtuelles Firecracker
- Documentation Swagger intégrée
- Connexion à une base de données MySQL
- Intégration avec RabbitMQ pour la messagerie asynchrone
- Communication avec les autres services (service-cluster, service-system-image, service-vm-offer)

## Structure de la base de données

Table `vm_host` avec les champs suivants :
- `id` : Identifiant unique
- `name` : Nom de la machine virtuelle
- `cpu_count` : Nombre de cœurs CPU
- `memory_size_mib` : Taille de la mémoire RAM (en MiB)
- `disk_size_gb` : Taille du disque (en GB)
- `image_name` : Nom de l'image système utilisée
- `ip_address` : Adresse IP de la VM
- `mac_address` : Adresse MAC de la VM
- `status` : Statut de la VM (running, stopped, etc.)
- `created_at` : Date de création
- `updated_at` : Date de dernière mise à jour

## Installation

1. Cloner le dépôt :
```
git clone <repository-url>
cd Tsore-Iaas-Firecracker/service-vm-host
```

2. Créer un environnement virtuel et l'activer :
```
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
```

3. Installer les dépendances :
```
pip install -r requirements.txt
```

4. Configurer la base de données :
   - Créer une base de données MySQL nommée `service_vm_host_db`
   - Modifier le fichier `.env` avec vos informations de connexion

5. Initialiser la base de données :
```
python db_init.py
```

## Utilisation

1. Démarrer le serveur :
```
python main.py
```

2. Accéder à l'API :
   - API : http://localhost:5003/api
   - Documentation Swagger : http://localhost:5003/docs

## Endpoints API

### Gestion des machines virtuelles
- `POST /vm/create` : Crée une nouvelle machine virtuelle
- `POST /vm/start/{vm_name}` : Démarre une machine virtuelle
- `POST /vm/stop/{vm_name}` : Arrête une machine virtuelle
- `DELETE /vm/delete/{vm_name}` : Supprime une machine virtuelle
- `GET /vm/status/{vm_name}` : Obtient le statut d'une machine virtuelle
- `GET /vm/list` : Liste toutes les machines virtuelles

### Exemple de requête pour créer une VM
```json
{
    "name": "test-vm",
    "cpu_count": 2,
    "memory_size_mib": 1024,
    "disk_size_gb": 5,
    "image_name": "ubuntu-22.04.ext4",
    "ssh_key": "optional-ssh-public-key"
}
```

## Configuration .env docker

```
SECRET_KEY=your_secret_key_here

#Database configuration
MYSQL_HOST=mysql_db_service_vm_host
MYSQL_PORT=3306
MYSQL_USER=firecracker
MYSQL_PASSWORD=firecracker
MYSQL_DB=service_vm_host_db
APP_PORT=5003
APP_NAME=service-vm-host

#Rabbit configuration
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

#URL
EUREKA_SERVER=http://service-registry:8761/eureka/
SERVICE_CLUSTER_HOST=http://service-cluster:5003
SERVICE_CONFIG_URI=http://service-config:8080

#All Exchange
SERVICE_VM_OFFER_EXCHANGE=vm-offer-exchange
SERVICE_SYSTEM_IMAGE_EXCHANGE=system-image-exchange
```

## Configuration .env local

```
SECRET_KEY=your_secret_key_here

#Database configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
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
SERVICE_CLUSTER_HOST=http://localhost:5003
SERVICE_CONFIG_URI=http://localhost:8080

#All Exchange
SERVICE_VM_OFFER_EXCHANGE=vm-offer-exchange
SERVICE_SYSTEM_IMAGE_EXCHANGE=system-image-exchange
```
