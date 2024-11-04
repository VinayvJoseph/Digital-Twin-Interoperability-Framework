import confluent_kafka
import time
import datetime
import redis
from confluent_kafka import Producer
from time import sleep
from threading import Thread
from confluent_kafka import Consumer
from confluent_kafka.admin import (AdminClient, NewTopic, ConfigResource)
from neo4j import GraphDatabase

CLIENT_ID_LOCAL = 'Physical' # Synonymous with K.G
CLIENT_ID = ''


#--------------------------------Configuration---------------------------------------

# Central server configuration
ip_broker = '131.155.222.254' # ip address of your kafka broker
port_broker = '29093'
ip_neo4j = '131.155.222.254' # ip address of youe neo4j server
port_neo4j = '7687'

config_broker = ip_broker + ':' + port_broker

# Admin configuration
config_admin = {'bootstrap.servers': config_broker}

# Producer configuration
config_Producer = {'bootstrap.servers': config_broker, 'batch.size': 1}

# Consumer configuration for ACKNOWLEDGE
# Should have unique consumer group ID - solved by unsubscribing
config_Consumer_ack = {'bootstrap.servers': config_broker,
          'auto.offset.reset': 'earliest',
          'group.id': 'client_ack'}

# Consumer configuration for COMMANDS
config_Consumer_command = {'bootstrap.servers': config_broker,
          'auto.offset.reset': 'earliest',
          'group.id': 'client_command',
          'enable.auto.commit': True}

# Consumer configuration for DATA
# Should have unique consumer group ID because different consumers subsribe to
# the same topic - solved by assigning CLIENT_ID as group_ID.
config_Consumer_message = {'bootstrap.servers': config_broker,
          'auto.offset.reset': 'latest',
          'group.id': 'default',
          'enable.auto.commit': True}

# Redis Configuration
redis_host = 'localhost'
redis_port = 6379

# Neo4j Configuration
config_neo4j = 'bolt://' + ip_neo4j + ':' + port_neo4j
URI = config_neo4j
AUTH = ("neo4j", "digitaltwin")
#URI = "bolt://131.155.223.22:7687"

#------------------------------------Function---------------------------------------

def register(): # Register the client
    global CLIENT_ID
    topic_register = 'REGISTER'
    topic_ack = 'ACKNOWLEDGE'

    # Create producer for topic 'REGISTER'
    producer = Producer(config_Producer)
    producer.produce(topic_register, ip_neo4j) # Send neo4j_ip to manager
    producer.poll(0)
    print("Requested to join the network")


    # Create a Consumer for topic 'ACKNOWLEDGE'
    consumer = Consumer(config_Consumer_ack)
    # Subscribe to topic 'ACKNOWLEDGE'
    consumer.subscribe([topic_ack])
    print("Awaiting confirmation...")

    while True:
            msg = consumer.poll(1.0)  # Timeout of 1 second
            if msg is None:
                continue
            elif msg.error():
                print("Consumer error: {}".format(msg.error()))
            else:
                data = msg.value().decode('utf-8')
                consumer.commit(msg)
                CLIENT_ID = data # Set client ID
                print("Client registered with ID:", CLIENT_ID)

                # Update K.G with Client_ID
                records, summary, keys = driver.execute_query(
                "MATCH (p:Client {local_id:$local_id}) SET p.global_id = $ids",
                    local_id = CLIENT_ID_LOCAL, ids = CLIENT_ID,
                    database_="neo4j",
                )
                driver.close()
                print("Knowledge graph updated with client_ID")

                # Create management topic
                admin = AdminClient(config_admin)
                create_topic(admin, CLIENT_ID)

                # Unsubscribe to avoid hassle of unique group ID
                consumer.unsubscribe()
                break

    print("--------------------REGISTRATION COMPLETE------------------")


def create_Producer(sensor_ID): # Create a new producer to send payload data
    producer = Producer(config_Producer)

    # Call the function 'poll_Producer'in a separate thread
    thread = Thread(target=poll_Producer, args=(producer,sensor_ID,))
    print("Beginning to send data to topic:", sensor_ID)
    thread.start()

