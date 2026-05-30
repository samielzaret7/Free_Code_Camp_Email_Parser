"""
eml_reader.py

Manual override: reads .eml files from /EML_Files, parses headers + body,
moves processed files to /EML_Files/Processed/.

Returns a list of dicts compatible with emlScript.request_func().
"""

import logging
import os
import shutil
from email import policy
from email.parser import BytesParser
from typing import Dict, List


def eml_to_html(parent_folder: str) -> List[Dict[str, str]]:
    """
    Scan ``parent_folder/EML_Files/`` for *.eml files, parse each one
    into {From, Subject, Body} dicts, and move them to a Processed/ sub-folder.
    """
    logging.info("eml_to_html started execution.")

    folder_with_files = os.path.join(parent_folder, "EML_Files")

    html_list: List[Dict[str, str]] = []
    total_eml_files = 0
    total_processed_files = 0
    total_failed_files = 0

    for _, _, files in os.walk(folder_with_files):
        for file in files:
            if not file.endswith(".eml"):
                continue

            total_eml_files += 1
            file_path = os.path.join(folder_with_files, file)
            file_data: Dict[str, str] = {}

            if not os.path.exists(file_path):
                continue

            try:
                with open(file_path, "rb") as opened_file:
                    msg = BytesParser(policy=policy.default).parse(opened_file)

                plain_text_part = msg.get_body(preferencelist=("plain",))
                html_part = msg.get_body(preferencelist=("html",))

                try:
                    from_header = msg.get("From", "")
                    file_data["From"] = from_header.split("<")[1].replace(">", "")
                except Exception:
                    file_data["From"] = "Error when getting From data"

                try:
                    file_data["Subject"] = msg.get("Subject") or "Error when getting Subject data"
                except Exception:
                    file_data["Subject"] = "Error when getting Subject data"

                if html_part:
                    try:
                        file_data["Body"] = html_part.get_content()
                    except Exception:
                        file_data["Body"] = "<html><body>Error when getting Body data</body></html>"
                elif plain_text_part:
                    try:
                        file_data["Body"] = f"<html><body>{plain_text_part.get_content()}</body></html>"
                    except Exception:
                        file_data["Body"] = "<html><body>Error when getting Body data</body></html>"
                else:
                    file_data["Body"] = "<html><body>No content found</body></html>"

                html_list.append(file_data)
                total_processed_files += 1

                processed_dir = os.path.join(folder_with_files, "Processed")
                os.makedirs(processed_dir, exist_ok=True)
                processed_file = os.path.join(processed_dir, file)
                shutil.move(file_path, processed_file)

            except Exception:
                logging.exception("Failed processing EML file: %s", file_path)
                file_data["From"] = "Couldn't get From data"
                file_data["Subject"] = "Couldn't get Subject data"
                file_data["Body"] = "<html><body>No content found</body></html>"
                html_list.append(file_data)
                total_failed_files += 1

    logging.info("Total eml files in %s: %s", folder_with_files, total_eml_files)
    logging.info("Total files successfully processed: %s", total_processed_files)
    logging.info("Total failed files: %s", total_failed_files)
    logging.info("Total items in html_list: %s", len(html_list))

    return html_list
