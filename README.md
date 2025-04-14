# Firecracker VM Manager API

Cette API Python permet de gérer les machines virtuelles Firecracker via une interface REST.

## Installation

1. Installez les dépendances :
```bash
pip install -r requirements.txt
```

2. Lancez l'API :
```bash
python main.py
```

L'API sera accessible sur `http://localhost:5000`

## Points d'accès API

### Création d'une VM
```http
POST /vm/create
```
Corps de la requête :
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

### Démarrage d'une VM
```http
POST /vm/start/{vm_name}
```

### Arrêt d'une VM
```http
POST /vm/stop/{vm_name}
```

### Suppression d'une VM
```http
DELETE /vm/delete/{vm_name}
```

### Statut d'une VM
```http
GET /vm/status/{vm_name}
```

### Liste des VMs
```http
GET /vm/list
```

## Documentation API

La documentation Swagger de l'API est disponible à l'adresse : `http://localhost:5000/docs`
