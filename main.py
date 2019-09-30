# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

from flask import Flask
from flask import request
from botocore.exceptions import ClientError


import datetime

app = Flask(__name__)
import boto3
import json

bucket='emp-face-recognition-demo'
regionName = 'us-east-1'
tableName = 'employee_collection'

rekognition = boto3.client('rekognition', region_name=regionName)
dynamodb = boto3.client('dynamodb', region_name=regionName)
s3 = boto3.client('s3')


def create_collection(collection_id):

    client=boto3.client('rekognition')

    #Create a collection
    print('Creating collection:' + collection_id)
    response=client.create_collection(CollectionId=collection_id)
    print('Collection ARN: ' + response['CollectionArn'])
    print('Status code: ' + str(response['StatusCode']))
    print('Done...')

def list_collections():

    max_results=2
    
    collection_ids=[]

    #Display all the collections
    #print('Displaying collections...')
    response=rekognition.list_collections(MaxResults=max_results)
    collection_count=0
    done=False
    
    while done==False:
        collections=response['CollectionIds']
        collection_ids += collections
        for collection in collections:
            print (collection)
            collection_count+=1
        if 'NextToken' in response:
            nextToken=response['NextToken']
            response=rekognition.list_collections(NextToken=nextToken,MaxResults=max_results)
            
        else:
            done=True

    return collection_ids 


@app.route('/')
def hello():
    return "Welcome to Face Recognition!"

@app.route('/face-recognition/registration',methods = ['POST'])
def register():
    req_data = request.get_json(force=True)
    s3BucketUrl = req_data['s3BucketUrl']
    userKey = req_data['userKey']
    #emp_name = req_data['emp_name']
    fileName = s3BucketUrl.split('/')[-1]
    print(fileName)
    #print(faceid)
    
    collection_id = str(userKey)
    
    collection_ids = list_collections()
    print(collection_ids)
    
    if collection_id not in collection_ids:
        create_collection(collection_id)
    try:
        response = rekognition.index_faces(
                                    CollectionId=collection_id,
                                    Image={
                                            "S3Object": {"Bucket": bucket,"Name": fileName} 
                                          }, 
                                    ExternalImageId= userKey,
                                    DetectionAttributes = ['ALL']
                                    )
        
        # Commit faceId and full name emp_code to DynamoDB
            
        responseDict = {}
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            faceId = response['FaceRecords'][0]['Face']['FaceId']
    
            #ret = s3.head_object(Bucket=bucket,Key=fileName)
            #ret['Metadata']['fullname']
            #personFullName = emp_name
            #print(personFullName)
            
            createdOn = str(datetime.datetime.now())
    
            response = dynamodb.put_item(
            TableName=tableName,
            Item={
                'RekognitionId': {'S': faceId},
                #'FullName': {'S': personFullName},
                'UserKey': {'S': userKey},
                'CreationDate' : {'S' : createdOn }
                }
            )
            responseDict["success"] = True
            responseDict["otherDetails"] = {}
            responseDict["otherDetails"]["RekognitionId"] = faceId
        
        else:
            responseDict["success"] = False
            responseDict["Message"] = "Error in Registration"
            
        return json.dumps(responseDict)
    
    except Exception as e:
        print(e)
        #register()
        responseDict = {}
        responseDict["success"] = False
        responseDict["otherDetails"] = {}
        responseDict["otherDetails"]["Message"] = e.response['Error']['Message']
        return json.dumps(responseDict)
        
    

def SearchFace(fileName,userKey):

    threshold = 70
    maxFaces=1
  
    collection_id = str(userKey)
    responseDict = {}
    try:
        response=rekognition.search_faces_by_image(CollectionId=collection_id,
                                    Image={'S3Object':{'Bucket':bucket,'Name':fileName}},
                                    FaceMatchThreshold=threshold,
                                    MaxFaces=maxFaces)
    
                                    
        faceMatches=response['FaceMatches']
        
        #print(faceMatches)
        if len(faceMatches) != 0 :
            print ('Matching faces')
            
            for match in faceMatches:
                face_id = match['Face']['FaceId']
                similarity = match['Similarity']
                external_id = match['Face']['ExternalImageId']
                print ('FaceId:' + face_id)
                print ('Similarity: ' + "{:.2f}".format(similarity) + "%")
                
                
                responseDict["otherDetails"]={}
                responseDict["otherDetails"][face_id]= {}
                responseDict["otherDetails"][face_id]['Similarity']= similarity
                
                face = dynamodb.get_item(
                TableName=tableName,  
                Key={'RekognitionId': {'S': face_id}}
                )
            
                if 'Item' in face:
                    #fullname = face['Item']['FullName']['S']
                    UserKey_fromDB = face['Item']['UserKey']['S']
                    #print (fullname, employee_code)
                    #responseDict["otherDetails"][face_id]['FullName']= fullname
                    responseDict["otherDetails"][face_id]['UserKey']= UserKey_fromDB
                    
                else:
                    responseDict["otherDetails"]["Message"] = "no match found in person lookup" 
                    return responseDict
                
                if userKey == external_id :
                        print("ID verified")
                        responseDict["success"] = True
                        return responseDict
                else:
                    responseDict["success"] = False
                    responseDict["otherDetails"]["Message"] = "ID proof is not verified, Invalid ID Proof!"
                    return responseDict
                    
        else:
            responseDict["success"] = False
            responseDict["otherDetails"] = {}
            responseDict["otherDetails"]["Message"] = "ID proof is not verified, Invalid ID Proof! No match found"
            return responseDict
        
        
    except Exception as e:
        print(e)
        #print('in exception')
        #register()
        responseDict["success"] = False
        responseDict["otherDetails"] = {}
        responseDict["otherDetails"]["Message"] = "Collection is not present.Register yourself!"
        return responseDict

    

