import zendriver as Driver
import asyncio
import os
import time
from curl_cffi import requests
import json
import re
from random import uniform, randint

async def POST(url, headers, session, data = None, json = None):
    response = await session.post(
        url,
        headers=headers,
        data=data,
        json=json,
        impersonate="firefox"  # or "chrome114"
    )
    if response.status_code != 200:
        print("Failed to retrieve data. Status code:", response.status_code)
        print("Response:", response.text)
        exit(1)
    return response




async def create_contacts(favorites_list, parsed_urls, session: requests.AsyncSession, headers, authdata):
    async def clone_driver(cookies, local_storage, session_storage):
        slave = await Driver.start(headless=True, no_sandbox=True, browser_executable_path='/usr/bin/chromium-browser')
        # await slave.cookies.set_all(cookies)
        page = await slave.get("https://www.furnishedfinder.com")
        await page.wait(uniform(3.0, 6.0))
        await page.evaluate(f"{local_storage}")
        await page.evaluate(f"{session_storage}")
        return slave


    async def get_metdata(browser, page, url):
        attempts = 0
        candidates = None
        while True:
            candidates = await page.find_elements_by_text('Call The Landlord')
            if candidates:
                break
            else:
                attempts += 1
                if attempts >= 3:
                    raise Exception(f"Phone menu not found at {url}")
                await page.wait(uniform(3.0, 5.0))
        index = 1
        for candidate in candidates:
            if candidate:
                await candidate.apply("candidate => candidate.click()")
                await browser.wait(uniform(3.0, 5.0))
                finder = await page.query_selector_all("div.flex.flex-col.items-center.gap-4")
                if not finder:
                    await browser.wait(uniform(3.0, 5.0))
                    finder = await page.query_selector_all("div.flex.flex-col.items-center.gap-4")
                    if index >= len(candidates) and not finder:
                        return "Not Provided"
                    if not finder:
                        index += 1
                        continue
                for menu in finder:
                    text = menu.text_all
                    match = re.search(r'(\([0-9]{3}\) [0-9]{3}\-[0-9]{4})', text)
                    if match:
                        return text
                if index >= len(candidates):
                    return "Not Provided"
                index += 1
                #If phone number wasn't found

    async def parse_favorite(property, url):
        nonlocal parsed
        slave = await clone_driver(zendriver_cookies, local_storage, session_storage)
        await slave.wait(uniform(0.5, 1.5))
        page = await slave.get(url)
        attempts = 0
        loaded = False
        while True:
            attempts += 1
            try:
                await page.wait_for_ready_state('complete', uniform(3 + (attempts ** 2), 3 + (attempts ** 2) + 2))
                loaded = True
                break
            except:
                page = await slave.get(url)
            finally:
                if attempts >= 3:
                    break
        valid = True
        phone_blocked = await page.query_selector('button.cursor-not-allowed')
        target = await page.evaluate("window.location.href")
        if loaded and (target == "https://www.furnishedfinder.com/" or phone_blocked): #Redirect due to invalid link or blocked button
            metadata = 'Not Provided'
            valid = False
        contact = {}
        attempts = 0
        metadata = 'Not Provided'
        while valid:
            target = await page.evaluate("window.location.href")
            phone_blocked = await page.query_selector('button.cursor-not-allowed')
            if target == "https://www.furnishedfinder.com/" or phone_blocked:
                break
            attempts += 1
            subattempts = 0
            success = False
            error = ""
            while True:
                subattempts += 1
                error = ""
                try:
                    metadata = await get_metdata(slave, page, url)
                    if metadata != 'Not Provided':
                        success = True
                        break
                    elif subattempts >= 3:
                        break
                except Exception as e:
                    error = e
                    metadata = 'Not Provided' 
                    if subattempts >= 3:
                        break
                await page.wait_for_ready_state('complete', uniform(3 + (attempts ** 2), 3 + (attempts ** 2) + 2))
            if success:
                break
            elif attempts >= 3:
                if error:
                    with open('error.txt', 'a') as file:
                        file.write(f"{url}:\n{str(error)}\n\n")
                break
            else:
                page = await slave.get(url)
                await page.wait_for_ready_state('complete', uniform(3 + (attempts ** 2), 3 + (attempts ** 2) + 2)) #longer wait each time
            
        phone = 'Not Provided'
        name = 'Not Provided'
        location = 'Not Provided'
        if metadata != 'Not Provided':
            match = re.search(r'(\([0-9]{3}\) [0-9]{3}\-[0-9]{4})', metadata)
            phone = match.group(1)
            range = match.span()[1]
            metadata = metadata[range+1: ].split(' ')
            try:    
                def find_city():
                    nonlocal buffer
                    city = ""
                    while buffer < len(metadata):
                        temp = metadata[buffer]
                        buffer += 1
                        if re.search(',', temp):
                            temp = temp[0:-1]
                            city += temp
                            city = city.strip()
                            return city
                        city += temp
                    return 'Not Provided'

                buffer = 0
                name = metadata[0]
                buffer += 1
                if re.fullmatch(r'([A-Z])|([A-Z]\.?)', name):
                    name = f" {metadata[buffer]}"
                    buffer += 1

                city = find_city()
                if city == 'Not Provided':
                    location = 'Not Provided'
                else:
                    state = metadata[buffer]
                    location = f"{city}, {state}"
                    if not re.fullmatch(r'([A-Z][a-z]*)|([A-Z]\.\s[A-Z][a-z]*)', name):
                        contact['name'] = 'Not Provided'
                        buffer = 0
                        city = find_city()
                        if city == 'Not Provided':
                            location = 'Not Provided'
                        else:
                            state = metadata[buffer]
                            location = f"{city}, {state}"

                    if not re.fullmatch(r'[A-Z][a-z]*, [A-Z]{2}', location):
                        contact['location'] = 'Not Provided'
            
            except Exception as e:
                contact['name'] = 'Not Provided'
                contact['location'] = 'Not Provided'
                with open('error.txt', 'a') as file:
                    file.write(f"Issue while parsing metadata: {str(e)}\n\n")
                    
        contact['phone'] = phone
        contact['name'] = name
        contact['location'] = location
        contact['url'] = url
        contact['desc'] = property['name']
        contact['details'] = property['details']
        if page:
            await page.close()
        return contact

    
    # session = requests.AsyncSession()
    cookies = session.cookies.jar
    headers = headers

    zendriver_cookies = [
        {
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'path': cookie.path,
            'secure': cookie.secure,
            'httpOnly': cookie.has_nonstandard_attr('HttpOnly'),
            'sameSite': cookie.has_nonstandard_attr('SameSite'),
        }
        for cookie in cookies
    ]

    new_contacts = []
    local_storage = f"localStorage.setItem('authdetailnew', '{authdata}')" 
    session_storage = f"sessionStorage.setItem('authdetailnew', '{authdata}')"
    tasks = []
    parsed = 0

    chill = randint(2,4)
    for property in favorites_list:
        property_id = property['id'].lstrip('Prop')
        url = f"https://www.furnishedfinder.com/property/{property_id}"
        if url in parsed_urls:
            continue
        if parsed >= chill * 2:
            break
        task = asyncio.create_task(parse_favorite(property, url))
        tasks.append(task)
        parsed += 1
        if parsed != 0 and parsed % chill == 0:
            new_contacts.extend(await asyncio.gather(*tasks))
            tasks = []
            await asyncio.sleep(uniform(3.0 , 6.0))  # To avoid overwhelming the server
        else:
            await asyncio.sleep(uniform(2.0, 3.0))
    new_contacts.extend(await asyncio.gather(*tasks))
    return new_contacts

        

