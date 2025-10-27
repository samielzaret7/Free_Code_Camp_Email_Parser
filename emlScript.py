from email import policy
from email.parser import BytesParser
import requests
import logging
from datetime import date
import os
import time
import asyncio


async def keep_alive_task():
    while True:
        print("Process is alive...")
        await asyncio.sleep(30)

async def main():
    await keep_alive_task()

def eml_to_html(parent_folder):

    print("eml_to_html started execution.")

    logging.info('eml_to_html started execution.')

    folder_with_files = os.path.join(parent_folder, "EML_Files")

    html_list = []
    total_eml_files = 0
    for _,_,files in os.walk(folder_with_files):
        for file in files:
            if file.endswith(".eml"):

                total_eml_files+=1

                file_path = os.path.join(folder_with_files, file)
            
                file_data = {}

                with open(file_path, 'rb') as file:
                    msg = BytesParser(policy=policy.default).parse(file)
    
            
                plain_text_part = msg.get_body(preferencelist=('plain',))
                if plain_text_part:
                    try:
                        file_data["From"] = msg.get("From").split("<")[1].replace(">","")
                    except:
                        file_data["From"] = "Error when getting From data"

                    try:
                        file_data["Subject"] = msg.get("Subject")
                    except:
                        file_data["Subject"] = "Error when getting Subject data"

                    try:
                        file_data["Body"] = f"<html><body>{plain_text_part.get_content()}</body></html>"
                    except:
                        file_data["Body"] = "<html><body>Error when getting Body data</body></html>"

                    html_list.append(file_data)
                else:
                    file_data["From"] = "Couldn't get From data"
                    file_data["Subject"] = "Couldn't get Subject data"
                    file_data["Body"] = "<html><body>No content found</body></html>"

                    html_list.append(file_data)

    
    print(f"Total eml files in {folder_with_files}: {total_eml_files}")
    print(f"Total items in html_list: {len(html_list)}")
    logging.info(f"Total eml files in {folder_with_files}: {total_eml_files}")
    logging.info(f"Total items in html_list: {len(html_list)}")
    
    return html_list




def request_func(html_list):


    print('Request function started.')
    logging.info('Request function started.')
    
    total_items = 0
    for item in html_list:

        data = {
        "from": item["From"],
        "subject": item["Subject"],
        "html": item["Body"]
        }

        try:
            r = requests.post("http://127.0.0.1:8000/inbound", json=data)
            total_items+=r.json()["staged"]
            print(r.json())
            logging.info(f"Request posted successfully: {r.json()}")
            print(f"Request posted successfully: {r.json()}")
            
        except Exception as e:
            print(f"There was an error when posting the item {item}")
            print(f"Exception: {e}")
            logging.error(f"Exception: {e}")
            print(f"Exception: {e}")

    total_items_string = f"Total Items Staged: {total_items}"
    print(total_items_string)
    logging.info(total_items_string)



def request_main():

    print("Request main started")

    for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
    
    parent_folder = os.getcwd()

    print(f"Parent folder: {parent_folder}")

    today_folder = os.path.join(parent_folder, f"logs/{str(date.today())}")

    print(f"Today folder: {today_folder}")

    if (not os.path.isdir(today_folder)):
        os.mkdir(today_folder)


    log_file = today_folder + "/FreeCodeCampRequestLog.log"

    print(f"Log file: {log_file}")

    time.sleep(5)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] - %(message)s',
        filename=log_file)
    
    logging.info('Request main started.')

    try:
        
        html_list = eml_to_html(parent_folder)

        request_func(html_list)

    except Exception as e:
        print(f"Exception: {e}")
        logging.error(f"Exception on main: {e}")
        print(f"Exception on main: {e}")

    logging.info('Request main finished.')
    print('Request main finished.')



request_main()
        
