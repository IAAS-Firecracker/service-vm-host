from fastapi import APIRouter,Depends, HTTPException, BackgroundTasks,WebSocketDisconnect,WebSocket
from models.model_virtual_machine import VirtualMachine, VirtualMachineCreate, VMStartConfig, VMStopConfig, VMDeleteConfig, VMStatusConfig, VMStatus
from models.model_ssh_key import SSHKey
from models.model_vm_offers import VMOfferEntity
from models.model_system_images import SystemImageEntity
from utils.utils_ssh import generate_ssh_key_pair, save_ssh_key_to_db
from sqlalchemy.orm import Session
from database import SessionLocal
import subprocess
import json
import time
import os
from typing import Dict
from logging import getLogger
from utils.utils_ssh import generate_ssh_key_pair, save_ssh_key_to_db
from utils.utils_mac_adress import generate_ip_from_sequence, generate_tap_ip_from_sequence, generate_mac_address
from dotenv import load_dotenv
from dependencies import get_db,StandardResponse
import platform
import psutil
import uuid
import requests
import logging
import sys

import asyncio
import websockets
import json
import pty
import select
import termios
import struct
import fcntl
import subprocess
import time
import threading
from typing import Dict, Optional
from pydantic import BaseModel



logger = getLogger(__name__)


router = APIRouter(
    prefix="/api/service-vm-host",
    tags=["vm-host"],
    responses={404: {"description": "Not found"}},
)

# Charger les variables d'environnement avant d'importer les autres modules
load_dotenv()

