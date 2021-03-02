import argparse
import os
import sys
import openstack 

# for VMs creation scheduling
from datetime import datetime
from threading import Timer

# REST APIs
from flask import Flask 
from flask import jsonify 
from flask import request, escape, abort 

app = Flask(__name__)


# connection to cloud 
def cloud_connect():
    # enabling logging
    openstack.enable_logging(True, path = "openstack.log")

    # Connection to OpenStack Cloud from config file cloud.yaml
    conn = openstack.connection.from_config(cloud = "openstack")

    return conn 

# list images 
def list_images(conn):
    print("List Images:")

    for image in conn.compute.images():
        print(image)
        print("\n\n")

# get images list
def get_imagesList(conn):
    images = []
    for image in conn.compute.images():
        name = image.name 

        image = {
            "name": name 
        }

        images.append(image)
    return images 

# list VMs 
def list_servers(conn):
    print("List Servers:")

    for server in conn.compute.servers():
        print(server)
        print("\n\n")

# list Flavors 
def list_flavors(conn):
    print("List Flavors:")

    for flavor in conn.compute.flavors():
        print(flavor)
        print("\n\n")

# get Flavors list 
def get_flavorsList(conn):
    flavors = []
    for flavor in conn.compute.flavors():
        name = flavor.name
        ram = flavor.ram 
        vcpus = flavor.vcpus
        disk = flavor.disk 
        
        flavor = {
            "name": name,
            "ram": ram,
            "vcpus": vcpus,
            "disk": disk
        }

        flavors.append(flavor)
    return flavors

# list Netwokrs 
def list_networks(conn):
    print("List Networks:")

    for network in conn.network.networks():
        print(network)
        print("\n\n")

# create flavors 
def create_flavors(conn):
    existing_flavors = []
    for flavor in conn.compute.flavors():
        existing_flavors.append(flavor.name)

    # create standard flavor if it not exists
    if "standard" not in existing_flavors:
        conn.create_flavor(name = "standard",
                        ram = 128,
                        vcpus = 1,
                        disk = 1)

    # create large flavor if it not exists 
    if "large" not in existing_flavors: 
        conn.create_flavor(name = "large",
                        ram = 264,
                        vcpus = 2,
                        disk = 1)

# create VMs
def create_servers(conn, IMAGE_NAME, FLAVOR_NAME, NUM_SERVERS):
    VMs_names = []
    for x in range(NUM_SERVERS):
        print("Creating Server " + str(x) + "...")
        VMs_names.append("VM" + str(x))

        image = conn.compute.find_image(IMAGE_NAME)
        flavor = conn.compute.find_flavor(FLAVOR_NAME)
        network = conn.network.find_network("internal")

        server = conn.compute.create_server(
            name = VMs_names[x], image_id = image.id, flavor_id = flavor.id,
            networks = [{"uuid": network.id}])

        server = conn.compute.wait_for_server(server)

# destroy VMs
def destroy_servers(conn, NUM_SERVERS):
    VMs_names = []
    for x in range(NUM_SERVERS):
        print("Deleting Server " + str(x) + "...")
        VMs_names.append("VM" + str(x))

        # find server to be deleted 
        server = conn.compute.find_server(VMs_names[x])

        # delete server
        conn.compute.delete_server(server.id)

# parse string date utility function
def compute_delta(peak_start_str):
    peak_start = datetime.strptime(peak_start_str, '%d/%m/%Y %H:%M:%S')
    now = datetime.today()
    delta_t = peak_start - now
    seconds = delta_t.seconds + 1
    #print("Creating new Server in " + str(seconds) + "seconds.")
    return seconds

# admin_request example structure 
admin_request = [
    {
        "peak_start": "19:00",
        "peak_stop": "20:00",
        "flavor_name": "standard",
        "image_name": "Cirros",
        "VMs_number": 1
    }
]

# flavor example structure 
flavor = [
    {
        "name": "standard",
        "ram": 128,
        "vcpus": 1,
        "disk": 1 
    }
]

#image example structure 
image = [
    {
        "name": "Cirros"
    }
]

# HTTP requests handlers 
@app.route('/v2/flavors', methods=['GET'])
def get_flavors():
    return jsonify(flavors)

@app.route('/v2/images', methods=['GET'])
def get_images():
    return jsonify(images)

admin_requests = []
@app.route('/v2/admin_requests', methods=['POST'])
def create_admin_request():
    if not request.json or not 'peak_start' in request.json or not "peak_stop" in request.json:
        abort(400)
    admin_request = {
        "peak_start": request.json["peak_start"],
        "peak_stop": request.json["peak_stop"],
        "flavor_name": request.json.get("flavor", "standard"),
        "image_name": request.json.get("image", "Cirros"),
        "VMs_number": request.json.get("VMs_number", 1)
    }
    admin_requests.append(admin_request)
    print(admin_request)

    conn = cloud_connect()

    VMs = admin_request["VMs_number"]
    image_name = admin_request["image_name"]
    flavor_name = admin_request["flavor_name"]
    peak_start_str = admin_request["peak_start"]
    peak_stop_str = admin_request["peak_stop"]

    # parsing peak_start string inserted by admin 
    secsToCreate = compute_delta(peak_start_str)

    #schedule call to create_servers(...) as admin requested 
    createTimer = Timer(secsToCreate, lambda: create_servers(conn, image_name, flavor_name, VMs))
    createTimer.start()

    # parsing peak_stop string inserted by admin
    secsToDestroy = compute_delta(peak_stop_str)

    #schedule call to destory_servers(...) as admin requested
    stopTimer = Timer(secsToDestroy, lambda: destroy_servers(conn, VMs))
    stopTimer.start()
   
    return jsonify({'admin_request': admin_request}), 201

if __name__ == '__main__':
    
    # Connection to OpenStack Cloud from config file cloud.yaml
    conn = cloud_connect()

    # creating 2 flavors
    create_flavors(conn)

    # retrieving available flavors 
    flavors = get_flavorsList(conn)

    # retrieving available images 
    images = get_imagesList(conn)
    
    app.run(host='0.0.0.0', port=8080)