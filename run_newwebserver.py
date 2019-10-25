#!/usr/bin/python3
import time
import sys
import boto3
import logging
import requests
import subprocess
import logging
from progress.bar import IncrementalBar
from botocore.exceptions import  ClientError
from datetime import datetime,timedelta

logging.basicConfig(filename='info.log', filemode='w', level=logging.INFO, format='%(asctime)s %(message)s')

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
        logging.error(e)

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
        print(f'ERROR: {bucket_name} already exists')
        logging.error(f'{bucket_name} already exists')

#Delete bucket + contents
# def del_bucket_contents(bucket):
#     for key in bucket.objects.all():
#         try:
#             response = key.delete()
#             print(response)
#         except Exception as e:
#             print(e)
#             logging.error(e)

#------------------Pulling and Pulling of image from url to bucket------------------#
def pull_image(url,filename):
    try:
        response = requests.get(url, filename)
        output = open(filename,"wb")
        output.write(response.content)
        output.close()
    except Exception as e:
        print(e)
        logging.error(e)

def push_image(filename,bucket):
    try:
        s3.Object(bucket,filename).put(Body=open(filename,'rb'),ACL='public-read')
    except Exception as e:
        print(e)
        logging.error(e)

#Lab Code used for metrics (Ref)
def metricForCloudwatch(instanceId,metricName):
    metricInfo = cloudwatch.metrics.filter(
        Namespace='AWS/EC2',
        MetricName= metricName,
        Dimensions=[{'Name':'InstanceId', 'Value': instanceId}])

    for metric in metricInfo:
        response = metric.get_statistics(StartTime=datetime.now() - timedelta(minutes=65),     # 5 minutes ago
                                            EndTime=datetime.now() - timedelta(minutes=60),       # now
                                            Period=300,                                           # 5 minute intervals
                                            Statistics=['Average'])
        print (" >> Average Result of "+ metricName+" (%):", response['Datapoints'][0]['Average'])
        logging.debug(response)   # for debugging only

def main():

    #Initiate logging
    logging.info('Started Logging')
    #------------------Assigning values before running------------------#
    image_id ='ami-0ce71448843cb18a1'
    inst_type = 't2.micro'
    key = 'njordan-key'
    imageUrl = 'http://devops.witdemo.net/image.jpg'
    bucket ='njordan-oct19-1908'
    filename = 'urlImage.jpg'



    #------------------LAUNCH INSTANCE------------------#
    instance = create_instance(image_id,inst_type,key)
    logging.info('Instance has been created')
    print('  >> Instance has been created')

    print("  >> Waiting for instance state = running")
    with IncrementalBar('  >> Launching',max=100) as bar:
        for i in range(100):
            time.sleep(1)
            bar.next()
    logging.info(instance.state)
    print(instance.state)
    print()


    #------------------CREATING BUCKET------------------#
    logging.info('Creating Bucket:')
    print(f'  >> Creating Bucket: {bucket}')
    time.sleep(5)
    create_bucket(bucket)


    #------------------Pulling Image from the url provided------------------#
    logging.info("Pulling image from url")
    time.sleep(5)
    print()
    print('  >> Pulling image from url')
    pull_image(imageUrl, filename)

    print()
    print('  >> Image downloaded')
    print()


    #------------------Pushing image to bucket------------------#
    logging.info("Pushing Image to bucket")
    time.sleep(5)
    print('  >> Image is being pushed to the bucket')
    push_image(filename,bucket)

    print()
    print(f'  >> Image is now in {bucket}' )
    print()


    #------------------Ssh remote command to retrieve------------------#
    logging.info("Beginning ssh process")

    print('  >> SSHing into ec2-user@'+ instance.public_ip_address )
    print("  >> Please wait while we try to ssh into the instance")
    with IncrementalBar('  >> SSHing into Instance',max=30) as bar:
        for i in range(30):
            time.sleep(1)
            bar.next()
    instance.reload()
    print()

    #linebreak
    nextLine = "ssh -i njordan-key.pem ec2-user@"+instance.public_ip_address+ """ 'echo "</br>"  >> /var/www/html/index.html'"""

    #Adding metadata to index
    logging.info("Adding metadata to index")

    ipLine = "ssh  -o StrictHostKeyChecking=no -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'echo 'Private IP:' >> /var/www/html/index.html'"
    ipmetadata = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'curl http://169.254.169.254/latest/meta-data/local-ipv4 >> /var/www/html/index.html'"


    print("  >> Instance Meta Data is being loaded to index.html")
    subprocess.run(ipLine,shell=True)
    subprocess.run(ipmetadata,shell=True)
    subprocess.run(nextLine, shell=True)
    print()

    #Security Group Meta-data
    secGroupLine = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'echo 'Security Groups:' >> /var/www/html/index.html'"
    secGroupMetadata = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'curl http://169.254.169.254/latest/meta-data/security-groups >> /var/www/html/index.html'"
    subprocess.run(secGroupLine,shell=True)
    subprocess.run(secGroupMetadata,shell=True)
    subprocess.run(nextLine, shell=True)
    print()

    #Hostname Meta-data
    hostnameLine = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'echo 'Hostname:' >> /var/www/html/index.html'"
    hostnameMetadata = "ssh -i  njordan-key.pem ec2-user@" + instance.public_ip_address  + " 'curl http://169.254.169.254/latest/meta-data/hostname >> /var/www/html/index.html'"
    subprocess.run(hostnameLine,shell=True)
    subprocess.run(hostnameMetadata,shell=True)
    subprocess.run(nextLine, shell=True)
    print()


    #Loading Image onto the page
    logging.info("Attempting to display image")

    imageInPage = "ssh -i njordan-key.pem ec2-user@" + instance.public_ip_address + f""" echo '\<img src="https://{bucket}.s3-eu-west-1.amazonaws.com/{filename} alt="Image for Assignment" \>"  >> /var/www/html/index.html' """
    print("  >> Loading Image")
    subprocess.run(imageInPage,shell=True)
    print("  >> Success: Image Loaded")
    print()

    #---------------------Cloudwatch & Metrics------------------#
    logging.info("Cloudwatch Metrics")
    print()
    print("  >> Cloudwatch Metrics:")
    metricForCloudwatch(instance.id,"CPUUtilization")
    metricForCloudwatch(instance.id,"NetworkIn")
    metricForCloudwatch(instance.id,"NetworkOut")

    #Ending Logging
    logging.info("Script finished successfully")
    logging.info('Finished Logging')
main()

logging.shutdown

