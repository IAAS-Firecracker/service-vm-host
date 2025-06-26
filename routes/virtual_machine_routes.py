from fastapi import APIRouter,Depends, HTTPException, BackgroundTasks
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
    Démarre une VM existante.
    """
    try:
        #check user_id and vm_id
        logger.info(f"Check vm of user in database")
        db = SessionLocal()
        vm = db.query(VirtualMachine).filter_by(
            user_id=vm_start_config.user_id,
            id=vm_start_config.vm_id
        ).first()
        if not vm:
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )


        # Vérifier si la VM existe
        logger.info(f"Check vm of user in file")
        vm_dir = os.path.join("/opt/firecracker/vm", str(vm.user_id), str(vm.name))
        if not os.path.exists(vm_dir):
            return StandardResponse(
            statusCode=404,
            message="VM not found",
            data={}
        )

        # Déterminer le type d'OS
        logger.info(f"Check OStype")

        os_type = None
        for file in os.listdir(vm_dir):
            if file.endswith(".ext4"):
                os_type = file.replace(".ext4", "")
                break

        if os_type is None:
            return StandardResponse(
            statusCode=404,
            message="OS type not found",
            data={}
        )

        # Définir le chemin du socket unique pour cette VM
        socket_dir = "/tmp/firecracker-sockets"
        os.makedirs(socket_dir, exist_ok=True)
        os.chmod(socket_dir, 0o777)  # Donner les permissions nécessaires

        socket_path = f"{socket_dir}/{vm.user_id}_{vm.name}.socket"
        
        # Supprimer l'ancien socket s'il existe
        if os.path.exists(socket_path):
            os.unlink(socket_path)

        # Démarrer le processus Firecracker
        logger.info(f"Starting Firecracker Process")
        start_firecracker_process(str(vm.user_id), vm.name, socket_path)

        # Démarrer la VM
        logger.info(f"Starting VM {str(vm.name)}")
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

        return StandardResponse(
            statusCode=200,
            message=f"VM {vm.name} started successfully",
            data={
                # "pid": 0,
                # "ssh_key_id": ssh_key_id,
                # "private_key": ssh_key_pair['private_key']
            }
        )

    except HTTPException as he:
        return StandardResponse(
            statusCode=he.status_code,
            message=he.detail,
            data={}
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

@router.post("/vm/status", response_model=VMStatus)
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
        
        if status_result.returncode != 0:
            logger.error(f"Failed to get VM status: {status_result.stderr}")
            return StandardResponse(
            statusCode=500,
            message=f"Failed to get VM status: {status_result.stderr}",
            data={}
        )

        # Parser la sortie JSON
        try:
            status_data = json.loads(status_result.stdout)
            return VMStatus(
                name=vm.name,
                status=status_data["status"],
                cpu_usage=status_data.get("metrics", {}).get("cpu_usage"),
                memory_usage=status_data.get("metrics", {}).get("memory_usage"),
                uptime=status_data.get("metrics", {}).get("uptime")
            )
        except json.JSONDecodeError:
            return StandardResponse(
            statusCode=500,
            message="Invalid status response format",
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