def poll_Producer(producer, sensor_ID,): # Send data to kafka continuosly in a new thread
    prev = ""
    topic = sensor_ID

    while True:
        # Retrieve latest item from redis
        last_item = redis_client.lindex(sensor_ID, -1)
        if last_item is None:
            sleep(1)
            continue
        last_item_string = last_item.decode('utf-8')

        # Send only recent and updated data to kafka broker
        if prev != last_item_string:
            producer.produce(topic, last_item_string)
            producer.poll(0)  # Flush messages without waiting
            print('Message Sent by', sensor_ID, ":", last_item_string)
            prev = last_item_string

    sleep(1)

def create_Consumer(sensor_ID): # Create a new consumer to receive payload data
    global CLIENT_ID
    global config_Consumer_message

    # Update consumer settings for a unique group ID
    config_Consumer_message['group.id'] = CLIENT_ID
    print(config_Consumer_message['group.id'])

    consumer = Consumer(config_Consumer_message)
    # Subscribe to a topic
    topic = sensor_ID
    consumer.subscribe([sensor_ID])
    print("Successfully subscribed to topic:", sensor_ID)

    # Call the function in a separate thread
    thread = Thread(target=poll_Consumer, args=(consumer,sensor_ID,))
    thread.start()


def poll_Consumer(consumer, sensor_ID,): # Receive data from kafka continuosly in a new thread
    # Poll for data from topic
    while True:
            msg = consumer.poll(1.0)  # Timeout of 1 second
            if msg is None:
                continue
            elif msg.error():
                print("Consumer error: {}".format(msg.error()))
            else:
                sensor_data = msg.value().decode('utf-8')
                redis_upload(sensor_ID, sensor_data)
                print("Received data", sensor_data)

            consumer.commit(msg)  # Commit offsets

def redis_upload(sensor_ID, data):
    # Uploading sensor data to redis server
    redis_client.rpush(sensor_ID, data)
    # Maintain list of length 1
    if redis_client.llen(sensor_ID) > 1:
        redis_client.lpop(sensor_ID)

# create new topic and return results dictionary
def create_topic(admin, topic):
    # Create topic if it doesn't exist
    if not topic_exists(admin, topic):
        new_topic = NewTopic(topic, num_partitions=1, replication_factor=1)
        result_dict = admin.create_topics([new_topic])
        for topic, future in result_dict.items():
            try:
                future.result()  # The result itself is None
                print("Topic {} created".format(topic))
            except Exception as e:
                print("Failed to create topic {}: {}".format(topic, e))
    else:
        print("Topic already exists")

# return True if topic exists and False if not
def topic_exists(admin, topic):
    metadata = admin.list_topics()
    for t in iter(metadata.topics.values()):
        if t.topic == topic:
            return True
    return False


#------------------------------------MAIN------------------------------------------------

# Connect to Redis server
redis_client = redis.Redis(host=redis_host, port=redis_port)
print("Connected to REDIS server with port", redis_port)

# Verify connectivity to Neo4j Database
with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()

if __name__ == '__main__':

    # Register the client
    register()

    # Create management topic
    admin = AdminClient(config_admin)

    # Create a Consumer for management messages
    consumer_command = Consumer(config_Consumer_command)
    # Subscribe to topic 'CLIENT_ID'
    consumer_command.subscribe([CLIENT_ID])
    print("Listening for comands...")

    while True:
            msg = consumer_command.poll(1.0)  # Timeout of 1 second
            if msg is None:
                continue
            elif msg.error():
                print("Consumer error: {}".format(msg.error()))
            else:
                command = msg.value().decode('utf-8')
                print("Received command:", command)

                # Split the message on the comma (",") delimiter
                sensor_ID, action = command.split(",")
                if action == 'produce':
                    # Verify if topic already exists to prevent duplicate data
                    if not topic_exists(admin, sensor_ID):
                        create_Producer(sensor_ID)
                    else:
                        print("Topic already exists, you can subscribe")
                elif action == 'consume':
                    create_Consumer(sensor_ID)
                else:
                    print("Unknown command")

            consumer_command.commit(msg)  # Commit offsets