class FirecrackerAPI:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def _make_request(self, method: str, path: str, data: dict = None) -> dict:
        try:
            curl_cmd = [
                "curl",
                "-X", method,
                "--unix-socket", self.socket_path,
                f"http://localhost{path}"
            ]
            
            if data:
                curl_cmd.extend(["-H", "Content-Type: application/json"])
                curl_cmd.extend(["-d", json.dumps(data)])
            
            result = subprocess.run(
                curl_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout) if result.stdout else {}
                except json.JSONDecodeError:
                    return {"raw_output": result.stdout}
            else:
                logger.error(f"Curl command failed: {result.stderr}")
                return {"error": result.stderr}
                
        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
            return {"error": str(e)}

    def get_metrics(self) -> Dict:
        """
        Récupère les métriques de la VM via l'API Firecracker.
        """
        try:
            logger.info("Getting VM metrics")
            machine_config = self._make_request("GET", "/machine-config")
            # vm_state = self._make_request("GET", "/vm")
            
            return {
                "machine_config": machine_config,
                # "state": vm_state
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            return {}

    def start_instance(self) -> bool:
        try:
            logger.info("Starting instance")
            return self._make_request("PUT", "/actions", {"action_type": "InstanceStart"})
        except Exception as e:
            logger.error(f"Error starting instance: {str(e)}")
            return False

    def stop_instance(self) -> bool:
        try:
            logger.info("Stopping instance")
            # D'abord, envoyer un signal d'arrêt gracieux
            self._make_request("PUT", "/actions", {"action_type": "SendCtrlAltDel"})
            
            # Attendre quelques secondes pour l'arrêt gracieux
            time.sleep(5)
            
            # Ensuite, forcer l'arrêt si nécessaire
            return self._make_request("PUT", "/actions", {"action_type": "InstanceHalt"})
        except Exception as e:
            logger.error(f"Error stopping instance: {str(e)}")
            return False

    def get_machine_config(self) -> Dict:
        try:
            logger.info("Getting machine config")
            curl_cmd = [
                "curl",
                "-X", "GET",
                "--unix-socket", self.socket_path,
                "http://localhost/machine-config"
            ]
            
            result = subprocess.run(
                curl_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {}
        except Exception as e:
            logger.error(f"Error getting machine config: {str(e)}")
            return {}

def start_firecracker_process(user_id: str, vm_name: str, socket_path: str) -> None:
    """
    Démarre le processus Firecracker et attend que le socket soit disponible.
    
    Args:
        user_id (str): ID de l'utilisateur
        vm_name (str): Nom de la VM
        socket_path (str): Chemin du socket Firecracker
    
    Raises:
        HTTPException: Si le démarrage échoue ou le timeout est atteint
    """
    logger.info("Starting Firecracker process")
    firecracker_process = subprocess.Popen([
        "./script_sh/start_firecracker.sh",
        user_id,
        vm_name
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Attendre que le socket soit disponible
    timeout = 30
    start_time = time.time()
    while not os.path.exists(socket_path):
        if time.time() - start_time > timeout:
            stderr_output = firecracker_process.stderr.read().decode()
            stdout_output = firecracker_process.stdout.read().decode()
            logger.error(f"Socket not created after {timeout} seconds")
            logger.error(f"Firecracker stdout: {stdout_output}")
            logger.error(f"Firecracker stderr: {stderr_output}")
            
            # Vérifier les logs Firecracker
            log_path = f"/opt/firecracker/logs/firecracker-{user_id}_{vm_name}.log"
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    logger.error(f"Firecracker logs: {f.read()}")
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start Firecracker. Stderr: {stderr_output}"
            )
        time.sleep(0.1)

    logger.info("Socket is available, waiting for API")
    time.sleep(2)  # Attendre que l'API soit prête



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


@router.get("/")
async def read_root():
    return {"message": "Firecracker VM Manager API"}

@router.post("/vm/create", response_model=StandardResponse)
async def create_vm(vm_config: VirtualMachineCreate, background_tasks: BackgroundTasks):
    try:
        logger.info(f"Creating VM: {vm_config.name} for user: {vm_config.user_id}")
        
        # Générer une paire de clés SSH
        ssh_key_pair = generate_ssh_key_pair()
        vm_config.ssh_public_key = ssh_key_pair['public_key']
        
        logger.info(f"Creating VM: {vm_config.name} for user: {vm_config.user_id}")
        
        # Valider les paramètres
        if not vm_config.ssh_public_key and not vm_config.root_password:
            raise HTTPException(
                status_code=400, 
                detail="Either ssh_public_key or root_password must be provided"
            )
        
        # Enregistrer la clé SSH dans la base de données
        db = SessionLocal()
        try:
            # Utiliser la fonction de utils_ssh.py pour enregistrer la clé SSH
            ssh_key_id = save_ssh_key_to_db(db, vm_config.user_id, ssh_key_pair)
        finally:
            db.close()


        if not vm_config.root_password:
            vm_config.root_password = "FirecrackerVM@2024"  # Mot de passe par défaut si non fourni

        # Enregistrer la VM dans la base de données 
        db = SessionLocal()
        try:
            # Créer un nouvel enregistrement de VM

            # Vérifier si la VM existe déjà
            existing_vm = db.query(VirtualMachine).filter_by(user_id=int(vm_config.user_id), name=vm_config.name).first()
            if existing_vm:
                return StandardResponse(
                    statusCode=400,
                    message="VM already exists: " + vm_config.name,
                    data={}
                )
            
            virtual_machine = VirtualMachine(
                user_id=int(vm_config.user_id),
                ssh_key_id=ssh_key_id,  # Utiliser l'ID de la clé SSH générée précédemment
                service_cluster_id=vm_config.service_cluster_id,
                vm_offer_id=vm_config.vm_offer_id,
                system_image_id=vm_config.system_image_id,
                root_password_hash=vm_config.root_password,
                name=vm_config.name,
                vcpu_count=vm_config.cpu_count,# de service-vm-offer
                memory_size_mib=vm_config.memory_size_mib,# de service-vm-offer
                disk_size_gb=vm_config.disk_size_gb,# de service-vm-offer
                network_namespace=f"ns_{vm_config.name.lower().replace(' ', '-')}",
                ssh_port=22,
                track_dirty_pages=True,
                allow_mmds_requests=True,
                status="creating",
            )
            
            # Ajouter et valider l'enregistrement
            db.add(virtual_machine)
            db.commit()
            db.refresh(virtual_machine)
            
            # Récupérer l'ID de la VM
            vm_id = virtual_machine.id
            logger.info(f"VM record saved with ID: {vm_id}")
            
            # Configurer les paramètres réseau de la VM
            vm_config.tap_device = f"tap{vm_id}"
            vm_config.vm_ip = generate_ip_from_sequence(vm_id)
            vm_config.tap_ip = generate_tap_ip_from_sequence(vm_id)
            vm_config.vm_mac = generate_mac_address(vm_config.vm_ip)
            
            # Mettre à jour la VM avec les nouvelles informations réseau
            logger.info(f"Updating VM with tap_device_name: {vm_config.tap_device}")
            logger.info(f"Updating VM with tap IP: {vm_config.tap_ip}")
            logger.info(f"Updating VM with ip_address: {vm_config.vm_ip}")
            logger.info(f"Updating VM with mac_address: {vm_config.vm_mac}")
            
            virtual_machine.tap_device_name = vm_config.tap_device
            virtual_machine.ip_address = vm_config.vm_ip
            virtual_machine.tap_ip = vm_config.tap_ip
            virtual_machine.mac_address = vm_config.vm_mac
            db.commit()
            db.refresh(virtual_machine)
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving VM to database: {str(e)}")
            return StandardResponse(
                statusCode=500,
                message="Failed to save VM configuration: " + str(e),
                data={}
            )
        finally:
            db.close()
            
        

        # Créer le dossier pour les sockets s'il n'existe pas
        socket_dir = "/tmp/firecracker-sockets"
        os.makedirs(socket_dir, exist_ok=True)
        os.chmod(socket_dir, 0o777)  # Donner les permissions nécessaires
        
        # Définir le chemin du socket unique pour cette VM
        socket_path = f"{socket_dir}/{vm_config.user_id}_{vm_config.name}.socket"
        
        # Supprimer l'ancien socket s'il existe
        if os.path.exists(socket_path):
            os.unlink(socket_path)

        # Démarrer le processus Firecracker
        start_firecracker_process(vm_config.user_id, vm_config.name, socket_path)

        # Créer le dossier de la VM
        vm_path = f"/opt/firecracker/vm/{vm_config.user_id}/{vm_config.name}"
        if os.path.exists(vm_path):
            return StandardResponse(
                statusCode=400,
                message="VM already exists firecracker: " + vm_config.name,
                data={}
            )

        os.makedirs(vm_path, exist_ok=True)

        # Préparer l'image personnalisée si elle n'existe pas
        custom_vm = f"/opt/firecracker/vm/{vm_config.user_id}/{vm_config.name}/{vm_config.os_type}.ext4"
        if not os.path.exists(custom_vm):
            logger.info(f"Preparing custom vm for user {vm_config.user_id}")
            prepare_result = subprocess.run(
                ["./script_sh/prepare_vm_image.sh", 
                 vm_config.os_type,
                 vm_config.user_id,
                 vm_config.ssh_public_key,
                 str(vm_config.disk_size_gb),
                 vm_config.name,
                 vm_config.root_password
                ],
                capture_output=True,
                text=True
            )
            if prepare_result.returncode != 0:
                logger.error(f"Failed to prepare custom vm: {prepare_result.stderr}")
                return StandardResponse(
                    statusCode=500,
                    message="Failed to prepare custom vm: " + prepare_result.stderr,
                    data={}
                )


        #Setup VM
        logger.info("Setting up VM")
        # Vérifier que tous les paramètres sont valides
        if not vm_config.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        if not vm_config.name:
            raise HTTPException(status_code=400, detail="Name is required")
        if not vm_config.os_type:
            raise HTTPException(status_code=400, detail="OS type is required")
        if not vm_config.disk_size_gb:
            raise HTTPException(status_code=400, detail="Disk size is required")
        if not vm_config.cpu_count:
            raise HTTPException(status_code=400, detail="CPU count is required")
        if not vm_config.memory_size_mib:
            raise HTTPException(status_code=400, detail="Memory size is required")
        if not vm_config.tap_device:
            raise HTTPException(status_code=400, detail="Tap device is required")
        if not vm_config.tap_ip:
            raise HTTPException(status_code=400, detail="Tap IP is required")
        if not vm_config.vm_ip:
            raise HTTPException(status_code=400, detail="VM IP is required")
        if not vm_config.vm_mac:
            raise HTTPException(status_code=400, detail="VM MAC is required")

        setting_up_vm = subprocess.run(
                ["./script_sh/setting_vm_image.sh", 
                 vm_config.os_type, 
                 vm_config.user_id, 
                 vm_config.ssh_public_key, 
                 str(vm_config.disk_size_gb), 
                 vm_config.name,
                 str(vm_config.cpu_count),
                 str(vm_config.memory_size_mib),
                 str(vm_config.tap_device),
                 str(vm_config.tap_ip),
                 str(vm_config.vm_ip),
                 str(vm_config.vm_mac)
                ],
                capture_output=True,
                text=True
            )
        if setting_up_vm.returncode != 0:
            logger.error(f"Failed to setting custom vm: {setting_up_vm.stderr}")
            return StandardResponse(
                statusCode=500,
                message="Failed to setting custom vm: " + setting_up_vm.stderr,
                data={}
            )        
        
        # Mettre à jour les informations de la VM dans la base de données
        db = SessionLocal()
        try:
            # Récupérer la VM créée précédemment
            vm = db.query(VirtualMachine).filter_by(
                user_id=int(vm_config.user_id), 
                name=vm_config.name
            ).first()
            
            if vm:
                # Mettre à jour les champs nécessaires
                vm.tap_device_name = vm_config.tap_device
                vm.ip_address = vm_config.vm_ip
                vm.tap_ip = vm_config.tap_ip
                vm.mac_address = vm_config.vm_mac
                vm.status = "created"
                #vm.os_type = vm_config.os_type
                
                # Enregistrer les modifications
                db.commit()
                logger.info(f"VM record updated with network information for VM ID: {vm.id}")
            else:
                logger.warning(f"Could not find VM record to update for {vm_config.name}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating VM in database: {str(e)}")
            # Ne pas lever d'exception ici pour ne pas interrompre le processus
        finally:
            db.close()
            
        logger.info(f"VM {vm_config.name} created successfully")
        return StandardResponse(
            statusCode=200,
            message=f"VM {vm_config.name} created successfully",
            data={
                "pid": 0,
                "ssh_key_id": ssh_key_id,
                "private_key": ssh_key_pair['private_key']
            }
        )

    except Exception as e:
        logger.error(f"Error creating VM: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error creating VM: {str(e)}",
            data={}
        )



@router.post("/vm/start", response_model=StandardResponse)
async def start_vm(vm_start_config: VMStartConfig):
    """
    Démarre une VM existante qui a déjà été créée et configurée.
    Cette fonction se contente de démarrer la VM sans refaire la configuration.
    """
    try:
        logger.info(f"Starting VM for user {vm_start_config.user_id}, VM ID: {vm_start_config.vm_id}")
        
        # Récupérer les informations de la VM depuis la base de données
        db = SessionLocal()
        try:
            vm = db.query(VirtualMachine).filter_by(
                user_id=vm_start_config.user_id,
                id=vm_start_config.vm_id
            ).first()
            
            if not vm:
                return StandardResponse(
                    statusCode=404,
                    message="VM not found in database",
                    data={}
                )
            
            # Vérifier que la VM a été correctement créée et configurée
            if not all([vm.tap_device_name, vm.ip_address, vm.tap_ip, vm.mac_address]):
                return StandardResponse(
                    statusCode=400,
                    message="VM is not properly configured. Please recreate the VM.",
                    data={}
                )
            
            # Vérifier si la VM est déjà en cours d'exécution
            if vm.status == "running":
                return StandardResponse(
                    statusCode=200,
                    message=f"VM {vm.name} is already running",
                    data={
                        "vm_ip": vm.ip_address,
                        "ssh_port": vm.ssh_port or 22
                    }
                )
        finally:
            db.close()

        # Vérifier l'existence du répertoire de la VM
        vm_dir = os.path.join("/opt/firecracker/vm", str(vm.user_id), str(vm.name))
        if not os.path.exists(vm_dir):
            return StandardResponse(
                statusCode=404,
                message="VM files not found. Please recreate the VM.",
                data={}
            )

        # Déterminer le type d'OS à partir des fichiers existants
        os_type = None
        for file in os.listdir(vm_dir):
            if file.endswith(".ext4"):
                os_type = file.replace(".ext4", "")
                break

        if os_type is None:
            return StandardResponse(
                statusCode=404,
                message="VM disk image not found. Please recreate the VM.",
                data={}
            )

        # Définir le chemin du socket (réutiliser la logique existante)
        socket_dir = "/tmp/firecracker-sockets"
        socket_path = f"{socket_dir}/{vm.user_id}_{vm.name}.socket"
        
        # Vérifier si Firecracker est déjà en cours d'exécution
        firecracker_running = os.path.exists(socket_path)
        
        if not firecracker_running:
            # Créer le répertoire des sockets si nécessaire
            os.makedirs(socket_dir, exist_ok=True)
            os.chmod(socket_dir, 0o777)
            
            # Démarrer le processus Firecracker seulement s'il n'est pas déjà en cours
            logger.info(f"Starting Firecracker process for VM {vm.name}")
            start_firecracker_process(str(vm.user_id), vm.name, socket_path)
        else:
            logger.info(f"Firecracker process already running for VM {vm.name}")

        # Démarrer la VM en utilisant les paramètres déjà configurés
        logger.info(f"Starting VM {vm.name} with existing configuration")
        start_result = subprocess.run(
            ["./script_sh/start_vm.sh",
             str(vm.user_id),
             str(vm.name),
             str(os_type),
             str(vm.vcpu_count),
             str(vm.memory_size_mib),
             str(vm.disk_size_gb),
             str(vm.tap_device_name),
             str(vm.tap_ip),
             str(vm.ip_address),
             str(vm.mac_address)
            ],
            capture_output=True,
            text=True
        )

        if start_result.returncode != 0:
            logger.error(f"Failed to start VM: {start_result.stderr}")
            return StandardResponse(
                statusCode=500,
                message=f"Failed to start VM: {start_result.stderr}",
                data={}
            )

        # Mettre à jour le statut de la VM en base de données
        db = SessionLocal()
        try:
            vm = db.query(VirtualMachine).filter_by(
                user_id=vm_start_config.user_id,
                id=vm_start_config.vm_id
            ).first()
            
            if vm:
                vm.status = "running"
                db.commit()
                logger.info(f"VM {vm.name} status updated to running")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating VM status: {str(e)}")
        finally:
            db.close()

        # Retourner les informations d'accès distant
        return StandardResponse(
            statusCode=200,
            message=f"VM {vm.name} started successfully and ready for remote access",
            data={
                "vm_ip": vm.ip_address,
                "ssh_port": vm.ssh_port or 22,
                "status": "running",
                "remote_access_info": {
                    "ssh_command": f"ssh root@{vm.ip_address}",
                    "note": "Use the private key provided during VM creation"
                }
            }
        )

    except Exception as e:
        logger.error(f"Error starting VM: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error starting VM: {str(e)}",
            data={}
        )

@router.post("/vm/stop", response_model=StandardResponse)
async def stop_vm(vm_stop_config: VMStopConfig):
    try:
        logger.info(f"Stopping VM: {vm_stop_config.vm_id}")
        
        #check user_id and vm_id
        db = SessionLocal()
        vm = db.query(VirtualMachine).filter_by(
            user_id=vm_stop_config.user_id,
            id=vm_stop_config.vm_id
        ).first()
        if not vm:
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )
        
        # Arrêter la VM
        stop_result = subprocess.run(
            ["./script_sh/stop_vm.sh", str(vm.user_id), vm.name,vm.tap_device_name],
            capture_output=True,
            text=True
        )
        
        if stop_result.returncode != 0:
            logger.error(f"Failed to stop VM: {stop_result.stderr}")
            return StandardResponse(
            statusCode=500,
            message=f"Failed to stop VM: {stop_result.stderr}",
            data={}
        )

        # Mettre à jour le statut de la VM
        vm.status = "stopped"
        db.commit() 

        logger.info(f"VM {vm.name} stopped successfully")
        return StandardResponse(
            statusCode=200,
            message=f"VM {vm.name} stopped successfully",
            data={}
        )

    except Exception as e:
        logger.error(f"Error stopping VM: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error stopping VM: {str(e)}",
            data={}
        )

@router.post("/vm/delete", response_model=StandardResponse)
async def delete_vm(vm_delete_config: VMDeleteConfig):
    try:
        logger.info(f"Deleting VM: {vm_delete_config.vm_id}")
        
        #check user_id and vm_id
        db = SessionLocal()
        vm = db.query(VirtualMachine).filter_by(
            user_id=vm_delete_config.user_id,
            id=vm_delete_config.vm_id
        ).first()
        if not vm:
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )
        
        # Supprimer la VM
        delete_result = subprocess.run(
            ["./script_sh/delete_vm.sh", str(vm.user_id), vm.name, vm.tap_device_name],
            capture_output=True,
            text=True
        )
        
        if delete_result.returncode != 0:
            logger.error(f"Failed to delete VM: {delete_result.stderr}")
            return StandardResponse(
            statusCode=500,
            message=f"Failed to delete VM: {delete_result.stderr}",
            data={}
        )

        #supprimer la vm de la base de données
        db.delete(vm)
        db.commit() 
        db.close()

        logger.info(f"VM {vm.name} deleted successfully")
        return StandardResponse(
            statusCode=200,
            message=f"VM {vm.name} deleted successfully",
            data={}
        )

    except Exception as e:
        logger.error(f"Error deleting VM: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error deleting VM: {str(e)}",
            data={}
        )

@router.post("/vm/status", response_model=StandardResponse)
async def get_vm_status(vm_status_config: VMStatusConfig):
    try:
        logger.info(f"Getting status for VM: {vm_status_config.vm_id}")
        
        #check user_id and vm_id
        db = SessionLocal()
        vm = db.query(VirtualMachine).filter_by(
            user_id=vm_status_config.user_id,
            id=vm_status_config.vm_id
        ).first()
        if not vm:
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
            )
        
        # Obtenir le statut de la VM
        status_result = subprocess.run(
            ["./script_sh/status_vm.sh", str(vm.user_id), vm.name],
            capture_output=True,
            text=True
        )

        logger.info(f"VM status: {status_result.stdout}")
        
        if status_result.returncode != 0:
            logger.error(f"Failed to get VM status: {status_result.stderr}")
            return StandardResponse(
            statusCode=500,
            message=f"Failed to get VM status: {status_result.stderr}",
            data={}
            )

        # Parser la sortie JSON
        try:
            status_output = status_result.stdout.strip()
            logger.info(f"VM status raw output: {repr(status_output)}")
            
            # Gérer le cas où la sortie contient plusieurs lignes
            # Chercher la ligne qui contient du JSON valide
            status_data = None
            for line in status_output.split('\n'):
                line = line.strip()
                if line and line.startswith('{') and line.endswith('}'):
                    try:
                        status_data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            
            if status_data is None:
                # Essayer de parser la sortie complète comme JSON
                status_data = json.loads(status_output)
            
            vm_status = status_data["status"]
            
            # Cas spéciaux selon le statut
            if vm_status == "not_found":
                return StandardResponse(
                    statusCode=404,
                    message="VM not found in filesystem",
                    data={}
                )
            elif vm_status == "error":
                return StandardResponse(
                    statusCode=500,
                    message=status_data.get("message", "VM status error"),
                    data={}
                )
            else:
                # Pour les statuts "running", "stopped", etc.
                # Extraire les informations de machine_config si disponibles
                machine_config = status_data.get("machine_config", {})
                
                # Créer l'objet VMStatus avec les données disponibles
                vm_status_obj = VMStatus(
                    name=vm.name,
                    status=vm_status,
                    cpu_usage=None,  # Pas de métriques temps réel disponibles
                    memory_usage=None,  # Pas de métriques temps réel disponibles
                    uptime=None  # Pas de métriques temps réel disponibles
                )
                
                # Préparer les données de réponse
                response_data = {
                    "status": vm_status_obj
                }
                
                # Ajouter machine_config si disponible (pour les VMs running)
                if machine_config:
                    response_data["machine_config"] = {
                        "vcpu_count": machine_config.get("vcpu_count"),
                        "mem_size_mib": machine_config.get("mem_size_mib"),
                        "smt": machine_config.get("smt"),
                        "track_dirty_pages": machine_config.get("track_dirty_pages")
                    }
                
                return StandardResponse(
                    statusCode=200,
                    message="VM status retrieved successfully",
                    data=response_data
                )
        except Exception as e:
            logger.error(f"Error parsing VM status: {str(e)}")
            return StandardResponse(
                statusCode=500,
                message="Invalid status response format " + str(e)+"\nLine :"+str(sys.exc_info()[2].tb_lineno),
                data={}
            )
        
    except Exception as e:
        logger.error(f"Error getting VM status: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error getting VM status: {str(e)}",
            data={}
        )

