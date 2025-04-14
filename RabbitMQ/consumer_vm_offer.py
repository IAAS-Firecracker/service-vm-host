#!/usr/bin/env python3
import os
import json
import logging
import threading
import pika
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from models import VMOffer, Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration de la base de données
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DB", "service_vm_host_db")

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# Configuration SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class RabbitMQConsumer:
    """
    A utility class to handle RabbitMQ connections and consuming messages
    for the service-vm-host application.
    """
    
    def __init__(self):
        """Initialize the RabbitMQ connection and channel."""
        self.connection = None
        self.channel = None
        self.exchange_name = os.getenv('SERVICE_VM_OFFER_EXCHANGE', 'vm-offer-exchange')
        self.queue_name = f"{self.exchange_name}-vm-host-queue"
        self.host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.port = int(os.getenv('RABBITMQ_PORT', 5672))
        self.user = os.getenv('RABBITMQ_USER', 'guest')
        self.password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.consumer_thread = None
        self.is_running = False
        
    def connect(self):
        """Establish connection to RabbitMQ server and set up the exchange and queue."""
        try:
            # Create connection parameters
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            # Establish connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare the fanout exchange
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type='fanout',
                durable=True
            )
            
            # Declare a queue with a unique name for this service
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                exclusive=False,
                auto_delete=False
            )
            
            # Bind the queue to the exchange
            self.channel.queue_bind(
                exchange=self.exchange_name,
                queue=self.queue_name
            )
            
            logger.info(f"Successfully connected to RabbitMQ and bound queue {self.queue_name} to exchange {self.exchange_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False
    
    def process_message(self, ch, method, properties, body):
        """
        Process a message received from RabbitMQ.
        
        Args:
            ch: The channel
            method: The method
            properties: The properties
            body: The message body
        """
        try:
            # Parse the message
            message = json.loads(body)
            action = message.get('action')
            data = message.get('data')
            
            logger.info(f"Received {action} event for VM offer: {data.get('id')}")
            
            # Process based on action
            if action == 'create' or action == 'update':
                self.sync_vm_offer(data)
            elif action == 'delete':
                self.delete_vm_offer(data.get('id'))
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Reject the message and requeue it
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def sync_vm_offer(self, data):
        """
        Synchronize a VM offer with the local database.
        
        Args:
            data (dict): The VM offer data
        """
        db = SessionLocal()
        try:
            # Check if the VM offer already exists
            vm_offer = db.query(VMOffer).filter(VMOffer.id == data.get('id')).first()
            
            if vm_offer:
                # Update existing VM offer
                vm_offer.name = data.get('name')
                vm_offer.description = data.get('description')
                vm_offer.cpu_count = data.get('cpu_count')
                vm_offer.memory_size_mib = data.get('memory_size_mib')
                vm_offer.disk_size_gb = data.get('disk_size_gb')
                vm_offer.price_per_hour = data.get('price_per_hour')
                vm_offer.is_active = data.get('is_active')
                logger.info(f"Updated VM offer: {vm_offer.id}")
            else:
                # Create new VM offer
                vm_offer = VMOffer(
                    id=data.get('id'),
                    name=data.get('name'),
                    description=data.get('description'),
                    cpu_count=data.get('cpu_count'),
                    memory_size_mib=data.get('memory_size_mib'),
                    disk_size_gb=data.get('disk_size_gb'),
                    price_per_hour=data.get('price_per_hour'),
                    is_active=data.get('is_active')
                )
                db.add(vm_offer)
                logger.info(f"Created VM offer: {vm_offer.id}")
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing VM offer: {str(e)}")
        finally:
            db.close()
    
    def delete_vm_offer(self, offer_id):
        """
        Delete a VM offer from the local database.
        
        Args:
            offer_id (int): The VM offer ID
        """
        db = SessionLocal()
        try:
            # Find the VM offer
            vm_offer = db.query(VMOffer).filter(VMOffer.id == offer_id).first()
            
            if vm_offer:
                # Delete the VM offer
                db.delete(vm_offer)
                db.commit()
                logger.info(f"Deleted VM offer: {offer_id}")
            else:
                logger.warning(f"VM offer not found for deletion: {offer_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting VM offer: {str(e)}")
        finally:
            db.close()
    
    def start_consuming(self):
        """Start consuming messages from the queue."""
        if self.is_running:
            logger.warning("Consumer is already running")
            return
        
        if not self.connection or self.connection.is_closed:
            if not self.connect():
                logger.error("Failed to connect to RabbitMQ, cannot start consuming")
                return
        
        # Set up basic consume
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.process_message
        )
        
        logger.info(f"Starting to consume messages from queue: {self.queue_name}")
        self.is_running = True
        
        # Start consuming in a separate thread
        self.consumer_thread = threading.Thread(target=self._consume_thread)
        self.consumer_thread.daemon = True
        self.consumer_thread.start()
    
    def _consume_thread(self):
        """Thread function for consuming messages."""
        try:
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error in consumer thread: {str(e)}")
            self.is_running = False
    
    def stop_consuming(self):
        """Stop consuming messages."""
        if not self.is_running:
            logger.warning("Consumer is not running")
            return
        
        try:
            self.channel.stop_consuming()
            self.is_running = False
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping consumer: {str(e)}")

# Create a singleton instance
rabbitmq_consumer = RabbitMQConsumer()

# # For testing
# if __name__ == "__main__":
#     # Create tables if they don't exist
#     Base.metadata.create_all(bind=engine)
    
#     # Start consuming
#     rabbitmq_consumer.start_consuming()
    
#     # Keep the main thread alive
#     try:
#         while True:
#             import time
#             time.sleep(1)
#     except KeyboardInterrupt:
#         rabbitmq_consumer.stop_consuming()
#         print("Consumer stopped")
