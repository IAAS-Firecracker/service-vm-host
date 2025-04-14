#!/bin/bash

API_URL="http://localhost:5000"

echo "1. Création d'une nouvelle VM..."
curl -X POST $API_URL/vm/create \
-H "Content-Type: application/json" \
-d '{
    "name": "test-vm",
    "cpu_count": 2,
    "memory_size_mib": 1024,
    "disk_size_gb": 5,
    "image_name": "ubuntu-22.04.ext4"
}'
echo -e "\n"

sleep 2

echo "2. Démarrage de la VM..."
curl -X POST $API_URL/vm/start/test-vm
echo -e "\n"

sleep 2

echo "3. Vérification du statut de la VM..."
curl $API_URL/vm/status/test-vm
echo -e "\n"

echo "4. Liste de toutes les VMs..."
curl $API_URL/vm/list
echo -e "\n"

sleep 2

echo "5. Arrêt de la VM..."
curl -X POST $API_URL/vm/stop/test-vm
echo -e "\n"

sleep 2

echo "6. Suppression de la VM..."
curl -X DELETE $API_URL/vm/delete/test-vm
echo -e "\n"
