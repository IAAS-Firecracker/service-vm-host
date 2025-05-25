#!/usr/bin/env python3
import os
import sys
import json
import logging
import threading
import pika
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime

# Import the SystemImage model
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.model_user import UserEntity
from database import Base,SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class UserConsumer:
    """
    A utility class to handle RabbitMQ connections and consuming messages
    for users in the service-vm-host application.
    """
    
    def __init__(self):
        """Initialize the RabbitMQ connection and channel."""
        self.connection = None
        self.channel = None
        self.exchange_name = os.getenv('SERVICE_USER_EXCHANGE', 'user-exchange')
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
            
            logger.info(f"Received {action} event for System Image: {data.get('id')}")
            
            # Process based on action
            if action == 'create' or action == 'update':
                self.sync_user(data)
            elif action == 'delete':
                self.delete_user(data.get('id'))
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Reject the message and requeue it
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def sync_user(self, data):
        """
        Synchronize a user with the local database.
        
        Args:
            data (dict): The user data
        """
        db = SessionLocal()
        try:
            # Check if the user already exists
            user = db.query(UserEntity).filter(UserEntity.id == data.get('id')).first()
            
            if user:
                # Update existing user
                user.name = data.get('name')
                user.email = data.get('email')
                user.role = data.get('role')
                user.token = data.get('token')
                logger.info(f"Updated User: {user.id}")
            else:
                # Create new user
                user = UserEntity(
                    id=data.get('id'),
                    name=data.get('name'),
                    email=data.get('email'),
                    role=data.get('role'),
                    token=data.get('token')
                )
                db.add(user)
                logger.info(f"Created User: {user.id}")
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing User: {str(e)}")
        finally:
            db.close()
    
    def delete_user(self, user_id):
        """
        Delete a user from the local database.
        
        Args:
            user_id (int): The user ID
        """
        db = SessionLocal()
        try:
            # Find the user
            user = db.query(UserEntity).filter(UserEntity.id == user_id).first()
            
            if user:
                # Delete the user
                db.delete(user)
                db.commit()
                logger.info(f"Deleted User: {user_id}")
            else:
                logger.warning(f"User not found for deletion: {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting User: {str(e)}")
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
user_consumer = UserConsumer()