@app.route('/face-recognition/verify',methods = ['GET'])
def verify():
    req_data = request.get_json(force=True)
    s3BucketUrl = req_data['s3BucketUrl']
    userKey = req_data['userKey']
    #emp_name = req_data['emp_name']
    fileName = s3BucketUrl.split('/')[-1]
    #faceid = req_data['faceid']
    #fileName='s1.jpg'
    #'22778.JPG'
    #emp_code = '1289'
    #emp_name = 'selana'
    
    #print(filename)
    #print(faceid)
    
    matched_faces = SearchFace(fileName,userKey)
    
    print("hello")
    print(matched_faces)
    
    # check if data is in table 
    
    
    matched_faces_json = json.dumps(matched_faces)
    return matched_faces_json


def updation(fileName,userKey):
    
    collection_id = str(userKey) 
    response = rekognition.index_faces(
                                CollectionId=collection_id,
                                Image={
                                        "S3Object": {"Bucket": bucket,"Name": fileName} 
                                      }, 
                                ExternalImageId= userKey,
                                DetectionAttributes = ['ALL']
                                )
    
    # Commit faceId and full name emp_code to DynamoDB
        
    responseDict = {}
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        faceId = response['FaceRecords'][0]['Face']['FaceId']

        #ret = s3.head_object(Bucket=bucket,Key=fileName)
        #ret['Metadata']['fullname']
        #personFullName = emp_name
        #print(personFullName)
        
        createdOn = str(datetime.datetime.now())

        response = dynamodb.put_item(
        TableName=tableName,
        Item={
            'RekognitionId': {'S': faceId},
            #'FullName': {'S': personFullName},
            'UserKey': {'S': userKey},
            'CreationDate' : {'S' : createdOn }
            }
        )
        responseDict["success"] = True
        responseDict["otherDetails"] = {}
        responseDict["otherDetails"]["RekognitionId"] = faceId
    
    else:
        responseDict["success"] = False
        responseDict["Message"] = "Error in Updation"
    
    
    return responseDict
    

@app.route('/face-recognition/update',methods = ['PUT'])
def update():
    req_data = request.get_json(force=True)
    s3BucketUrl = req_data['s3BucketUrl']
    userKey = req_data['userKey']
    #emp_name = req_data['emp_name']
    fileName = s3BucketUrl.split('/')[-1]
    #faceid = req_data['faceid']
    #fileName='s1.jpg'
    #'22778.JPG'
    #emp_code = '1289'
    #emp_name = 'selana'
    
    #print(filename)
    #print(faceid)
    
    matched_faces = SearchFace(fileName,userKey)
    
    print(matched_faces)
    
    responseDict ={} 
    # check if data is in table 
    if matched_faces["success"] == True :
        responseDict = updation(fileName,userKey)
    else :
        responseDict = matched_faces
    matched_faces_json = json.dumps(responseDict)
    return matched_faces_json

'''
def list_faces_in_collection():


    maxResults=2
    faces_count=0
    tokens=True

    client=boto3.client('rekognition')
    response=client.list_faces(CollectionId=collectionId,
                               MaxResults=maxResults)

    print('Faces in collection ' + collectionId)

 
    while tokens:

        faces=response['Faces']

        for face in faces:
            print (face)
            faces_count+=1
        if 'NextToken' in response:
            nextToken=response['NextToken']
            response=client.list_faces(CollectionId=collectionId,
                                       NextToken=nextToken,MaxResults=maxResults)
        else:
            tokens=False
    return faces_count   
'''


def delete_collection(collection_id):
    print('Attempting to delete collection ' + collection_id)
  
    status_code=0
    responseDict = {}
    
    try:
        response=rekognition.delete_collection(CollectionId=collection_id)
        status_code=response['StatusCode']
        responseDict["success"] = True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print ('The collection ' + collection_id + ' was not found ')
            responseDict["success"] = False
            responseDict["message"] = 'The collection ' + collection_id + ' was not found '
        else:
            print ('Error other than Not Found occurred: ' + e.response['Error']['Message'])
            responseDict["success"] = False
            responseDict["message"] = e.response['Error']['Message']
        
        status_code=e.response['ResponseMetadata']['HTTPStatusCode']
    return(responseDict)

@app.route('/face-recognition/delete',methods = ['DELETE'])
def delete():
    req_data = request.get_json(force=True)
    #s3BucketUrl = req_data['s3BucketUrl']
    userKey = req_data['userKey']
    #emp_name = req_data['emp_name']
    #fileName = s3BucketUrl.split('/')[-1]
    
    collection_id = str(userKey) 
    
    responseDict = delete_collection(collection_id)
    
    return json.dumps(responseDict)


if __name__ == '__main__':
    app.run()