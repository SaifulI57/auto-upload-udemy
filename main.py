import asyncio
from typing import Any
import httpx
# from playwright.async_api import async_playwright, Playwright
from bs4 import BeautifulSoup
from loguru import logger
import re
from dotenv import load_dotenv
import os
import redis
import hashlib
import json

load_dotenv()



class BaseRequest():
    api_key = os.getenv("api_key")
    auth_id = os.getenv("auth_id")
    auth_key = os.getenv("auth_key")
    facebook_key = os.getenv("facebook_key")
    page_id = os.getenv("page_id")
    redis_uri = redis.from_url(os.getenv("redis_url"))
    
    def __init__(self, channelUrl: str) -> None:
        self.channelUrl = channelUrl
        self.headers = {
            "Host": "t.me",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Chromium";v="112"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/112.0.5615.50 Safari/537.36"),
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "DNT": "1",  
            "Cache-Control": "no-cache",  
            "Pragma": "no-cache",  
            "Sec-Ch-Ua-Arch": "x86",  
            "Sec-Ch-Ua-Full-Version": "112.0.5615.50", 
        }
    def parserUrl(self, url: str) -> str:
        pattern = r"https://www\.udemy\.com/.*/.*/\?couponCode=[a-zA-Z0-9]+"
        match = re.search(pattern, url)
        return match.group() if match else "Not Found"
    def md5_hash_string(self, s: str) -> str:
        hash_object = hashlib.md5()
        
        hash_object.update(s.encode('utf-8'))
        
        return hash_object.hexdigest()
    
    async def make_request(self):
        async with httpx.AsyncClient() as client:
            logger.info(f"Initiating request to {self.channelUrl}...")
            res = await client.get(self.channelUrl, headers=self.headers)
            content = b""
            async for chunk in res.aiter_bytes():
                content += chunk
            logger.info("Request successful.")
            soup = BeautifulSoup(content, "html.parser")
            logger.info("Parsing HTML content with BeautifulSoup...")
            soup = await self.extract_soup(soup)
            return soup
    async def test_request(self):
        async with httpx.AsyncClient() as client:
            res = await client.get(self.channelUrl, headers=self.headers)
            content = b""
            async for chunk in res.aiter_bytes():
                content += chunk
            soup = BeautifulSoup(content, "html.parser")
            return soup
    async def fetch_baseurl(self, url: str):
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            content = b""
            async for chunk in res.aiter_bytes():
                content += chunk
            soup = BeautifulSoup(content, "html.parser")
            return soup
    async def extract_soup(self, soup: BeautifulSoup):
        async with httpx.AsyncClient() as client:
            images = []
            logger.info("Extracting messages from soup...")
            for i in soup.find_all("a", class_="tgme_widget_message_photo_wrap", style=True):
                try:
                    temp = re.search(r"background-image:url\(['\"]?(.*?)['\"]?\)",i['style']).group(1)
                    images.append(temp)
                    logger.info(f"Extracted image URL: {temp}")
                except:
                    logger.error("Error extracting image URL.")
            links = [a_tag['href'] for a_tag in soup.find_all('a', href=True) if "coursekingdom.xyz" in a_tag['href']]
            description = [ x.decode_contents().split("<br/>") for x in soup.find_all(class_="tgme_widget_message_text")]
            for i, v in enumerate(description):
                logger.info(f"Processing description {i+1}/{len(description)}...")
                image = images[i]
                base_resp = await self.fetch_baseurl(links[i])
                parse_base = [self.parserUrl(x['href']) for x in base_resp.find_all("a", href=True)]
                base_links = [x for x in parse_base if x != "Not Found"][0]
                desc = BeautifulSoup(v[0], "html.parser").text
                
                
                
                hashdesc = self.md5_hash_string(desc)
                
                logger.info(f"Checking if description hash {hashdesc} exists in Redis...")
                resp = self.redis_uri.get(hashdesc)
                
                if resp is not None:
                    logger.info("Description hash found in Redis. Skipping...")
                    del description[i]
                    continue
                    
                
                
                if base_links == [] or base_links == "Not Found":
                    logger.info("No Udemy link found. Skipping...")
                    del description[i]
                    continue
                if os.getenv("deploy") == "development":
                    description[i] = {"desc": BeautifulSoup("\n\n\n".join([x for x in v if x != " "][:4]), "html.parser").text + f"\nEnroll Now 👉: {base_links}", "image": image}
                else:
                    logger.debug("Creating gplinks...")
                    gplinks = await client.get(f"https://api.gplinks.com/api?api={self.api_key}&url={base_links}")
                    try:
                        payload = {
                            "long_url": gplinks.json()["shortenedUrl"]
                        }
                        logger.warning("Error parsing gplinks response into payload.")
                    except:
                        logger.error("Error parsing gplinks response. Skipping...")
                        del description[i]
                        continue
                    headers = {
                        'X-Auth-Id': self.auth_id,
                        'X-Auth-Key': self.auth_key,
                        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
                        'Content-Type': 'application/json'
                    }
                    logger.info("Creating S.id link...")
                    response = await client.post(
                        "https://api.s.id/v1/links",
                        json=payload,
                        headers=headers
                    )
                    try:
                        data = response.json()
                        data = "https://s.id/"+ data["data"]["short"]
                        logger.info("S.id link created successfully.")
                    except:
                        logger.error("Error creating S.id link. Moving creating localy...")
                        response = await client.post("http://go_app:3000/short", data={"url": payload["long_url"]})
                        data = response.json()
                        data = "https://short.unbound.my.id/" + data["id"]
                    description[i] = {"desc": BeautifulSoup("\n\n\n".join([x for x in v if x != " "][:4]), "html.parser").text + f"\nEnroll Now 👉: {data}", "image": image}
                self.redis_uri.setex(hashdesc, 6 * 60 * 60, json.dumps(description[i]))
            return description
        
    async def post_facebook(self, desc):
        async with httpx.AsyncClient(timeout=240.0) as client:
            for i in desc:
                if type(i) != list:
                    try:
                        logger.info(f"Attempting to parse content for Facebook post...")
                        data = {
                            "url": i["image"],
                            "message": i["desc"],
                            "published": "true",
                            "access_token": self.facebook_key
                        } 
                        logger.info("Content parsed successfully...")
                    except Exception as e:
                        logger.warning(f"Error preparing data for Facebook post: {e}")
                        continue
                    
                    url = f"https://graph.facebook.com/v20.0/{self.page_id}/photos"
                    logger.info("Initiating post to Facebook...")
                    res = await client.post(url, data=data)
                    try:
                        logger.info(f"f{res.json()}")
                        if res.json()["id"] != "":
                            continue
                        logger.info("Post to Facebook successful.")
                    except:
                        logger.error("Error parsing Facebook response.")
                        continue
            logger.info("all done for now")
    # async def fetch_page_udemy(self):
    #     async with async_playwright() as p:
    #         browser = await p.chromium.launch(headless=True)
    #         page = await browser.new_page()
    #         try:
    #             await page.set_extra_http_headers(self.headers)
    #             await page.goto(self.channelUrl, wait_until="networkidle")
    #             await page.wait_for_load_state('networkidle')
    #             content = await page.content()
    #         except Exception as e:
    #             print(f"Error fetching page: {e}")
    #             return None
    #         finally:
    #             await browser.close()
    #         content = BeautifulSoup(content, "html.parser")
    #         return content

# async def run(playwright: Playwright):
#     chromium = playwright.chromium 
#     browser = await chromium.launch_persistent_context(user_data_dir=r"C:\Users\saifu\AppData\Local\Google\Chrome\User Data",headless=False, args=["--profile-directory=Profile 13"])
#     page = await browser.new_page()
#     await page.goto("https://www.udemy.com/course/marketing-digital-facebook-ads-ecommerce-ventas-online-dropshipping/?couponCode=310724")
#     print(await page.content())


async def main():
    makeReq = BaseRequest("https://t.me/s/udemycoursesfree")

    while True:
        soup = await makeReq.make_request()
        await makeReq.post_facebook(soup)
        
        logger.info("Posted to Facebook. Sleeping for 1 hour 20 minutes.")
        await asyncio.sleep(80 * 60)
        
        
        
        
if __name__ == "__main__":
    asyncio.run(main())