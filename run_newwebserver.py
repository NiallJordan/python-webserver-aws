#!/usr/bin/python3
import time
import sys
import boto3
import logging
import requests
import paramiko
from botocore.exceptions import  ClientError

ec2 = boto3.resource('ec2', region_name='eu-west-1')
s3 = boto3.resource('s3')

def create_instance(image_id,inst_type,key):
    instance = ec2.create_instances(
        ImageId= image_id,
        SecurityGroupIds=['sg-0bad22fa427075f60'],
        InstanceType= inst_type,
        KeyName = key,
        UserData= """
        #!/bin/bash
        sudo yum install httpd -y
        sudo systemctl enable httpd
        sudo systemctl start httpd
        """,
        MinCount=1,
        MaxCount=1
    )

    #Adding a tag to the instance
    name_tag ={'Key': 'Name', 'Value': 'Assignment Instance'}
    instance[0].create_tags(Tags= [name_tag])

    return instance[0]


def create_bucket(bucket_name):
    #Creating a bucket
    try:
        response = s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint' : 'eu-west-1'})
        print(response)
    except:
        print(f'{bucket_name} already exists')

def del_bucket_contents(bucket):
    for key in bucket.objects.all():
        try:
            response = key.delete()
            print(response)
        except Exception as e:
            print (e)

def pull_image(url,filename):
    try:
        response = requests.get(url, filename)
        output = open(filename,"wb")
        output.write(response.content)
        output.close()
    except Exception as e:
        print(e)

def push_image(filename,bucket):
    try:
        s3.Object(bucket,filename).put(Body=open(filename,'rb'))
    except Exception as e:
        print(e)

def ssh_into_instance(key, inst_ip,cmd):
    sshClient = paramiko.SSHClient()
    sshClient.load_system_host_keys()
    sshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        sshClient.connect(hostname=inst_ip, username="ec2-user",key_filename= key )
        ssh = sshClient.invoke_shell()
        stdin, stdout, stderr = sshClient.exec_command(cmd)
        sshClient.close()
    except Exception as e:
        print(e)

def main():
    #Assigning values before running
    image_id ='ami-0ce71448843cb18a1'
    inst_type = 't2.micro'
    key = 'njordan-key'
    parakey ='njordan-key.pem'
    imageUrl = 'http://devops.witdemo.net/image.jpg'
    bucket ='njordan-oct19-1908'
    filename = 'urlImage.jpg'

    #Launch of the ec2 instance
    instance = create_instance(image_id,inst_type,key)

    inst_list = []
    for instance in ec2.instances.all():
        inst_list.append(instance)

    print('Waiting for instance state = running')
    instance.reload()
    instance.wait_until_running()

    print('Instance has been created')
    inst_list[0].reload()
    for instance in ec2.instances.all():
        print (instance.id, instance.state)


    #Creating bucket
    print('Creating Bucket')
    time.sleep(5)
    create_bucket(bucket)


    #Pulling Image from the url provided
    time.sleep(5)
    print('Pulling image from url')
    pull_image(imageUrl, filename)
    print('Image downloaded')


    #Pushing image to bucket
    time.sleep(5)
    print('Image is being pushed to the bucket')
    push_image(filename,bucket)
    print(f'Image is now in {bucket}' )



    #Ssh remote command to retrieve
    time.sleep(60)
    instance.reload()
    print('SSHing into instance ')
    #CMDS to run in ssh
    setOwnerPermissionsForServer = """sudo touch var/www/html/index.html
    sudo chown ec2-user var/www/html/index.html
    sudo chmod -R o+r html
    """

    indexContent = """echo '<html>' > index.html
    echo 'Image:' >> index.html
    echo '<img src="s3://njordan-oct19-1908/urlImage.jpg">' >> index.html
    echo 'Instance Metadata' >> index.html
    curl http://169.254.169.254/latest/meta-data/local-ipv4 >> index.html
    echo '</html>'
    """

    inst_ip = instance.public_ip_address
    ssh_into_instance(key +".pem",inst_ip,setOwnerPermissionsForServer)
    print("Permissions have been set for server")
    ssh_into_instance(parakey,inst_ip,indexContent)
    print("Index content has been pushed to server")


main()