@router.get("/vms", response_model=StandardResponse)
async def list_vms(db: Session = Depends(get_db)):
    try:
        logger.info("Listing all VMs")
        
        # Obtenir la liste des VMs
        list_result = db.query(VirtualMachine).all() 
        
        if list_result is None:
            logger.error(f"Failed to list VMs: {list_result}")
            return StandardResponse(
            statusCode=500,
            message=f"Failed to list VMs: {list_result}",
            data={}
        )

        # Convertir chaque VirtualMachine en dictionnaire
        vms_list = [vm.to_dict() for vm in list_result]

        return StandardResponse(
            statusCode=200,
            message="VMs listed successfully",
            data={
                "vms": vms_list
            }
        )

    except Exception as e:
        logger.error(f"Error listing VMs: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error listing VMs: {str(e)}",
            data={}
        )

#get user vms
@router.get("/user/{user_id}", response_model=StandardResponse)
def get_user_vms(user_id: int, db: Session = Depends(get_db)):
    try:
        user_vms = db.query(VirtualMachine).filter(VirtualMachine.user_id == user_id).all()
        if user_vms:
            user_vms_list = [vm.to_dict() for vm in user_vms]
            return StandardResponse(
                statusCode=200,
                message="User VMs found",
                data={
                    "vms": user_vms_list
                }
            )
        else:
            return StandardResponse(
                statusCode=404,
                message="User VMs not found",
                data={}
            )
    except Exception as e:
        logger.error(f"Internal error: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message="Internal error",
            data={}
        )

