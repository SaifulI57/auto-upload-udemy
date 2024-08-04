import asyncio
from typing import Any
import httpx
# from playwright.async_api import async_playwright, Playwright
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
import os
import redis
import hashlib


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
            print("Requesting Base Url...")
            res = await client.get(self.channelUrl, headers=self.headers)
            content = b""
            async for chunk in res.aiter_bytes():
                content += chunk
            print("Done✅")
            soup = BeautifulSoup(content, "html.parser")
            print("Parsing html with bs4...")
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
            for i in soup.find_all("a", class_="tgme_widget_message_photo_wrap", style=True):
                try:
                    temp = re.search(r"background-image:url\(['\"]?(.*?)['\"]?\)",i['style']).group(1)
                    images.append(temp)
                except:
                    print("Non Type")
            links = [a_tag['href'] for a_tag in soup.find_all('a', href=True) if "coursekingdom.xyz" in a_tag['href']]
            description = [ x.decode_contents().split("<br/>") for x in soup.find_all(class_="tgme_widget_message_text")]
            for i, v in enumerate(description):
                print("looping description:", i)
                image = images[i]
                base_resp = await self.fetch_baseurl(links[i])
                parse_base = [self.parserUrl(x['href']) for x in base_resp.find_all("a", href=True)]
                base_links = [x for x in parse_base if x != "Not Found"][0]
                desc = BeautifulSoup(v[0], "html.parser").text
                
                
                
                hashdesc = self.md5_hash_string(desc)
                
                print("Checking existing hash...")
                resp = await self.redis_uri.get(hashdesc)
                
                if resp is not None:
                    print("Key Exists, Skipping...")
                    continue
                    
                
                
                if base_links == [] or base_links == "Not Found":
                    continue
                print("Creating gplinks...")
                gplinks = await client.get(f"https://api.gplinks.com/api?api={self.api_key}&url={base_links}")
                try:
                    payload = {
                        "long_url": gplinks.json()["shortenedUrl"]
                    }
                except:
                    continue
                headers = {
                    'X-Auth-Id': self.auth_id,
                    'X-Auth-Key': self.auth_key,
                    'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
                    'Content-Type': 'application/json'
                }
                print("Creating S.id link...")
                response = await client.post(
                    "https://api.s.id/v1/links",
                    json=payload,
                    headers=headers
                )
                try:
                    data = response.json()
                    data = "https://s.id/"+ data["data"]["short"]
                except:
                    print("Skipping S.id link, limit reached...")
                    print("Creating Local short link...")
                    response = await client.post("http://go_app:3000/short", data={"url": payload["long_url"]})
                    data = response.json()
                    data = "https://short.unbound.my.id/" + data["id"]
                description[i] = {"desc": BeautifulSoup("\n\n".join([x for x in v if x != " "][:4]), "html.parser").text + f"\nEnroll Now 👉: {data}", "image": image}
                await self.redis_uri.set(hashdesc, description[i])
            return description
        
    async def post_facebook(self, desc):
        async with httpx.AsyncClient(timeout=240.0) as client:
            for i in desc:
                try:
                    print("Try parsing to post facebook...")
                    data = {
                        "url": i["image"],
                        "message": i["desc"],
                        "published": "true",
                        "access_token": self.facebook_key
                    } 
                except:
                    print("Skipping parsing error occured...")
                    continue
                
                url = f"https://graph.facebook.com/v20.0/{self.page_id}/photos"
                print("Posting to Facebook...")
                res = await client.post(url, data=data)
                try:
                    print("Success")
                    if res.json()["id"] != "":
                        continue
                except:
                    print("Failed")
                    continue
            print("all done for now")
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
        post = await makeReq.post_facebook(soup)
        
        print("Posted")
        
        await asyncio.sleep(3 * 60 * 60)
        
        
        
        
if __name__ == "__main__":
    asyncio.run(main())