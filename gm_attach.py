from __future__ import print_function
import base64
from apiclient import errors
from io import BytesIO
from time import sleep

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/drive']

"""
Features to implement:
    1. Select which email of the same title to download from
    2. Avoid logos, button elements, etc.
    3. Optimize to be faster and more time-efficient
    4. Display the entire PATH of the folders with the same name, till the root directory
    5. Option to create a folder and where to set it
    6. Implement a nextPageToken so every folder can be reviewed, instead of a max of 1000

"""

def SearchMessage(service, user_id, search_string):
    try:
        # Initiate the list for returning
        list_ids = []

        # Get the id of all messages that are in the search string
        search_ids = service.users().messages().list(userId=user_id, q=search_string).execute()
        
        # If there were no results, print warning and return empty string
        try:
            ids = search_ids['messages']

        except KeyError:
            print("WARNING: the search queried returned 0 results")
            print("returning an empty string")
            return ""

        if len(ids)>1:
            for msg_id in ids:
                list_ids.append(msg_id['id'])
            return list_ids
        else:
            list_ids.append(ids[0]['id'])
            return list_ids
        
    except errors.HttpError as error:
        print(f"An error occured: {error}")


def GetFiles(service, user_id, msg_id):
    try:
        # Save message using message ID found earlier
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        parts, files = [message['payload']], []
        #print(parts[0]['body'])

        # Find 'filename' section of message and return necessary file data
        while parts:
            part = parts.pop()

            if part.get('parts'):
                parts.extend(part['parts'])
            if part.get('filename'):
                
                if 'data' in part['body']:
                    file_data = base64.urlsafe_b64decode(part['body']['data'].encode('UTF-8'))
                elif 'attachmentId' in part['body']:
                    attachment = service.users().messages().attachments().get(
                        userId=user_id, messageId=message['id'], id=part['body']['attachmentId']
                    ).execute()
                    file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                else:
                    file_data = None
                if file_data:
                    files.append((part['filename'], BytesIO(file_data), part['mimeType']))
        return files

                    
    except errors.HttpError as error:
        print(f"An error occurred: {error}")


def main():

    creds = None
    
    # token.json stores a user's login access as a token and is created during first run of authorization
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        user_id = "me"
        intFlag = True
        
        # Call the Gmail and Drive API
        gm_service = build('gmail', 'v1', credentials=creds)
        gd_service = build('drive', 'v3', credentials=creds)

        # Find all email matches with the user-defined title
        search_string = input("Gmail Title with Attachments: ")
        folder = input("Folder Name: ")
        
        childIds = gd_service.files().list(q=f"mimeType='application/vnd.google-apps.folder' and name= '{folder}'",spaces= 'drive', fields="files(id, name, parents)", pageSize= 1000).execute()['files']
        if len(childIds) > 1:
            while (intFlag):
                print(f"\nMore than one folder is called \"{childIds[0]['name']}\", select the correct folder location (Please enter an integer)? ")
                for index, option in enumerate(childIds):
                    parentId = gd_service.files().get(fileId=option['parents'][0]).execute()
                    print(f"{index+1}. /{parentId['name']}/{option['name']}")
                try:
                    selection = int(input('\n')) - 1
                    folder_id = childIds[selection]['id']
                except:
                    print("\n[That was not an integer, please try again]\n")
                    sleep(.5)
                    pass
                print('\n')
                intFlag = False
        else:
            folder_id = childIds[0]['id']


        
        list_ids = SearchMessage(gm_service, user_id, search_string)
        
        # Gather file data and upload it to the user-defined Google Drive folder
        for msg_id in list_ids:
            files = GetFiles(gm_service, user_id, msg_id)
            for file in files:
                file_name, file_data, mime_type = file[0], file[1], file[2]
                file_metadata = {
                    "name": file_name,
                    "parents": [folder_id]
                }
                media = MediaIoBaseUpload(file_data, mimetype=mime_type, chunksize= 1024 * 1024, resumable=True)
                file = gd_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                #print(file)


    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