@router.get("/vm/{user_id}/{vm_name}/metrics")
async def get_vm_metrics(user_id: str, vm_name: str):
    """
    Récupère les métriques d'une VM spécifique.
    """
    try:
        # Construire le chemin du socket
        socket_path = f"/tmp/firecracker-sockets/{user_id}_{vm_name}.socket"
        
        # Vérifier si la VM existe et est en cours d'exécution
        vm_dir = os.path.join("/opt/firecracker/vm", user_id, vm_name)
        pid_file = os.path.join('/opt/firecracker/logs', "firecracker-{user_id}_{vm_name}.pid")
        if not os.path.exists(vm_dir):
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )
            
        if not os.path.exists(socket_path):
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )

        # Vérifier si le processus est en cours d'exécution
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
                try:
                    os.kill(int(pid), 0)  # Vérifie si le processus existe
                except OSError:
                    return StandardResponse(
                    statusCode=404,
                    message="VM not found",
                    data={}
                    )

        # Créer une instance de l'API Firecracker
        api = FirecrackerAPI(socket_path)
        
        # Récupérer les métriques
        metrics = api.get_metrics()
        
        if "error" in metrics:
            return StandardResponse(
            statusCode=500,
            message=f"Failed to get metrics: {metrics['error']}",
            data={}
        )
            
        # Formater la réponse
        return StandardResponse(
            statusCode=200,
            message="VM metrics retrieved successfully",
            data={
                "vm_name": vm_name,
                "state": "running",
                "machine_config": metrics.get("machine_config", {}),
                # "vm_state": metrics.get("state", {})
            }
        )
        
    except HTTPException as he:
        return StandardResponse(
            statusCode=he.status_code,
            message=he.detail,
            data={}
        )
    except Exception as e:
        logger.error(f"Error getting VM metrics: {str(e)}")
        return StandardResponse(
            statusCode=500,
            message=f"Error getting VM metrics: {str(e)}",
            data={}
        )


