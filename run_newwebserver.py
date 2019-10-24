#!/usr/bin/python3
import time
import sys
import boto3
import logging
import requests
import subprocess
import logging
from botocore.exceptions import  ClientError
from datetime import datetime,timedelta

logging.basicConfig(level=logging.INFO)
ec2 = boto3.resource('ec2', region_name='eu-west-1')
s3 = boto3.resource('s3')
cloudwatch = boto3.resource('cloudwatch',region_name='eu-west-1')

#------------------Create instance method------------------#
def create_instance(image_id,inst_type,key):
    try:
        instance = ec2.create_instances(
            ImageId= image_id,
            SecurityGroupIds=['sg-0bad22fa427075f60'],
            InstanceType= inst_type,
            KeyName = key,
            UserData= """#!/bin/bash
                         yum update -y
                         yum install httpd -y
                         systemctl enable httpd
                         systemctl start httpd
                         sudo touch /var/www/html/index.html
                         sudo chown -R ec2-user /var/www/html/index.html
            """,
            MinCount=1,
            MaxCount=1,
            Monitoring={
            'Enabled': True
            }
        )
    except Exception as e:
        print(e)

    #Adding a tag to the instance
    name_tag ={'Key': 'Name', 'Value': 'Assignment Instance'}
    instance[0].create_tags(Tags= [name_tag])
    return instance[0]

#------------------Create & Delete Bucket Method------------------#s
def create_bucket(bucket_name):
    try:
        response = s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint' : 'eu-west-1'})
        print(response)
    except:
        logging.error(f'{bucket_name} already exists')

def del_bucket_contents(bucket):
    for key in bucket.objects.all():
        try:
            response = key.delete()
            print(response)
        except Exception as e:
            print (e)

#------------------Pulling and Pulling of image from url to bucket------------------#
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

def metricsForCloudwatch(instanceId):
    metric_iterator = cloudwatch.metrics.filter(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[{'Name':'InstanceId', 'Value': instanceId}])

    for metric in metric_iterator:
        response = metric.get_statistics(StartTime=datetime.now() - timedelta(minutes=65),     # 5 minutes ago
                                            EndTime=datetime.now() - timedelta(minutes=60),       # now
                                            Period=300,                                           # 5 minute intervals
                                            Statistics=['Average'])
        print ("Average CPU utilisation:", response['Datapoints'][0]['Average'])
        print (response)   # for debugging only




def main():
    #------------------Assigning values before running------------------#
    image_id ='ami-0ce71448843cb18a1'
    inst_type = 't2.micro'
    key = 'njordan-key'
    imageUrl = 'http://devops.witdemo.net/image.jpg'
    bucket ='njordan-oct19-1908'
    filename = 'urlImage.jpg'



    #------------------LAUNCH INSTANCE------------------#
    instance = create_instance(image_id,inst_type,key)
    logging.info('>Instance has been created')

    logging.info("Waiting for instance state = running")
    instance.wait_until_running()
    print (instance.id, instance.state)


    #------------------CREATING BUCKET------------------#
    logging.info('>Creating Bucket:')
    time.sleep(5)
    create_bucket(bucket)


    #------------------Pulling Image from the url provided------------------#
    time.sleep(5)
    print()
    logging.info('>Pulling image from url')
    pull_image(imageUrl, filename)

    print()
    logging.info('>Image downloaded')
    print()


    #------------------Pushing image to bucket------------------#
    time.sleep(5)
    logging.info('>Image is being pushed to the bucket')
    push_image(filename,bucket)

    print()
    logging.info(f'>Image is now in {bucket}' )
    print()


    #------------------Ssh remote command to retrieve------------------#
    logging.info('>SSHing into ec2-user@'+ instance.public_ip_address )
    logging.info("Please wait while we try to ssh into the instance")
    time.sleep(60)
    instance.reload()
    print()
    copy = "scp -i njordan-key.pem index.html ec2-user@"+instance.public_ip_address +":."
    scopy = "ssh -o StrictHostKeyChecking=no -i njordan-key.pem ec2-user@"+instance.public_ip_address + " 'sudo cp index.html /var/www/html/index.html' "
    line1 = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'echo 'Instance Meta Data' >> /var/www/html/index.html'"
    metadata = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'curl http://169.254.169.254/latest/meta-data/local-ipv4 >> /var/www/html/index.html '"

    logging.info(">Copying file from local machine to the EC2 instance")
    subprocess.run(copy,shell=True)
    logging.info(">Success: File Copied")

    logging.info(">'index.html' is being copied to the /var/www/html folder on AWS")
    subprocess.run(scopy,shell=True)
    logging.info(">Success: File Copied")

    logging.info(">Instance Meta Data is being loaded to index.html")
    subprocess.run(line1,shell=True)
    subprocess.run(metadata,shell=True)

    #---------------------Cloudwatch & Metrics------------------#
    print()
    logging.info(">Cloudwatch Metrics:")
    metricsForCloudwatch(instance.id)

main()

logging.shutdown

