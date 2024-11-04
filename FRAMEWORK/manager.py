import confluent_kafka
from confluent_kafka.admin import (AdminClient, NewTopic, ConfigResource)
from confluent_kafka import Consumer
from confluent_kafka import Producer
from time import sleep
from threading import Thread
import signal
import sys

#------------------------Configuration---------------------------------------

# Admin configuration
config_admin = {'bootstrap.servers': 'kafka:9092'}

# Consumer configuration
config_Consumer = {'bootstrap.servers': 'kafka:9092',
          'auto.offset.reset': 'earliest',
          'group.id': 'manager',
          'enable.auto.commit': True}

# Producer configuration
config_Producer = {'bootstrap.servers': 'kafka:9092','batch.size': 1}


#------------------------Functions-------------------------------------------

# return True if topic exists and False if not
def topic_exists(admin, topic):
    metadata = admin.list_topics()
    for t in iter(metadata.topics.values()):
        if t.topic == topic:
            return True
    return False

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
        
def send_command(client_ID, sensor_ID, action): 
    # Create a new producer and send data
    producer = Producer(config_Producer)
    message = f"{sensor_ID},{action}"
    
    producer.produce(client_ID, message)
    producer.flush()
    print("Command sent to", client_ID, "with message:", message)

# Send parameter mapping to the application logic
def send_mapping(service_ID, parameter1, parameter2, operation): 
    # Create a new producer and send data
    producer = Producer(config_Producer)
    message = f"{parameter1},{parameter2},{operation}"
    
    producer.produce(service_ID, message)
    producer.flush()
    print("Command sent to", service_ID, "with message:", message)


def init_manager():
    # Standard topics for the network
    topic_register = 'REGISTER'
    topic_ack = 'ACKNOWLEDGE'

    # Create Admin client and two standard topics
    admin = AdminClient(config_admin)
    create_topic(admin, topic_register)
    create_topic(admin, topic_ack)
    print("Topics 'REGISTER' and 'ACKNOWLEDGE' created")
    
    # Create a Consumer for topic REGISTER
    consumer = Consumer(config_Consumer)
    # Create a Producer for topic ACKNOWLEDGE
    producer = Producer(config_Producer)
    
    # Subscribe to topic 'REGISTER'
    consumer.subscribe([topic_register])
    print("Listening for new clients")
    
    name = 0
    # Poll for data from topic 'REGISTER'
    while True:
            msg = consumer.poll(1.0)  # Timeout of 1 second
            if msg is None:
                continue
            elif msg.error():
                print("Consumer error: {}".format(msg.error()))
            else:
                data = msg.value().decode('utf-8')
                print("Request from new client:", data)
                write_data(data)

                # Create unique name for the new client
                name = name + 1
                client_name = "CLIENT_" + str(name)
                sleep(1) # Since config is 'auto.offset.reset': 'latest', delay publishing to ACKNOWLEDGE
                
                # Send unique name to the client
                producer.produce(topic_ack, client_name)
                producer.flush()
                print('Unique ID created', client_name)
            

            consumer.commit(msg)  # Commit offsets

def read_data():
  data_points = []  # Create an empty list to store data points
  try:
    with open("/usr/src/app/shared/data.txt", "r") as f:
      for line in f:
        # Read each line and append it to the list
        data_points.append(line.strip())  # Remove trailing newline character
  except FileNotFoundError:
    return None

  return data_points

def clear_data():
  try:
    with open("/usr/src/app/shared/data.txt", 'w') as f:
      # Write an empty string to clear the file content
      f.write("")
    return True
  except FileNotFoundError:
    print(f"File not found:")
    return False
  except Exception as e:
    print(f"An error occurred: {e}")
    return False

# Write neo4j ip address to a common file  
def write_data(data):
      if data not in neo4j_ip:
         neo4j_ip.append(data) # Add the ip address to the list
         with open("/usr/src/app/shared/neo4j_ip.txt", "w") as f:
          # Write the parameters to the file
          f.write(f"{data}\n")

def clear_neo4jip():
  try:
    with open("/usr/src/app/shared/neo4j_ip.txt", 'w') as f:
      # Write an empty string to clear the file content
      f.write("")
      print("Neo4j_ip.txt cleared")
    return True
  except FileNotFoundError:
    print(f"File not found:")
    return False
  except Exception as e:
    print(f"An error occurred: {e}")
    return False
  

            
#-------------------------------------------MAIN----------------------------------------------

sleep(10)
print("Manager is starting")
neo4j_ip = [] # List to store neo4j ip address of digital twins
clear_neo4jip()

if __name__ == '__main__':
    # Initilaize the manager in a separate thread
    thread = Thread(target=init_manager)
    thread.start()

    # Send commands to clients based on input from web interface.
    while True:
        # Read file
        command = read_data()
        if command:
            # Process the read data (lines)
            print(f"Received data: {command}")
            source_ID = command[0]
            destination_ID = command[1]
            param_S = command[2]
            param_D = command[3]
            service_ID = command[4]
            operation = command[5]

            # Send mapping to application logic
            send_mapping(service_ID, param_S, param_D, operation)

            # Send message to source
            send_command(source_ID, param_S, 'produce')
            sleep(5)
            # Send message to destination
            send_command(destination_ID, param_S, 'consume')

            # Clear the file containing the command to precent re-procesing
            clear_data()
        else:
            sleep(5)
            continue