class SSHConnectRequest(BaseModel):
    vm_id: str
    username: str = "root"

class SSHInputRequest(BaseModel):
    terminal_id: str
    input: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.terminal_connections: Dict[str, str] = {}  # terminal_id -> websocket_id

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Clean up terminal connections
        terminals_to_remove = [tid for tid, cid in self.terminal_connections.items() if cid == client_id]
        for terminal_id in terminals_to_remove:
            del self.terminal_connections[terminal_id]
            ssh_terminal_manager.cleanup_terminal(terminal_id)

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except:
                # Connection closed, clean up
                self.disconnect(client_id)

    async def broadcast_to_terminal(self, message: dict, terminal_id: str):
        if terminal_id in self.terminal_connections:
            client_id = self.terminal_connections[terminal_id]
            await self.send_personal_message(message, client_id)

manager = ConnectionManager()

class SSHTerminalEndpoint:
    def __init__(self, vm_manager=None):
        self.vm_manager = vm_manager
        self.terminals = {}
    
    def create_ssh_terminal(self, vm_id: str, username: str = 'root') -> str:
        """Create an interactive SSH terminal session"""
        # For demo purposes, we'll assume vm_manager exists
        # In real implementation, replace this with actual VM lookup
        vm_info = self.get_vm_info(vm_id)
        if not vm_info:
            raise ValueError("VM not found")
        
        # Create SSH command
        ssh_cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{vm_info["ip"]}'
        ]
        
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        
        # Start SSH process
        process = subprocess.Popen(
            ssh_cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )
        
        terminal_id = f"{vm_id}_{username}_{int(time.time())}"
        self.terminals[terminal_id] = {
            'process': process,
            'master_fd': master_fd,
            'slave_fd': slave_fd,
            'vm_id': vm_id,
            'username': username
        }
        
        return terminal_id
    
    def get_vm_info(self, vm_id: str) -> Optional[dict]:
        """Mock VM info - replace with actual VM manager implementation"""
        # This is a mock implementation
        mock_vms = {
            "vm1": {"ip": "192.168.1.100", "status": "running"},
            "vm2": {"ip": "192.168.1.101", "status": "running"},
        }
        return mock_vms.get(vm_id)
    
    def cleanup_terminal(self, terminal_id: str):
        """Clean up terminal resources"""
        if terminal_id in self.terminals:
            terminal = self.terminals[terminal_id]
            try:
                terminal['process'].terminate()
                os.close(terminal['master_fd'])
                os.close(terminal['slave_fd'])
            except:
                pass
            del self.terminals[terminal_id]
    
    def write_to_terminal(self, terminal_id: str, data: str):
        """Write data to terminal"""
        if terminal_id in self.terminals:
            terminal = self.terminals[terminal_id]
            try:
                os.write(terminal['master_fd'], data.encode())
            except OSError:
                self.cleanup_terminal(terminal_id)
    
    async def start_terminal_session(self, terminal_id: str):
        """Start reading from terminal and emit output"""
        if terminal_id not in self.terminals:
            return
            
        terminal = self.terminals[terminal_id]
        master_fd = terminal['master_fd']
        
        def read_terminal():
            while terminal['process'].poll() is None:
                try:
                    ready, _, _ = select.select([master_fd], [], [], 1)
                    if ready:
                        output = os.read(master_fd, 1024).decode('utf-8', errors='ignore')
                        # Use asyncio to send the message
                        asyncio.create_task(manager.broadcast_to_terminal({
                            'type': 'ssh_output',
                            'terminal_id': terminal_id,
                            'output': output
                        }, terminal_id))
                except OSError:
                    break
            
            # Cleanup when process ends
            asyncio.create_task(manager.broadcast_to_terminal({
                'type': 'ssh_disconnected',
                'terminal_id': terminal_id
            }, terminal_id))
            self.cleanup_terminal(terminal_id)
        
        # Run in thread to avoid blocking
        thread = threading.Thread(target=read_terminal)
        thread.daemon = True
        thread.start()

