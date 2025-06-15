import zendriver as Driver
import asyncio
import os
import time
from curl_cffi import requests
import json
import re
from random import uniform
import math
import random

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


async def clone_driver(cookies, local_storage, session_storage): 
    slave = await Driver.start(headless=True, no_sandbox=True, browser_executable_path='/usr/bin/chromium-browser')
    # await slave.cookies.set_all(cookies)
    page = await slave.get("https://www.furnishedfinder.com")
    await page.wait(uniform(1.0, 3.0))
    await page.evaluate(f"{local_storage}")
    await page.evaluate(f"{session_storage}")
    return slave

async def create_contacts(property, session: requests.AsyncSession, headers, authdata):
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
                    await browser.wait(uniform(1.0, 3.0))
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

    async def parse_favorite(url):
        nonlocal parsed
        slave = await clone_driver(zendriver_cookies, local_storage, session_storage)
        await slave.wait(uniform(1.0, 3.0))
        page = await slave.get(url)
        await page.wait(uniform(1.0, 3.0))
        
        contact = {}
        attempts = 0
        metadata = ''
        while True:
            try:
                metadata = await get_metdata(slave, page, url)
                if metadata != 'Not Provided':
                    break
                attempts += 1
                if attempts >= 3:
                    break
            except Exception as e:
                metadata = 'Not Provided' 
                attempts += 1
                if attempts >= 3:
                    with open('error.txt', 'a') as file:
                        file.write(f"{url}:\n{str(e)}\n\n")
                    break
            page = await slave.get(url)
            await page.wait(uniform(3 + (attempts ** 2), 3 + (attempts ** 2) + 2)) #longer wait each time
            
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

    contact = await parse_favorite(property)

    return contact

        

async def main():
    username = os.getenv("BURNER_USERNAME")
    password = os.getenv("BURNER_PASSWORD")
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

    # local_storage = f"localStorage.setItem('authdetailnew', '{authdata}')" 
    # session_storage = f"sessionStorage.setItem('authdetailnew', '{authdata}')"
    # random_list = [
    #     "Gainesville, Florida",
    #     "Tampa, Florida",
    #     "Orlando, Florida",
    #     "King George, Virginia",
    #     "Charleston, South Carolina",
    #     "Fredericksburg, Virginia"
    # ]
    # random_choice = random.choice(random_list)
    # slave = await clone_driver({}, local_storage=local_storage, session_storage=session_storage)
    # page = await slave.get("https://furnishedfinder.com")
    # await page.wait(uniform(1.0, 3.0))
    # search_bar = await page.find_element_by_text("Enter a destination")
    # await search_bar.click()
    # await page.wait(uniform(0.5, 1.0))
    # await search_bar.send_keys(random_choice)
    # await page.wait(uniform(1.0, 1.5))
    # search = await page.query_selector("#search-btn")
    # await search.apply("search => search.click()")
    # await page.wait(uniform(3.0, 6.0))
    # i = 0
    # scrolls = random.randint(0,5)
    # while i < scrolls:
    #     await page.scroll_down(random.randint(5, 25))
    #     await page.wait(uniform(1.0, 3.0))
    #     i += 1
    # await page.scroll_up(random.randint(0,10))
    # properties = await page.query_selector_all('div[data-testid="property-cards"')
    # property = random.choice(properties)
    # await page.wait(uniform(1.0, 3.0))
    # await property.click()
    # await page.close()

    favorites_list = [
        "https://www.furnishedfinder.com/property/657089_1",
        "https://www.furnishedfinder.com/property/573206_1",
        "https://www.furnishedfinder.com/property/778254_1",
        "https://www.furnishedfinder.com/property/669699_1",
        "https://www.furnishedfinder.com/property/795612_1",
        "https://www.furnishedfinder.com/property/770249_1",
        "https://www.furnishedfinder.com/property/572042_1",
        "https://www.furnishedfinder.com/property/515055_1",
        "https://www.furnishedfinder.com/property/745115_1"     
    ]

    expected = [
        "(716) 498-0151",
        "(718) 790-1579",
        "(917) 805-4151",
        "(347) 292-1261",
        "(714) 719-4608",
        "(714) 804-6899",
        "(626) 203-3821",
        "(714) 679-3839",
        "(657) 642-7666"
    ]

    choice = random.randint(0, 8)
    favorite = favorites_list[choice]
    expected = expected[choice]

    contact = await create_contacts(favorite, session, headers, authdata)
    number = contact['phone']
    if number != expected:
        raise Exception(f"Received: {number} | Expected: {expected}" + "\nThere seems to be a mismatch (or the link has become invalid)")

    end = time.time()
    print("Total time: " + str(end - start) + " seconds")
    return

if __name__ == '__main__':
    asyncio.run(main())
