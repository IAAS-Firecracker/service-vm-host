#!/usr/bin/env python3
import os
import subprocess
import random
import string
import time
import logging
from pathlib import Path
from fastapi import HTTPException
from models.model_ssh_key import SSHKey

# Configure logging
logger = logging.getLogger(__name__)

def generate_ssh_key_pair():
    """
    Generate an SSH key pair for a VM.
    
    Returns:
        dict: A dictionary containing the private key, public key, and key name.
    
    Raises:
        RuntimeError: If the key generation fails.
    """
    # Generate a random key name with timestamp
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    timestamp = int(time.time())
    key_name = f'vm_{random_string}_{timestamp}'
    
    # Define paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ssh_keys_dir = os.path.join(base_dir, 'ssh_keys_vm')
    private_key_path = os.path.join(ssh_keys_dir, key_name)
    public_key_path = f"{private_key_path}.pub"
    
    # Create directory if it doesn't exist
    os.makedirs(ssh_keys_dir, exist_ok=True)
    
    try:
        # Generate the SSH key pair
        logger.info(f"Generating SSH key pair: {key_name}")
        result = subprocess.run(
            ['ssh-keygen', '-t', 'rsa', '-b', '4096', '-f', private_key_path, '-N', ''],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Set appropriate permissions
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        # Read the generated keys
        with open(private_key_path, 'r') as f:
            private_key = f.read()
        
        with open(public_key_path, 'r') as f:
            public_key = f.read()
        
        return {
            'private_key': private_key,
            'public_key': public_key,
            'key_name': key_name,
            'private_key_path': private_key_path,
            'public_key_path': public_key_path
        }
    
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to generate SSH key pair: {e.stderr}"
        logger.error(error_message)
        raise RuntimeError(error_message)
    except Exception as e:
        error_message = f"Error generating SSH key pair: {str(e)}"
        logger.error(error_message)
        raise RuntimeError(error_message)

def delete_ssh_key_pair(key_name):
    """
    Delete an SSH key pair by name.
    
    Args:
        key_name (str): The name of the key to delete.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ssh_keys_dir = os.path.join(base_dir, 'ssh_keys_vm')
        private_key_path = os.path.join(ssh_keys_dir, key_name)
        public_key_path = f"{private_key_path}.pub"
        
        # Delete the keys if they exist
        for path in [private_key_path, public_key_path]:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted SSH key: {path}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting SSH key pair: {str(e)}")
        return False

def get_ssh_key_content(key_name, public=True):
    """
    Get the content of an SSH key.
    
    Args:
        key_name (str): The name of the key.
        public (bool): Whether to get the public key (True) or private key (False).
    
    Returns:
        str: The content of the key.
    
    Raises:
        FileNotFoundError: If the key doesn't exist.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ssh_keys_dir = os.path.join(base_dir, 'ssh_keys_vm')
    key_path = os.path.join(ssh_keys_dir, key_name)
    
    if public:
        key_path = f"{key_path}.pub"
    
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"SSH key not found: {key_path}")
    
    with open(key_path, 'r') as f:
        return f.read()

def list_ssh_keys():
    """
    List all SSH keys in the ssh_keys_vm directory.
    
    Returns:
        list: A list of dictionaries containing key information.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ssh_keys_dir = os.path.join(base_dir, 'ssh_keys_vm')
    
    if not os.path.exists(ssh_keys_dir):
        return []
    
    keys = []
    for file in os.listdir(ssh_keys_dir):
        if file.endswith('.pub'):
            key_name = file[:-4]  # Remove .pub extension
            keys.append({
                'key_name': key_name,
                'created_at': os.path.getctime(os.path.join(ssh_keys_dir, file)),
                'public_key_path': os.path.join(ssh_keys_dir, file),
                'private_key_path': os.path.join(ssh_keys_dir, key_name)
            })
    
    return keys

def save_ssh_key_to_db(db, user_id, ssh_key_pair):
    """
    Enregistre une clé SSH dans la base de données.
    
    Args:
        db (Session): Session de base de données SQLAlchemy
        user_id (int): ID de l'utilisateur propriétaire de la clé
        ssh_key_pair (dict): Dictionnaire contenant les informations de la clé SSH
        
    Returns:
        int: ID de la clé SSH enregistrée
    
    Raises:
        HTTPException: Si une erreur survient lors de l'enregistrement de la clé
    """

    
    try:
        # Créer un nouvel enregistrement de clé SSH en utilisant le modèle SQLAlchemy
        ssh_key = SSHKey(
            user_id=int(user_id),
            name=ssh_key_pair['key_name'],
            public_key=ssh_key_pair['public_key'],
            private_key=ssh_key_pair['private_key']
        )
        
        # Ajouter et valider l'enregistrement
        db.add(ssh_key)
        db.commit()
        db.refresh(ssh_key)
        
        # Récupérer l'ID de la clé SSH
        ssh_key_id = ssh_key.id
        logger.info(f"SSH key saved with ID: {ssh_key_id}")
        
        return ssh_key_id
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving SSH key to database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving SSH key: {str(e)}")