ssh_terminal_manager = SSHTerminalEndpoint()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get('type') == 'ssh_connect':
                await handle_ssh_connect(message, client_id)
            elif message.get('type') == 'ssh_input':
                await handle_ssh_input(message, client_id)
            elif message.get('type') == 'ssh_disconnect':
                await handle_ssh_disconnect(message, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)

async def handle_ssh_connect(data: dict, client_id: str):
    vm_id = data.get('vm_id')
    username = data.get('username', 'root')
    
    try:
        terminal_id = ssh_terminal_manager.create_ssh_terminal(vm_id, username)
        
        # Associate terminal with client
        manager.terminal_connections[terminal_id] = client_id
        
        # Start terminal session
        await ssh_terminal_manager.start_terminal_session(terminal_id)
        
        await manager.send_personal_message({
            'type': 'ssh_connected',
            'terminal_id': terminal_id,
            'status': 'connected'
        }, client_id)
        
    except Exception as e:
        await manager.send_personal_message({
            'type': 'ssh_error',
            'error': str(e)
        }, client_id)

async def handle_ssh_input(data: dict, client_id: str):
    terminal_id = data.get('terminal_id')
    input_data = data.get('input')
    
    if terminal_id and input_data:
        ssh_terminal_manager.write_to_terminal(terminal_id, input_data)

