import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from time import sleep

from selenium import webdriver

regex = {
    "date" : r"[0-9]{8}-[0-9]{6}",
    "name" : r"(.*?.)( \([0-9]{8}-[0-9]{6}\).dat)"
}

no_intro_type = {
    "standard"     : "standard",
    "parent-clone" : "xml"
}

for key, value in no_intro_type.items():

    # Download no-intro pack using selenium
    dir_path = os.path.dirname(os.path.realpath(__file__))

    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", dir_path)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
    options.add_argument  ("-headless")

    service = webdriver.FirefoxService(log_output = "firefox-webdriver.log" , service_args = ["--log", "debug"])

    driver = webdriver.Firefox(service=service, options=options)
    driver.implicitly_wait(10)

    try:
        # load website
        driver.get("https://datomatic.no-intro.org/index.php")
        print("Loaded no-intro datomatic ...")

        # accept terms and conditions
        driver.find_element(by="xpath", value="/html/body/div/form/input[2]").click()

        # select "DOWNLOAD"
        driver.find_element(by="xpath", value="/html/body/div/header/nav/ul/li[3]/a").click()

        # select "daily"
        driver.find_element(by="xpath", value="/html/body/div/header/div/a[5]").click()

        # set the type of dat file
        if key == "standard" :
            driver.find_element(by="xpath", value="//input[@name='dat_type' and @value='dat']").click()
        if key == "parent-clone" :
            driver.find_element(by="xpath", value="//input[@name='dat_type' and @value='pc']").click()
        print(f"Set dat type to {key} ...")

        # select "Request"
        if key == "standard" :
            driver.find_element(by="xpath", value="/html/body/div/section/article/form/input[8]").click()
        if key == "parent-clone" :
            driver.find_element(by="xpath", value="/html/body/div/section/article/form/input[5]").click()
        sleep(5)

        # retry loop for download
        name = None
        timeout = 300
        max_retries = 3

        for attempt in range(max_retries):
            # select "Download"
            driver.find_element(by="xpath", value="/html/body/div/section/article/form/input[2]").click()
            print(f"Waiting for download to complete (Attempt {attempt + 1}/{max_retries}) ...")

            time_slept = 0
            while name is None and time_slept <= timeout:
                for f in os.listdir(dir_path):
                    if "No-Intro Love Pack" in f and not f.endswith(".part"):
                        try:
                            with zipfile.ZipFile(os.path.join(dir_path, f)):
                                pass
                            name = f
                            print("No-Intro zip file download completed ...")
                            break
                        except zipfile.BadZipfile:
                            pass

                if name is not None:
                    break

                # wait 5 seconds and check for download completion again
                sleep(5)
                time_slept += 5

            if name is not None:
                break

            print(f"Download timed out after {timeout} seconds ({timeout / 60} minutes). Retrying...")

    finally:
        # clean up selenium
        driver.quit()

    if name is None:
        raise FileNotFoundError(f"No-Intro {key} zip file not found after {max_retries} attempts, download failed")

    # setup archive path and rename
    archive_name = "no-intro.zip" if key == "standard" else f"no-intro_{key}.zip"
    archive_full = os.path.join(dir_path, archive_name)
    os.rename(os.path.join(dir_path, name), os.path.join(dir_path, archive_full))

    # load & extract zip file, there is currently no way to remove files from zip archive
    with zipfile.ZipFile(os.path.join(dir_path, archive_full), mode="r") as orig_archive:
        orig_archive.extractall()

    print("Building new archive ...")
    # delete unneeded files
    if os.path.exists("index.txt"):
        os.remove("index.txt")

    with zipfile.ZipFile(os.path.join(dir_path, archive_full), mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        target_folders = {"No-Intro", "Non-Redump", "Source Code", "Unofficial"}
        for f in os.listdir(dir_path):
            if f in target_folders:
                print(f"\nAdding {f} dats ...")
                target_dir = os.path.join(dir_path, f)
                for x in os.listdir(target_dir):
                    if x.endswith(".dat"):
                        print("Adding to Archive: ", x)
                        filepath = os.path.join(target_dir, x)
                        archive.write(filepath, arcname=x)
                        os.remove(filepath)
                shutil.rmtree(target_dir, ignore_errors=True)
        dat_files = archive.namelist()

    print("\nCreating new clrmamepro datfile ...\n")
    # clrmamepro XML file
    tag_clrmamepro = ET.Element("clrmamepro")
    for dat in dat_files:
        print(dat)

        # Check for regex matches before adding to XML
        date_matches = re.findall(regex["date"], dat)
        if not date_matches:
            print(f"\033[93mWarning: skipped {dat} due to invalid date format\033[0m")
            continue
        dat_date = date_matches[0]

        name_matches = re.findall(regex["name"], dat)
        if not name_matches:
            print(f"\033[93mWarning: skipped {dat} due to invalid name format\033[0m")
            continue
        temp_name = name_matches[0][0]

        # section for this dat in the XML file
        tag_datfile = ET.SubElement(tag_clrmamepro, "datfile")

        # XML version
        ET.SubElement(tag_datfile, "version").text = dat_date
        print(dat_date)

        # XML name & description
        ET.SubElement(tag_datfile, "name").text = temp_name
        ET.SubElement(tag_datfile, "description").text = temp_name
        print(temp_name)

        # URL tag in XML
        ET.SubElement(tag_datfile, "url").text = f"https://github.com/hugo19941994/auto-datfile-generator/releases/latest/download/{archive_name}"

        # File tag in XML
        file_name = dat
        file_name = f"{file_name[:-4]}.dat"
        ET.SubElement(tag_datfile, "file").text = file_name
        print(file_name)

        # Author tag in XML
        ET.SubElement(tag_datfile, "author").text = "no-intro.org"

        # Command XML tag
        ET.SubElement(tag_datfile, "comment").text = "_"

        print("\n")

    # store clrmamepro XML file
    xml_data = ET.tostring(tag_clrmamepro).decode()
    xml_filename = "no-intro.xml" if key == "standard" else f"no-intro_{key}.xml"

    xml_path = os.path.join(dir_path, xml_filename)
    with open(xml_path, "w", encoding="utf-8") as xmlfile:
        xmlfile.write(xml_data)

    print("Finished")