async def main():
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    start = time.time()
    session = requests.AsyncSession()
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Safari/537.36',
        "Accept": "*/*",
        "Content-Type": "application/json; charset=utf-8",
        "Origin": "https://www.furnishedfinder.com",
        "Referer": "https://www.furnishedfinder.com/",
        "Ff-Origin": "FF-Web",
        "og-api-client-name": "web-modules"
    }
    payload = {
        "username": username,
        "password": password
    }
  
    login_response = await POST(
        "https://s12core.furnishedfinder.com/api/PwaData/WMSLoginUpdated",
        headers=headers,
        json=payload,
        session=session
    )

    response_data = json.loads(login_response.text)
    token = response_data['Value']['TokenString'].split('--jwttoken')[1].split('--user')[0]
    encrypted_username = response_data['Value']['EncryptedUserName']
    authdata = response_data['Value']['TokenString']

    # Sets cookies for the session in the backend
    verify_response = await POST(
        "https://www.furnishedfinder.com/pwaData.aspx/UserVerifyCookie",
        headers=headers,
        json={"verify": encrypted_username},
        session=session
    )


    headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/json; charset=utf-8',
        'token': token,
        'ff-origin': 'FF-Web',
        'X-Requested-With': 'XmlHttpRequest',
        'Origin': 'https://www.furnishedfinder.com',
        'Connection': 'keep-alive',
        'Referer': 'https://www.furnishedfinder.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'DNT': '1',
        'Sec-GPC': '1',
        'Content-Length': '0',
        'TE': 'trailers'
    }


    favorites_response = await POST(
        "https://s7core.furnishedfinder.com/api/Favorites/GetFavoriteList?cityState=",
        headers=headers,
        session=session
    )
    favorites_list = json.loads(favorites_response.text)['Value']


    parsed_urls = set()
    if os.path.exists('urls.txt'):
        with open('urls.txt', 'r') as file:
            for line in file:
                url = line.strip()
                if url:
                    parsed_urls.add(url)
    if os.path.exists('blocked.txt'):
        with open('blocked.txt') as file:
            for line in file:
                url = line.strip()
                if url:
                    parsed_urls.add(url)

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Safari/537.36',
        "Accept": "*/*",
        "Content-Type": "application/json; charset=utf-8",
        "Origin": "https://www.furnishedfinder.com",
        "Referer": "https://www.furnishedfinder.com/",
        "Ff-Origin": "FF-Web",
        "og-api-client-name": "web-modules"
    }
    
    if os.getenv("BURNER_USERNAME") != username:
        username = os.getenv("BURNER_USERNAME")
        password = os.getenv("BURNER_PASSWORD")
        payload = {
            "username": username,
            "password": password
        }
    
        login_response = await POST(
            "https://s12core.furnishedfinder.com/api/PwaData/WMSLoginUpdated",
            headers=headers,
            json=payload,
            session=session
        )

        response_data = json.loads(login_response.text)
        token = response_data['Value']['TokenString'].split('--jwttoken')[1].split('--user')[0]
        encrypted_username = response_data['Value']['EncryptedUserName']
        authdata = response_data['Value']['TokenString']

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Safari/537.36',
        'Accept': 'text/x-component',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': 'https://www.furnishedfinder.com/property/657089_1',
        'token': token,
        # 'Next-Action': '40806bbf717ad9b3f34bf0f07fe66c56e3eb73751e',
        'Content-Type': 'text/plain;charset=UTF-8',
        'Origin': 'https://www.furnishedfinder.com',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'DNT': '1',
    }


    

    new_contacts = await create_contacts(favorites_list, parsed_urls, session, headers, authdata)
    

    delete_list = []
    index = 0
    buffer = 0
    new_urls = set()
    for contact in new_contacts:
        if contact["phone"] == "Not Provided":
            with open('blocked.txt', 'a') as file:
                file.write(f"{contact['url']}\n")
            delete_list.append(index - buffer)
            buffer += 1
        else:
            new_urls.add(contact['url'])
            print(f"Name: {contact['name']}")
            print(f"Phone: {contact['phone']}")
            print(f"Location: {contact['location']}")
            print(f"URL: {contact['url']}")
            print("-" * 20)
        index += 1

    for index in delete_list:
        del new_contacts[index]


    with open('urls.txt', 'a') as file:
        for url in new_urls:
            file.write(url + "\n")

    webhook_url = 'https://services.leadconnectorhq.com/hooks/BNVJPUHZCILegkR51b4g/webhook-trigger/528d4656-d561-4591-b885-1c1a33dda461'
    tasks = []
    for contact in new_contacts:
        task = asyncio.create_task(POST(url=webhook_url, headers=[], session=session, json=contact))
        tasks.append(task)
    for response in await asyncio.gather(*tasks):
        if response.status_code == 200:
            print("Data sent successfully!")
        else:
            print("Failed to send data. Status code:", response.status_code)
            print("Response:", response.text)
    end = time.time()
    print("Length of favorites list: " + str(len(favorites_list)))
    print("Total time: " + str(end - start) + " seconds")
    return

if __name__ == '__main__':
    asyncio.run(main())