async def handle_ssh_disconnect(data: dict, client_id: str):
    terminal_id = data.get('terminal_id')
    if terminal_id:
        ssh_terminal_manager.cleanup_terminal(terminal_id)
        if terminal_id in manager.terminal_connections:
            del manager.terminal_connections[terminal_id]

# REST API endpoints
@router.post("/ssh/connect")
async def create_ssh_connection(request: SSHConnectRequest):
    """Create SSH terminal connection (REST endpoint)"""
    try:
        terminal_id = ssh_terminal_manager.create_ssh_terminal(request.vm_id, request.username)
        return {
            "terminal_id": terminal_id,
            "status": "created",
            "vm_id": request.vm_id,
            "username": request.username
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/ssh/{terminal_id}")
async def disconnect_ssh_terminal(terminal_id: str):
    """Disconnect SSH terminal"""
    ssh_terminal_manager.cleanup_terminal(terminal_id)
    return {"status": "disconnected", "terminal_id": terminal_id}

@router.get("/ssh/{terminal_id}/status")
async def get_terminal_status(terminal_id: str):
    """Get terminal status"""
    if terminal_id in ssh_terminal_manager.terminals:
        terminal = ssh_terminal_manager.terminals[terminal_id]
        return {
            "terminal_id": terminal_id,
            "status": "active" if terminal['process'].poll() is None else "inactive",
            "vm_id": terminal['vm_id'],
            "username": terminal['username']
        }
    else:
        raise HTTPException(status_code=404, detail="Terminal not found")

@router.get("/terminals")
async def list_terminals():
    """List all active terminals"""
    terminals = []
    for terminal_id, terminal in ssh_terminal_manager.terminals.items():
        terminals.append({
            "terminal_id": terminal_id,
            "vm_id": terminal['vm_id'],
            "username": terminal['username'],
            "status": "active" if terminal['process'].poll() is None else "inactive"
        })
    return {"terminals": terminals}